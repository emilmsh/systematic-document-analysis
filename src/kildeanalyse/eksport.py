"""Resultatpakke: CSV-filer, lesbar oversikt, plan, manifester og valgfrie kildekopier.

Pakken skal kunne leses uten appen. Simulerte kjøringer merkes tydelig. Ingen hemmeligheter
skrives ut (miljøvariabler og tokens inngår ikke i manifestene).
"""
from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from . import VERSJON
from .konfig import undermappe
from .lager import FS_FULLFORT, FS_VALIDERINGSFEIL, KONTROLL_GODKJENT, KONTROLL_RETTET, Lager
from .prompt import bygg_systeminstruks
from .parametre import fra_plan


def _skriv_csv(sti: Path, rader: list[dict[str, Any]], felter: list[str]) -> None:
    with open(sti, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=felter, delimiter=";", extrasaction="ignore")
        w.writeheader()
        for r in rader:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})


def eksporter(lager: Lager, analyse_id: str, *, med_kilder: bool = False) -> dict[str, Any]:
    from .tjeneste import gjeldende_vurderinger

    analyse = lager.analyse(analyse_id)
    prosjekt = lager.prosjekt(analyse["prosjekt_id"])
    versjoner = lager.planversjoner(analyse_id)
    gjeldende = lager.gjeldende_planversjon(analyse_id)
    kjoringer = lager.kjoringer(analyse_id)
    stempel = datetime.now().strftime("%Y%m%d-%H%M%S")
    mappe = undermappe(f"eksport/{analyse_id}_{stempel}", lager.mappe)
    (mappe / "forsok").mkdir(exist_ok=True)

    alle_kriterier: list[str] = []
    for v in versjoner:
        for k in v["plan"].kriterier:
            if k.id not in alle_kriterier:
                alle_kriterier.append(k.id)

    resultatrader, beleggrader, forsokrader, kontrollrader, json_kjoringer = [], [], [], [], []
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
        api_felter = {'api_endpoint': api.get('endpoint', ''), 'api_provider_valg': api.get('provider', ''),
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
            vurd = gjeldende_vurderinger(lager, gjeld, planrad["plan"])
            validering = json.loads(gjeld["validering_json"]) if gjeld.get("validering_json") else {}
            ld = validering.get("lesedekning", {})
            rad["lesedekning"] = f"{len(ld.get('sider_lest_oppgitt', []))}/{len(ld.get('sider_i_dokument', []))} sider" + ("" if ld.get("fullstendig") else " (ufullstendig)")
            kontrollert = sum(1 for v in vurd.values() if v["kontrollstatus"] in (KONTROLL_GODKJENT, KONTROLL_RETTET))
            rad["kontrollert_av_totalt"] = f"{kontrollert}/{len(vurd)}"
            kontrollert_totalt += kontrollert
            vurderinger_totalt += len(vurd)
            for kid, v in vurd.items():
                rad[f"{kid}_svar"] = v["svar"]
                rad[f"{kid}_kontroll"] = v["kontrollstatus"] + (" (rettet)" if v["kilde"] == "rettet" and v["kontrollstatus"] != KONTROLL_RETTET else "")
                rad[f"{kid}_validering"] = "ok" if v["validering_gyldig"] else ("feil: " + " | ".join(v["valideringsfeil"]))
                sidetekst = {s["nr"]: s["tekst"] for s in dok["sider"]}
                from .dokument import sitat_finnes

                for b in v["belegg"]:
                    beleggrader.append({
                        "kjoring_id": kj["id"], "forsok_id": gjeld["id"], "dokument": dok["navn"], "kriterium": kid, "svar": v["svar"],
                        "fysisk_side": b.get("side"), "sitat": b.get("sitat"), "kilde": v["kilde"],
                        "sitat_funnet_paa_side": "ja" if b.get("side") in sidetekst and sitat_finnes(str(b.get("sitat", "")), sidetekst[b["side"]]) else "NEI",
                    })
        resultatrader.append(rad)
        for f in forsok:
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
                for navn in ("input.json", "manifest.json", "raasvar.txt", "systeminstruks.txt"):
                    if (kilde / navn).is_file():
                        shutil.copy2(kilde / navn, maal / navn)
        json_kjoringer.append({"kjoring": kj, "dokument": {k: dok[k] for k in ("id", "navn", "sha256", "antall_sider", "lesbarhet")},
                               "gjeldende_forsok": gjeld, "vurderinger": vurd, "kontroller": [lager.kontroller(f["id"]) for f in forsok]})
        if med_kilder:
            kildemappe = mappe / "kilder"
            kildemappe.mkdir(exist_ok=True)
            kopi = Path(dok["lagret_kopi"])
            if kopi.is_file():
                shutil.copy2(kopi, kildemappe / f"{dok['id']}_{dok['navn']}")

    felter = ["kjoring_id", "dokument_id", "dokument", "sha256", "planversjon", "status", "forsok_id", "antall_forsok", "motor", "simulert",
              "modell", "modell_onsket", "tenkenivaa_onsket", "api_endpoint", "api_provider_valg", "maks_output_tokens",
              "sesjon_id", "lesedekning", "kontrollert_av_totalt"]
    for kid in alle_kriterier:
        felter += [f"{kid}_svar", f"{kid}_kontroll", f"{kid}_validering"]
    felter.append("merknad")
    _skriv_csv(mappe / "resultater.csv", resultatrader, felter)
    _skriv_csv(mappe / "belegg.csv", beleggrader, ["kjoring_id", "forsok_id", "dokument", "kriterium", "svar", "fysisk_side", "sitat",
                                                   "kilde", "sitat_funnet_paa_side"])
    _skriv_csv(mappe / "forsok.csv", forsokrader, ["id", "kjoring_id", "nr", "status", "startet", "avsluttet", "motor", "simulert",
                                                   "modell_onsket", "modell_rapportert", "tenkenivaa_onsket", "api_endpoint", "api_provider_valg",
                                                   "maks_output_tokens", "sesjon_id", "input_hash", "feil"])
    _skriv_csv(mappe / "kontroll.csv", kontrollrader, ["id", "forsok_id", "tid", "ansvarlig", "handling", "kriterium_id", "begrunnelse",
                                                       "opprinnelig", "nytt"])
    (mappe / "resultater.json").write_text(json.dumps({
        "app_versjon": VERSJON, "eksportert": datetime.now().astimezone().isoformat(timespec="seconds"), "analyse": analyse,
        "prosjekt": prosjekt, "planversjoner": [{k: v[k] for k in ("id", "versjon", "status", "opprettet", "godkjent_av", "godkjent",
                                                                  "endringsnotat", "oppgavetekst")} | {"plan": v["plan"].til_dict()} for v in versjoner],
        "kjoringer": json_kjoringer,
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    # plan.md
    plantekst = [f"# Arbeidsplan for analyse {analyse_id}: {analyse['navn']}", ""]
    for v in versjoner:
        p = v["plan"]
        plantekst += [f"## Planversjon {v['versjon']} ({v['status']})", "",
                      f"- Opprettet: {v['opprettet']}", f"- Godkjent: {v.get('godkjent') or 'nei'}" + (f" av {v['godkjent_av']}" if v.get("godkjent_av") else ""),
                      f"- Endringsnotat: {v.get('endringsnotat') or ''}", f"- Motor: {p.motor}" + (f" (modell {p.modell})" if p.modell else ""),
                      f"- Motorinnstillinger: {json.dumps(p.motorinnstillinger, ensure_ascii=False)}",
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
        f"Eksportert {datetime.now().strftime('%d.%m.%Y %H:%M')} med OE Kildeanalyse {VERSJON}. Prosjekt: {prosjekt['navn']} ({prosjekt['id']}).", "",
        merking, "",
        "## Hva pakken inneholder", "",
        "- `resultater.csv`: én rad per kjøring (dokument). Kolonner per kriterium: gjeldende svar, kontrollstatus og valideringsutfall. "
        "Skilletegn «;», UTF-8 med BOM (åpnes direkte i Excel).",
        "- `belegg.csv`: ett sitat per rad med fysisk side (fra 1) og om sitatet ble funnet på siden i bevart kopi.",
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
        "- Fysisk side teller fra 1 i PDF-filen; trykte sidetall i dokumentet er ikke brukt.",
        "- Appens lagrede resultater er autoritative. Endringer i denne eksporten føres ikke tilbake.", "",
    ]
    (mappe / "LESMEG.md").write_text("\n".join(lesmeg), encoding="utf-8")
    lager.logg("eksportert", analyse_id=analyse_id, mappe=str(mappe), med_kilder=med_kilder)
    return {"mappe": str(mappe), "filer": sorted(p.name for p in mappe.iterdir()), "antall_kjoringer": len(kjoringer),
            "kontrollert_av_totalt": f"{kontrollert_totalt}/{vurderinger_totalt}", "simulert": simulert_finnes, "ekte": ekte_finnes, "teller": teller}
