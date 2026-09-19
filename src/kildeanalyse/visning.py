"""Lesbar tekst (Markdown) av tjenestesvarene. Brukes av MCP-verktøyene og kommandolinjen."""
from __future__ import annotations

import json
from typing import Any
from .parametre import fra_plan, MODELLER, TENKENIVAA, STANDARD_TENKENIVAA

SIMULERT_MERKE = "⚠ SIMULERT"


def _merk(simulert: bool | int | None) -> str:
    return SIMULERT_MERKE if simulert else "ekte"


def md_oppsett(d: dict[str, Any]) -> str:
    ut = [f"# OE Kildeanalyse {d['app_versjon']}", "", f"- Datamappe: `{d['datamappe']}`", f"- Database: `{d['database']}`",
          f"- Python {d['python']} på {d['plattform']}", f"- Plugin-rot: `{d.get('plugin_root') or 'ikke lastet som plugin'}`", "", "## Motorer", ""]
    for navn, m in d["motorer"].items():
        ut.append(f"### {navn} — {'klar' if m['ok'] else 'BLOKKERT'} ({_merk(m['simulert'])})")
        ut.append(m["beskrivelse"])
        if navn in MODELLER:
            ut.append(f"- Nye planer: modell `{MODELLER[navn]}`, tenkenivå `{STANDARD_TENKENIVAA}` hvis ikke annet velges.")
            ut.append(f"- Valgbare nivåer: {', '.join(TENKENIVAA[navn])}. Tilgjengelighet avhenger av modellen.")
        for melding in m["meldinger"]:
            ut.append(f"- {melding}")
        inn = m["egenskaper"].get("innlogging")
        if inn:
            ut.append("- Innlogging: " + " / ".join(str(inn[k]) for k in ('authMethod', 'apiProvider', 'subscriptionType', 'email', 'orgName') if inn.get(k)))
        if m["egenskaper"].get("cli_versjon"):
            ut.append(f"- CLI-versjon: {m['egenskaper']['cli_versjon']}")
        ut.append("")
    ut += ["## Prosjekter", ""]
    ut += [f"- {p['id']}: {p['navn']} (opprettet {p['opprettet']})" for p in d["prosjekter"]] or ["(ingen)"]
    return "\n".join(ut)


def md_import(d: dict[str, Any]) -> str:
    ut = [f"# Import til prosjekt {d['prosjekt_id']}", ""]
    for r in d["resultater"]:
        if "feil" in r:
            ut.append(f"- ✗ `{r['sti']}`: {r['feil']}")
            continue
        dok = r["dokument"]
        status = {"lesbar": "lesbar", "delvis": f"DELVIS lesbar, sider uten tekst: {r['sider_uten_tekst']}", "uleselig": "ULESELIG (ingen tekstlag)"}[dok["lesbarhet"]]
        ut.append(f"- {'✓' if r['nytt'] else '='} {dok['id']}: `{dok['navn']}` — {dok['antall_sider']} sider, {status}, SHA-256 {dok['sha256'][:12]}…"
                  + ("" if r["nytt"] else " (fantes allerede, samme innhold)"))
    return "\n".join(ut)


def md_plan(d: dict[str, Any]) -> str:
    a = d["analyse"]
    ut = [f"# Analyse {a['id']}: {a['navn']}", f"Prosjekt {d['prosjekt']['id']}: {d['prosjekt']['navn']}", ""]
    for v in d["versjoner"]:
        p = v["plan"]
        gj = " ← gjeldende" if d["gjeldende"] and v["id"] == d["gjeldende"]["id"] else ""
        ut += [f"## Planversjon {v['versjon']} — {v['status']}{gj}", "",
               f"- Opprettet {v['opprettet']}" + (f", godkjent {v['godkjent']} av {v['godkjent_av']}" if v.get("godkjent") else ", ikke godkjent"),
               f"- Endringsnotat: {v.get('endringsnotat') or ''}",
               f"- Motor: **{p.motor}** ({_merk(p.motor == 'simulert')})" + (f", modell {p.modell}" if p.modell else ""),
               f"- Tenkenivå: **{fra_plan(p)['tenkenivaa']}**. Tidsgrense per dokument: {fra_plan(p)['tidsavbrudd_sek']:g} sekunder.",
               f"- Analyseenhet: {p.analyseenhet}. Sider uten tekst: {'tillatt (lesedekning merkes)' if p.tillat_sider_uten_tekst else 'stopper kjøringen'}.",
               f"- Kriteriesett: {p.kriteriesett_navn} {p.kriteriesett_versjon}. {p.kriteriesett_merknad}", "",
               "**Bestilling (oppgavetekst):**", "", v["oppgavetekst"], "", f"**Formål:** {p.formaal}", "",
               "| ID | Navn | Spørsmål | Tillatte svar | Belegg kreves ved | Regel |", "|---|---|---|---|---|---|"]
        ut += [f"| {k.id} | {k.navn} | {k.sporsmal} | {', '.join(k.tillatte_svar)} | {', '.join(k.krever_belegg_ved)} | {k.regel} |" for k in p.kriterier]
        if p.tilleggsinstruks:
            ut += ["", f"**Tilleggsinstruks:** {p.tilleggsinstruks}"]
        ut.append("")
    kj = d["kjoringer"]
    ut += [f"## Kjøringer: {len(kj)}", ""]
    teller: dict[str, int] = {}
    for k in kj:
        teller[k["status"]] = teller.get(k["status"], 0) + 1
    ut.append(", ".join(f"{s}: {n}" for s, n in sorted(teller.items())) or "(ingen kjøringer lagt til ennå)")
    ut += ["", "Bruk `vis_inputpakke` for å se nøyaktig hva som sendes for én kjøring, og `godkjenn_plan` før start."]
    return "\n".join(ut)


def md_inputpakke(d: dict[str, Any]) -> str:
    p = d["pakke"]
    return "\n".join([
        f"# Inputpakke for kjøring {d['kjoring']['id']} ({d['kilde']})", "",
        f"- Dokument: {p['dokument_navn']} ({p['dokument_id']}, SHA-256 {p['dokument_sha256'][:12]}…), fysiske sider sendt: {p['sider_sendt']}",
        f"- Input-hash: `{p['input_hash']}`", "", "## Fastlagt instruks (systemrolle)", "", "```", p["systeminstruks"], "```", "",
        "## Kjøreparametre", "", "```json", json.dumps(p.get("kjoreparametre", {"merknad": "Eldre inputpakke: se forsøksmanifest."}), ensure_ascii=False, indent=2), "```", "",
        "## Brukermelding (dokumentet)", "", "```", p["brukermelding"][:6000] + ("\n… (avkortet i visningen; hele teksten er lagret)" if len(p["brukermelding"]) > 6000 else ""), "```", "",
        "## Svarskjema", "", "```json", json.dumps(p["svarskjema"], ensure_ascii=False, indent=1), "```",
    ])


def md_status(d: dict[str, Any]) -> str:
    a = d["analyse"]
    gp = d["gjeldende_plan"]
    ut = [f"# Status for analyse {a['id']}: {a['navn']}", ""]
    if gp:
        ut.append(f"Gjeldende planversjon {gp['versjon']} ({gp['status']}), motor **{gp['plan'].motor}** ({_merk(gp['plan'].motor == 'simulert')}).")
    aa = d["aktiv_arbeider"]
    ut.append(f"Arbeider: {'aktiv (pid ' + str(aa['pid']) + ', siden ' + aa['tid'] + ')' if aa else 'ingen aktiv'}."
              + (" Stopp er forespurt." if d["stopp_forespurt"] else "")
              + (" Bakgrunnstråd i denne prosessen er aktiv." if d["bakgrunnstraad_aktiv"] else ""))
    ut.append("Sammendrag: " + (", ".join(f"{s}: {n}" for s, n in sorted(d["teller"].items())) or "ingen kjøringer") + ".")
    ut += ["", "| Kjøring | Dokument | Status | Forsøk | Motor | Kontroll | Merknad/feil |", "|---|---|---|---|---|---|---|"]
    for r in d["rader"]:
        k, dok, f, ks = r["kjoring"], r["dokument"], r["siste_forsok"], r["kontrollstatus"]
        motor = f"{f['motor']} ({_merk(f['simulert'])})" if f else ""
        merknad = (k.get("merknad") or (f.get("feil") if f else "") or "")
        ut.append(f"| {k['id']} | {dok['navn']} | **{k['status']}** | {r['antall_forsok']}" + (f" ({f['id']})" if f else "") +
                  f" | {motor} | {ks['status'] + ' ' + str(ks['kontrollert']) + '/' + str(ks['totalt']) if ks and ks['totalt'] else ''} | {merknad[:140]} |")
    br = d.get("bakgrunnsresultat")
    if br and "feil" in br:
        ut += ["", f"Bakgrunnskjøringen feilet: {br['feil']}"]
    if d["hendelser"]:
        ut += ["", "Siste hendelser:"] + [f"- {h['tid']} {h['type']}" + (f" {json.dumps(h['detaljer'], ensure_ascii=False)[:120]}" if h["detaljer"] else "") for h in d["hendelser"][-8:]]
    return "\n".join(ut)


def md_kjoring(d: dict[str, Any]) -> str:
    k, dok, pv = d["kjoring"], d["dokument"], d["planversjon"]
    ut = [f"# Kjøring {k['id']} — {dok['navn']}", "",
          f"- Status: **{k['status']}**. Planversjon {pv['versjon']} ({pv['status']}). Dokument {dok['id']}, {dok['antall_sider']} sider, {dok['lesbarhet']}, SHA-256 {dok['sha256'][:12]}…",
          f"- Bevart kopi: `{dok['lagret_kopi']}`"]
    if k.get("merknad"):
        ut.append(f"- Merknad: {k['merknad']}")
    if not d["forsok"]:
        ut += ["", "Ingen forsøk er gjort."]
    for fd in d["forsok"]:
        f = fd["forsok"]
        gj = " (gjeldende)" if f["id"] == k.get("gjeldende_forsok_id") else ""
        ut += ["", f"## Forsøk {f['id']}{gj} — {f['status']} — {f['motor']} ({_merk(f['simulert'])})", "",
               f"- Startet {f['startet']}, avsluttet {f.get('avsluttet') or '–'}. Modell ønsket/rapportert: {f.get('modell_onsket') or '–'} / {f.get('modell_rapportert') or 'ukjent'}. Sesjon: {f.get('sesjon_id') or 'ukjent'}.",
               f"- Input: `{f['input_sti']}` (hash {f['input_hash'][:12]}…)"]
        if f.get("feil"):
            ut.append(f"- Feil: {f['feil']}")
        val = fd["validering"]
        if val:
            ld = val["lesedekning"]
            ut.append(f"- Validering: {'gyldig' if val['gyldig'] else 'FEIL'}. Lesedekning: sider lest {ld['sider_lest_oppgitt']} av {ld['sider_i_dokument']}"
                      + (" (fullstendig)" if ld["fullstendig"] else " (UFULLSTENDIG)"))
            for a in val.get("advarsler", []):
                ut.append(f"  - Advarsel: {a['melding']}")
        if fd["vurderinger"]:
            ut += ["", "| Kriterium | Svar | Kilde | Validering | Kontroll | Belegg (fysisk side: sitat) |", "|---|---|---|---|---|---|"]
            for kid, v in fd["vurderinger"].items():
                belegg = "<br>".join(f"s.{b.get('side')}: «{str(b.get('sitat', ''))[:160]}»" for b in v["belegg"]) or "–"
                valid = "ok" if v["validering_gyldig"] else ("FEIL: " + "; ".join(v["valideringsfeil"]))
                kontroll = v["kontrollstatus"] + (f" ({v['kontroll']['ansvarlig']}, {v['kontroll']['tid'][:16]})" if v["kontroll"] else "")
                ut.append(f"| {kid} {v['kriterium']} | **{v['svar']}** | {v['kilde']} | {valid} | {kontroll} | {belegg} |")
        if fd["kontroller"]:
            ut += ["", "Kontrollhistorikk:"]
            for ko in fd["kontroller"]:
                ut.append(f"- {ko['tid']} {ko['handling']} {ko['kriterium_id'] or '(hele forsøket)'} av {ko['ansvarlig']}: {ko['begrunnelse']}"
                          + (f" — opprinnelig {json.dumps(ko['opprinnelig'], ensure_ascii=False)[:200]} → nytt {json.dumps(ko['nytt'], ensure_ascii=False)[:200]}" if ko["handling"] == "rettet" else ""))
        m = fd.get("manifest") or {}
        forbruk = m.get("forbruk") or {}
        if forbruk:
            u = forbruk.get("usage") or {}
            ut.append(f"- Forbruk: {forbruk.get('merknad', '')} " + (f"input {u.get('input_tokens')} + cache {u.get('cache_read_input_tokens')}/{u.get('cache_creation_input_tokens')}, output {u.get('output_tokens')}; listepris USD {forbruk.get('total_cost_usd_listepris')}" if u else ""))
    return "\n".join(ut)


def md_startrapport(d: dict[str, Any]) -> str:
    ut = [f"# Kjøring av analyse {d['analyse_id']} — motor {d['motor']} ({_merk(d['simulert'])})", ""]
    if d.get("ryddet_uavklart"):
        ut.append(f"- Forsøk fra en død arbeider ble merket uavklart: {', '.join(d['ryddet_uavklart'])}")
    if d.get("hoppet_over_gammel_planversjon"):
        ut.append(f"- Hoppet over kjøringer på erstattet planversjon: {', '.join(d['hoppet_over_gammel_planversjon'])}")
    ut.append(f"- Startet {len(d['startet'])} kjøringer: " + (", ".join(f"{k} → {s}" for k, s in d["utfall"].items()) or "ingen"))
    if d.get("stoppet_foer"):
        ut.append(f"- Stoppet før: {', '.join(d['stoppet_foer'])}")
    return "\n".join(ut)


def md_eksport(d: dict[str, Any]) -> str:
    return "\n".join([f"# Eksport ferdig", "", f"- Mappe: `{d['mappe']}`", f"- Filer: {', '.join(d['filer'])}",
                      f"- Kjøringer: {d['antall_kjoringer']} ({', '.join(f'{k}: {v}' for k, v in sorted(d['teller'].items()))})",
                      f"- Kontrollerte vurderinger: {d['kontrollert_av_totalt']}",
                      f"- Innhold: {'SIMULERT' if d['simulert'] and not d['ekte'] else 'blandet simulert/ekte' if d['simulert'] else 'ekte'}",
                      "", "Åpne LESMEG.md i mappen for leseveiledning."])
