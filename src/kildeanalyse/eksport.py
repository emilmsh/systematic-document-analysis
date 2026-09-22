"""Resultatpakke: CSV-filer, lesbar oversikt, plan, manifester og valgfrie kildekopier.

Pakken skal kunne leses uten appen. Simulerte kjøringer merkes tydelig. Ingen hemmeligheter
skrives ut (miljøvariabler og tokens inngår ikke i manifestene).
"""
from __future__ import annotations

import csv
import json
import shutil
import tempfile
from uuid import uuid4
from datetime import datetime
from pathlib import Path
from typing import Any

from . import VERSJON
from .konfig import undermappe
from .lager import FS_FULLFORT, FS_VALIDERINGSFEIL, KONTROLL_GODKJENT, KONTROLL_RETTET, Lager
from .prompt import bygg_systeminstruks
from .parametre import fra_plan
from .source_formats import location, metadata, annotate_assessments
from .call_evidence import call_records, call_warnings


def _skriv_csv(sti: Path, rader: list[dict[str, Any]], felter: list[str]) -> None:
    with open(sti, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=felter, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for r in rader:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})


def _legacy_export(lager: Lager, analyse_id: str, *, med_kilder: bool = False,
                   destination: Path | None = None) -> dict[str, Any]:
    from .tjeneste import gjeldende_vurderinger

    analyse = lager.analyse(analyse_id)
    prosjekt = lager.prosjekt(analyse["prosjekt_id"])
    versjoner = lager.planversjoner(analyse_id)
    gjeldende = lager.gjeldende_planversjon(analyse_id)
    kjoringer = lager.kjoringer(analyse_id)
    stempel = datetime.now().strftime("%Y%m%d-%H%M%S")
    mappe = destination or undermappe(f"eksport/{analyse_id}_{stempel}-{uuid4().hex[:8]}", lager.mappe)
    (mappe / "forsok").mkdir(exist_ok=True)

    alle_kriterier: list[str] = []
    for v in versjoner:
        for k in v["plan"].kriterier:
            if k.id not in alle_kriterier:
                alle_kriterier.append(k.id)

    resultatrader, beleggrader, forsokrader, kontrollrader, json_kjoringer = [], [], [], [], []
    model_calls = []
    teller: dict[str, int] = {}
    kontrollert_totalt = vurderinger_totalt = 0
    motorer: set[str] = set()
    simulert_finnes = ekte_finnes = False
    planversjoner_brukt: set[str] = set()

    for kj in kjoringer:
        teller[kj["status"]] = teller.get(kj["status"], 0) + 1
        planversjoner_brukt.add(kj["planversjon_id"])
        dok = lager.dokument(kj["dokument_id"])
        planrad = lager.planversjon(kj["planversjon_id"])
        parametre = fra_plan(planrad["plan"])
        api = parametre.get('api', {})
        api_felter = {'language': parametre['language'], 'api_endpoint': api.get('endpoint', ''), 'api_provider_valg': api.get('provider', ''),
                      'maks_output_tokens': api.get('maks_output_tokens', '')}
        forsok = lager.forsok_for_kjoring(kj["id"])
        gjeld = next((f for f in forsok if f["id"] == kj["gjeldende_forsok_id"]), forsok[-1] if forsok else None)
        rad: dict[str, Any] = {
            **api_felter,
            "kjoring_id": kj["id"], "dokument_id": dok["id"], "dokument": dok["navn"], "sha256": dok["sha256"],
            "planversjon": planrad["versjon"], "status": kj["status"], "forsok_id": gjeld["id"] if gjeld else "",
            "antall_forsok": len(forsok), "motor": gjeld["motor"] if gjeld else "", "simulert": "" if not gjeld else ("JA" if gjeld["simulert"] else "nei"),
            "modell": gjeld.get("modell_rapportert") if gjeld else "", "sesjon_id": gjeld.get("sesjon_id") if gjeld else "",
            "modell_onsket": parametre["modell"], "tenkenivaa_onsket": parametre["tenkenivaa"],
            "lesedekning": "", "kontrollert_av_totalt": "", "merknad": kj.get("merknad") or (gjeld.get("feil") if gjeld else ""),
        }
        vurd = None
        if gjeld:
            motorer.add(gjeld["motor"])
            simulert_finnes |= bool(gjeld["simulert"])
            ekte_finnes |= not gjeld["simulert"]
        if gjeld and gjeld["status"] in (FS_FULLFORT, FS_VALIDERINGSFEIL) and gjeld.get("svar_json"):
            vurd = annotate_assessments(dok, gjeldende_vurderinger(lager, gjeld, planrad["plan"]))
            validering = json.loads(gjeld["validering_json"]) if gjeld.get("validering_json") else {}
            ld = validering.get("lesedekning", {})
            rad["lesedekning"] = f"{len(ld.get('sider_lest_oppgitt', []))}/{len(ld.get('sider_i_dokument', []))} kildeenheter" + ("" if ld.get("fullstendig") else " (ufullstendig)")
            kontrollert = sum(1 for v in vurd.values() if v["kontrollstatus"] in (KONTROLL_GODKJENT, KONTROLL_RETTET))
            rad["kontrollert_av_totalt"] = f"{kontrollert}/{len(vurd)}"
            kontrollert_totalt += kontrollert
            vurderinger_totalt += len(vurd)
            for kid, v in vurd.items():
                rad[f"{kid}_svar"] = v["svar"]
                rad[f"{kid}_kontroll"] = v["kontrollstatus"] + (" (rettet)" if v["kilde"] == "rettet" and v["kontrollstatus"] != KONTROLL_RETTET else "")
                rad[f"{kid}_validering"] = "ok" if v["validering_gyldig"] else ("feil: " + " | ".join(v["valideringsfeil"]))
                sidetekst = {s["nr"]: s["tekst"] for s in dok["sider"]}
                from .dokument import belegg_finnes

                for b in v["belegg"]:
                    beleggrader.append({
                        "kjoring_id": kj["id"], "forsok_id": gjeld["id"], "dokument": dok["navn"], "kriterium": kid, "svar": v["svar"],
                        "fysisk_side": b.get("side") if metadata(dok)['format'] == 'pdf' else '',
                        'source_unit':b.get('side'), 'source_location':location(dok,b.get('side'))['location'],
                        'source_format':metadata(dok)['format'], "sitat": b.get("sitat"), "kilde": v["kilde"],
                        "sitat_funnet_paa_side": "ja" if any(s['nr'] == b.get('side') and belegg_finnes(str(b.get('sitat','')), s) for s in dok['sider']) else "NEI",
                    })
        resultatrader.append(rad)
        for f in forsok:
            model_calls.extend(call_records(f, dok['navn']))
            forsokrader.append({k: f.get(k) for k in ("id", "kjoring_id", "nr", "status", "startet", "avsluttet", "motor", "simulert",
                                                     "modell_onsket", "modell_rapportert", "sesjon_id", "input_hash", "feil")}
                               | {"tenkenivaa_onsket": parametre["tenkenivaa"]} | api_felter)
            for ko in lager.kontroller(f["id"]):
                kontrollrader.append({k: ko.get(k) for k in ("id", "forsok_id", "tid", "ansvarlig", "handling", "kriterium_id", "begrunnelse")}
                                     | {"opprinnelig": json.dumps(ko["opprinnelig"], ensure_ascii=False), "nytt": json.dumps(ko["nytt"], ensure_ascii=False)})
            kilde = Path(f["input_sti"])
            if kilde.is_dir():
                maal = mappe / "forsok" / f["id"]
                maal.mkdir(exist_ok=True)
                for navn in ("input.json", "manifest.json", "raasvar.txt", "systeminstruks.txt", 'file-workspace.json', 'reader-helper.py'):
                    if (kilde / navn).is_file():
                        shutil.copy2(kilde / navn, maal / navn)
                from .reader_files import copy_artifacts
                for folder in ('calls', 'workfiles'):
                    if (kilde/folder).is_dir():
                        copy_artifacts(kilde/folder, maal/folder, include_sources=med_kilder)
        json_kjoringer.append({"kjoring": kj, "dokument": {k: dok[k] for k in ("id", "navn", "sha256", "antall_sider", "lesbarhet")},
                               'source_metadata':metadata(dok), 'source_units':dok['sider'],
                               "gjeldende_forsok": gjeld, "vurderinger": vurd, "kontroller": [lager.kontroller(f["id"]) for f in forsok]})
        if med_kilder:
            kildemappe = mappe / "kilder"
            kildemappe.mkdir(exist_ok=True)
            kopi = Path(dok["lagret_kopi"])
            if kopi.is_file():
                shutil.copy2(kopi, kildemappe / f"{dok['id']}_{dok['navn']}")
            else:
                raise ValueError(f'Missing preserved source: {dok["id"]}. Export without source copies or restore the source.')

    felter = ["kjoring_id", "dokument_id", "dokument", "sha256", "planversjon", "status", "forsok_id", "antall_forsok", "motor", "simulert",
              "modell", "modell_onsket", "tenkenivaa_onsket", "language", "api_endpoint", "api_provider_valg", "maks_output_tokens",
              "sesjon_id", "lesedekning", "kontrollert_av_totalt"]
    for kid in alle_kriterier:
        felter += [f"{kid}_svar", f"{kid}_kontroll", f"{kid}_validering"]
    felter.append("merknad")
    _skriv_csv(mappe / "resultater.csv", resultatrader, felter)
    _skriv_csv(mappe / "belegg.csv", beleggrader, ["kjoring_id", "forsok_id", "dokument", "kriterium", "svar", "fysisk_side", "sitat",
                                                   "kilde", "sitat_funnet_paa_side", 'source_format', 'source_unit', 'source_location'])
    _skriv_csv(mappe / "forsok.csv", forsokrader, ["id", "kjoring_id", "nr", "status", "startet", "avsluttet", "motor", "simulert",
                                                   "modell_onsket", "modell_rapportert", "tenkenivaa_onsket", "language", "api_endpoint", "api_provider_valg",
                                                   "maks_output_tokens", "sesjon_id", "input_hash", "feil"])
    _skriv_csv(mappe / "kontroll.csv", kontrollrader, ["id", "forsok_id", "tid", "ansvarlig", "handling", "kriterium_id", "begrunnelse",
                                                       "opprinnelig", "nytt"])
    (mappe / "resultater.json").write_text(json.dumps({
        "app_versjon": VERSJON, "eksportert": datetime.now().astimezone().isoformat(timespec="seconds"), "analyse": analyse,
        "prosjekt": prosjekt, "planversjoner": [{k: v[k] for k in ("id", "versjon", "status", "opprettet", "godkjent_av", "godkjent",
                                                                  "endringsnotat", "oppgavetekst")} | {"plan": v["plan"].til_dict()} for v in versjoner],
        "kjoringer": json_kjoringer, 'model_calls': model_calls,
        'run_warnings': call_warnings(model_calls),
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    # plan.md
    plantekst = [f"# Arbeidsplan for analyse {analyse_id}: {analyse['navn']}", ""]
    for v in versjoner:
        p = v["plan"]
        plantekst += [f"## Planversjon {v['versjon']} ({v['status']})", "",
                      f"- Opprettet: {v['opprettet']}", f"- Godkjent: {v.get('godkjent') or 'nei'}" + (f" av {v['godkjent_av']}" if v.get("godkjent_av") else ""),
                      f"- Endringsnotat: {v.get('endringsnotat') or ''}", f"- Motor: {p.motor}" + (f" (modell {p.modell})" if p.modell else ""),
                      f"- Språk / language: {p.sprak}", f"- Motorinnstillinger: {json.dumps(p.motorinnstillinger, ensure_ascii=False)}",
                      f"- Kriteriesett: {p.kriteriesett_navn} {p.kriteriesett_versjon}. {p.kriteriesett_merknad}", "",
                      "### Oppgavetekst (bestillingen)", "", v["oppgavetekst"], "", "### Kriterier", "",
                      "| ID | Navn | Spørsmål | Tillatte svar | Belegg kreves ved | Regel |", "|---|---|---|---|---|---|"]
        for k in p.kriterier:
            plantekst.append(f"| {k.id} | {k.navn} | {k.sporsmal} | {', '.join(k.tillatte_svar)} | {', '.join(k.krever_belegg_ved)} | {k.regel} |")
        plantekst += ["", "### Fastlagt instruks (sendes uendret til motoren for hvert forsøk)", "", "```", bygg_systeminstruks(p), "```", ""]
    (mappe / "plan.md").write_text("\n".join(plantekst), encoding="utf-8")

    # LESMEG.md
    merking = ("**Alle resultater i denne pakken er SIMULERTE** (ingen modell er brukt). De viser flyten, ikke faglig kvalitet."
               if simulert_finnes and not ekte_finnes else
               "Pakken inneholder både simulerte og ekte modellresultater; se kolonnen «simulert» i resultater.csv." if simulert_finnes and ekte_finnes else
               "Resultatene kommer fra ekte modellkjøringer (kolonnen «simulert» = nei)." if ekte_finnes else "Ingen forsøk er gjennomført.")
    lesmeg = [
        f"# Resultatpakke: {analyse['navn']} ({analyse_id})", "",
        f"Eksportert {datetime.now().strftime('%d.%m.%Y %H:%M')} med Systematic Document Analysis {VERSJON}. Prosjekt: {prosjekt['navn']} ({prosjekt['id']}).", "",
        merking, "",
        "## Hva pakken inneholder", "",
        "- `resultater.csv`: én rad per kjøring (dokument). Kolonner per kriterium: gjeldende svar, kontrollstatus og valideringsutfall. "
        "Skilletegn «;», UTF-8 med BOM (åpnes direkte i Excel).",
        "- `belegg.csv`: ett sitat per rad med kildeplassering og kildeenhet (fra 1) og om sitatet ble funnet på siden i bevart kopi.",
        "- `forsok.csv`: alle forsøk, også mislykkede og avbrutte. `kontroll.csv`: alle godkjenninger, rettelser og avvisninger.",
        "- `plan.md`: bestilling, kriterier og den fastlagte instruksen per planversjon. `resultater.json`: alt strukturert.",
        "- `forsok/<forsøk-ID>/`: nøyaktig input som ble sendt (input.json), manifest med motor, modell, sesjon og forbruk, og råsvar.",
        "- `kilder/`: kopier av dokumentene" + ("." if med_kilder else " (ikke tatt med; velg «med kilder» ved eksport)."), "",
        "## Omfang og status", "",
        f"- Kjøringer: {len(kjoringer)}. Status: " + ", ".join(f"{k}: {v}" for k, v in sorted(teller.items())) + ".",
        f"- Kontrollerte vurderinger: {kontrollert_totalt} av {vurderinger_totalt}. Alle KI-svar starter som «ikke kontrollert»; "
        "bare vurderinger merket «godkjent» eller «rettet» er kontrollert av et menneske.",
        f"- Planversjoner brukt: {', '.join(sorted(planversjoner_brukt))}" + (" (blandede versjoner, se kolonnen planversjon)." if len(planversjoner_brukt) > 1 else "."),
        f"- Motorer brukt: {', '.join(sorted(motorer)) or 'ingen'}." + (" Merk: flere motorer kan påvirke sammenlignbarheten." if len(motorer) > 1 else ""), "",
        "## Slik leser du resultatene", "",
        "- Status «stoppet_uleselig» betyr at dokumentet manglet tekstlag; det er ikke vurdert og ikke «ikke omtalt».",
        "- Status «valideringsfeil» betyr at motoren svarte, men svaret brøt reglene (ugyldig svar, manglende eller feil belegg). Slike svar kan ikke godkjennes uendret.",
        "- Status «feilet»/«uavklart»/«stoppet» har en synlig feilpost i kolonnen merknad og ingen faglig verdi.",
        "- PDF bruker fysiske sider fra 1. Andre formater bruker avsnitt, poster, linjer eller ark/celleområder; se source_location. Uttrekksomfang og strukturer er lagret i resultater.json.",
        "- Appens lagrede resultater er autoritative. Endringer i denne eksporten føres ikke tilbake.", "",
    ]
    (mappe / "LESMEG.md").write_text("\n".join(lesmeg), encoding="utf-8")
    from .english_export import write_english_export
    write_english_export(mappe, analyse, versjoner, alle_kriterier)
    if destination is None:
        lager.logg("eksportert", analyse_id=analyse_id, mappe=str(mappe), med_kilder=med_kilder)
    return {"mappe": str(mappe), "filer": sorted(p.name for p in mappe.iterdir()), "antall_kjoringer": len(kjoringer),
            "kontrollert_av_totalt": f"{kontrollert_totalt}/{vurderinger_totalt}", "simulert": simulert_finnes, "ekte": ekte_finnes, "teller": teller}


def eksporter(lager: Lager, analyse_id: str, *, med_kilder: bool = True,
              include_csv: bool = False, legacy_format: bool = False) -> dict[str, Any]:
    """Publish a complete, unique snapshot; never overwrite an edited workbook."""
    from .project_files import root_for, plan_text, write_index
    from .workbook_export import write_workbook
    analysis = lager.analyse(analyse_id)
    if any(r['status'] == 'aktiv' for r in lager.kjoringer(analyse_id)):
        raise ValueError('Wait for active runs to finish before exporting a consistent snapshot.')
    root = root_for(lager, analysis['prosjekt_id'])
    exports = root/'exports'
    exports.mkdir(exist_ok=True)
    versions = lager.planversjoner(analyse_id)
    language = versions[-1]['plan'].sprak
    nb = language == 'nb'
    documentation = 'Dokumentasjon' if nb else 'Documentation'
    source_folder = 'Kilder' if nb else 'Sources'
    entry = 'START_HER.md' if nb else 'START_HERE.md'
    final = exports/f'{analyse_id}-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}'
    if legacy_format:
        with tempfile.TemporaryDirectory(prefix='.building-', dir=exports) as temporary:
            stage = Path(temporary)
            result = _legacy_export(lager, analyse_id, med_kilder=med_kilder, destination=stage)
            stage.rename(final)
        result.update(mappe=str(final), project_directory=str(root), entrypoint=str(final/'LESMEG.md'))
        lager.logg('eksportert', analyse_id=analyse_id, mappe=str(final), legacy_format=True)
        write_index(lager, analysis['prosjekt_id'])
        return result
    # Failed writes leave no apparently successful export and preserve old snapshots.
    with tempfile.TemporaryDirectory(prefix='.building-', dir=exports) as temporary:
        stage = Path(temporary)
        result = _legacy_export(lager, analyse_id, med_kilder=med_kilder, destination=stage)
        docdir = stage/documentation
        docdir.mkdir()
        data = json.loads((stage/'resultater.json').read_text(encoding='utf-8'))
        def rows(name):
            with (stage/name).open(encoding='utf-8-sig', newline='') as f:
                return list(csv.DictReader(f, delimiter=';'))
        attempts, reviews = rows('forsok.csv'), rows('kontroll.csv')
        (stage/'resultater.json').rename(docdir/'analyse.json')
        (stage/'forsok').rename(docdir/'modellkall')
        if (stage/'kilder').exists():
            (stage/'kilder').rename(stage/source_folder)
        workbook, notices = write_workbook(stage, analysis, versions, data['kjoringer'], attempts,
                                           reviews, language, med_kilder, documentation, calls=data['model_calls'])
        (stage/'plan.md').unlink()
        (stage/'Plan.md').write_text(plan_text(analysis, versions, language), encoding='utf-8')
        csv_names = ['resultater','belegg','forsok','kontroll'] if nb else ['results','evidence','attempts','reviews']
        if include_csv:
            (stage/'CSV').mkdir()
            for name in csv_names:
                (stage/f'{name}.csv').rename(stage/'CSV'/f'{name}.csv')
        # Only known generated duplicates in this private staging directory are removed.
        for name in ['resultater.csv','belegg.csv','forsok.csv','kontroll.csv','results.csv','evidence.csv',
                     'attempts.csv','reviews.csv','LESMEG.md','README.md','plan.md','plan-summary.md']:
            path = stage/name
            # Windows is case-insensitive: preserve the newly written Plan.md.
            if name != 'plan.md' and path.exists():
                path.unlink()
        mode = ('SIMULERT' if nb else 'SIMULATED') if result['simulert'] and not result['ekte'] else (
            ('Blandet: simulert og ekte' if nb else 'Mixed: simulated and real') if result['simulert'] else
            ('Ekte modellkall' if nb else 'Real model calls') if result['ekte'] else ('Ikke startet' if nb else 'Not started'))
        lines = [f'# {analysis["navn"]}', '',
                 f'**{mode}**', '',
                 f'- [{"Åpne arbeidsboken" if nb else "Open workbook"}]({workbook})',
                 '- [Plan](Plan.md)',
                 f'- [{"Fullstendig kontrollspor" if nb else "Full audit data"}]({documentation}/analyse.json)', '',
                 f'{"Status" if nb else "Status"}: {json.dumps(result["teller"], ensure_ascii=False)}',
                 f'{"Menneskelig kontroll" if nb else "Human review"}: {result["kontrollert_av_totalt"]}', '',
                 ('Arbeidsboken har fire ark: Oversikt, Resultater med sitater og kildeplasseringer, Kjøringer med kontrollhistorikk, og Modellkall.' if nb else
                  'The workbook has four sheets: Overview, Results with quotations and source locations, Runs with review history, and Model calls.'), '',
                 ('Sitater og kildeplasseringer står i samme rekkefølge, atskilt med blanklinjer. Kjøringer viser én rad per forsøk og kontrollhendelse; gjentatt forsøks-ID betyr ikke en ny kjøring.' if nb else
                  'Quotes and source locations appear in matching order, separated by blank lines. Runs has one row per attempt and review event; a repeated attempt ID is not a new run.'), '',
                 (f'Tekniske advarsler: {len(data["run_warnings"])}. Se Modellkall; advarsler stopper ikke køen.' if nb else
                  f'Technical warnings: {len(data["run_warnings"])}. See Model calls; warnings do not stop the queue.'), '',
                 ('Modellkall viser registrerte leseforsøk, også simulerte eller mislykkede. Manglende telemetri er ikke bevis på utført leverandørkall. Tokenbruk er ikke en faktura.' if nb else
                  'Model calls lists recorded reader attempts, including simulated or failed ones. Missing telemetry is not evidence of provider execution. Token usage is not an invoice.'), '',
                 ('Automatisk validering er ikke menneskelig kontroll. Endringer i Excel føres ikke tilbake til pluginen.' if nb else
                  'Automatic validation is not human review. Excel edits do not write back to the plugin.'), '',
                 ('Blandede versjoner kan påvirke sammenlignbarheten; se Planversjon i arbeidsboken.' if nb else
                  'Mixed plan versions may affect comparability; see Plan version in the workbook.'), '',
                 f'{documentation}/modellkall/: '+('eksakt input, instruks, råsvar og metadata per forsøk og delkall.' if nb else
                  'exact input, instructions, raw replies and metadata per attempt and call.'), '',
                 (f'{source_folder}/: '+('bevarte kilder.' if nb else 'preserved sources.')) if med_kilder else
                 ('Kildekopier er ikke inkludert.' if nb else 'Source copies are not included.'), '',
                 ('Hele mappen kan flyttes samlet; lenkene er relative. Hver eksport er et eget øyeblikksbilde.' if nb else
                  'Move the whole folder together; links are relative. Each export is a separate snapshot.')]
        if notices:
            lines += ['', ('Noe tekst overskrider Excels begrensninger; full tekst er lenket fra cellene: ' if nb else
                           'Some text exceeds Excel limits; cells link to the full text: ') + ', '.join(notices)]
        (stage/entry).write_text('\n'.join(lines)+'\n', encoding='utf-8')
        stage.rename(final)
    result.update(mappe=str(final), filer=sorted(p.name for p in final.iterdir()),
                  workbook=str(final/workbook), entrypoint=str(final/entry), project_directory=str(root))
    lager.logg('eksportert', analyse_id=analyse_id, mappe=str(final), med_kilder=med_kilder,
               include_csv=include_csv, legacy_format=False)
    write_index(lager, analysis['prosjekt_id'])
    return result
