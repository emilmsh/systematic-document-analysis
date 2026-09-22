"""Kommandolinje for test og drift uten Claude Code: python -m kildeanalyse <kommando> ...

Bruker samme tjenestelag og lagring som MCP-serveren. Kjør `python -m kildeanalyse -h`.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import VERSJON, tjeneste, visning
from .konfig import datamappe
from .lager import Lager, LagerFeil
from .tjeneste import TjenesteFeil


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="kildeanalyse", description=f"Systematic Document Analysis {VERSJON}")
    sub = p.add_subparsers(dest="kommando", required=True)
    sub.add_parser("oppsett", help="vis oppsett og motorstatus")
    s = sub.add_parser("prosjekt", help="opprett prosjekt"); s.add_argument("navn"); s.add_argument("--mappe")
    s = sub.add_parser("prosjektmappe", help="velg synlig prosjektmappe"); s.add_argument("prosjekt_id"); s.add_argument("mappe")
    s = sub.add_parser("importer", help="importer støttede filer eller mapper"); s.add_argument("prosjekt_id"); s.add_argument("stier", nargs="+")
    s = sub.add_parser("analyse", help="opprett analyse med planversjon 1")
    for a in ("prosjekt_id", "navn", "oppgavetekst"):
        s.add_argument(a)
    s.add_argument('kriteriefil', nargs='?', help='Valgfri eldre kriteriefil; uten denne brukes oppgaven direkte.')
    s.add_argument('--task-instructions', default=None)
    s.add_argument('--output-schema', help='JSON Schema as JSON text, describing result only.')
    s.add_argument('--quote-checks', help='Optional exact quote checks as a JSON list.')
    s.add_argument("--formaal", default=""); s.add_argument("--motor", required=True); s.add_argument("--modell", default="")
    s.add_argument("--tenkenivaa", default=None, help="low, medium, high, xhigh, max; også ultra for Codex")
    s.add_argument("--tilleggsinstruks", default=""); s.add_argument("--tillat-sider-uten-tekst", action="store_true")
    s.add_argument("--motorinnstillinger", default="", help="JSON")
    s = sub.add_parser("plan", help="vis plan"); s.add_argument("analyse_id")
    s = sub.add_parser("inputpakke", help="vis inputpakke for kjøring"); s.add_argument("kjoring_id")
    s = sub.add_parser("godkjenn", help="godkjenn plan"); s.add_argument("analyse_id"); s.add_argument("ansvarlig")
    s = sub.add_parser("kjoringer", help="legg til kjøringer"); s.add_argument("analyse_id"); s.add_argument("--dokumenter", nargs="*")
    s = sub.add_parser("start", help="start køen (i forgrunnen)"); s.add_argument("analyse_id"); s.add_argument("--kjoringer", nargs="*"); s.add_argument("--maks", type=int)
    s = sub.add_parser("stopp", help="be om stopp"); s.add_argument("analyse_id")
    s = sub.add_parser("gjenoppta", help="gjenoppta etter avbrudd"); s.add_argument("analyse_id")
    s = sub.add_parser("status", help="vis status"); s.add_argument("analyse_id")
    s = sub.add_parser("kjoring", help="vis kjøring"); s.add_argument("kjoring_id")
    s = sub.add_parser("nytt-forsok", help="bestill nytt forsøk"); s.add_argument("kjoring_id"); s.add_argument("begrunnelse")
    s = sub.add_parser("kontroll", help="registrer kontroll"); s.add_argument("forsok_id"); s.add_argument("ansvarlig"); s.add_argument("handling")
    s.add_argument("begrunnelse"); s.add_argument("--kriterium"); s.add_argument("--nytt-svar"); s.add_argument("--nytt-belegg", help="JSON-liste")
    s = sub.add_parser("eksporter", help="eksporter resultatpakke"); s.add_argument("analyse_id")
    s.add_argument("--med-kilder", action=argparse.BooleanOptionalAction, default=True)
    s.add_argument("--med-csv", action="store_true"); s.add_argument("--gammelt-format", action="store_true")
    args = p.parse_args(argv)
    lager = Lager(datamappe())
    try:
        ut = _utfor(lager, args)
    except (TjenesteFeil, LagerFeil) as e:
        print(f"Feil: {e}", file=sys.stderr)
        return 1
    print(ut)
    return 0


def _utfor(lager: Lager, a: argparse.Namespace) -> str:
    k = a.kommando
    if k == "oppsett":
        return visning.md_oppsett(tjeneste.oppsett(lager))
    if k == "prosjekt":
        pr = tjeneste.opprett_prosjekt(lager, a.navn, a.mappe)
        return f"Prosjekt {pr['id']} «{pr['navn']}» opprettet i {pr['directory']}."
    if k == "prosjektmappe":
        return json.dumps(tjeneste.set_project_directory(lager, a.prosjekt_id, a.mappe), ensure_ascii=False)
    if k == "importer":
        return visning.md_import(tjeneste.importer_dokumenter(lager, a.prosjekt_id, a.stier))
    if k == "analyse":
        r = tjeneste.opprett_analyse(lager, a.prosjekt_id, a.navn, a.oppgavetekst, a.kriteriefil, formaal=a.formaal, motor=a.motor,
                                     modell=a.modell, tilleggsinstruks=a.tilleggsinstruks, tillat_sider_uten_tekst=a.tillat_sider_uten_tekst,
                                     motorinnstillinger=json.loads(a.motorinnstillinger) if a.motorinnstillinger else None,
                                     tenkenivaa=a.tenkenivaa, task_instructions=a.task_instructions,
                                     output_schema=json.loads(a.output_schema) if a.output_schema else None,
                                     quote_checks=json.loads(a.quote_checks) if a.quote_checks else None)
        return f"Analyse {r['analyse']['id']} opprettet med planversjon {r['planversjon']['id']} (utkast)."
    if k == "plan":
        return visning.md_plan(tjeneste.vis_plan(lager, a.analyse_id))
    if k == "inputpakke":
        return visning.md_inputpakke(tjeneste.vis_inputpakke(lager, a.kjoring_id))
    if k == "godkjenn":
        v = tjeneste.godkjenn_plan(lager, a.analyse_id, a.ansvarlig)
        return f"Planversjon {v['id']} godkjent av {v['godkjent_av']}."
    if k == "kjoringer":
        r = tjeneste.legg_til_kjoringer(lager, a.analyse_id, a.dokumenter)
        return f"{len(r['nye'])} nye kjøringer: {', '.join(x['id'] for x in r['nye'])}. Fantes: {r['finnes_allerede']}"
    if k == "start":
        return visning.md_startrapport(tjeneste.start(lager, a.analyse_id, a.kjoringer, a.maks))
    if k == "stopp":
        return json.dumps(tjeneste.stopp(lager, a.analyse_id), ensure_ascii=False)
    if k == "gjenoppta":
        return visning.md_startrapport(tjeneste.gjenoppta(lager, a.analyse_id))
    if k == "status":
        return visning.md_status(tjeneste.vis_status(lager, a.analyse_id))
    if k == "kjoring":
        return visning.md_kjoring(tjeneste.vis_kjoring(lager, a.kjoring_id))
    if k == "nytt-forsok":
        return tjeneste.nytt_forsok(lager, a.kjoring_id, a.begrunnelse)["melding"]
    if k == "kontroll":
        r = tjeneste.registrer_kontroll(lager, a.forsok_id, a.ansvarlig, a.handling, a.begrunnelse, kriterium_id=a.kriterium,
                                        nytt_svar=a.nytt_svar, nytt_belegg=json.loads(a.nytt_belegg) if a.nytt_belegg else None)
        return f"Kontroll {r['kontroll']['id']} registrert."
    if k == "eksporter":
        return visning.md_eksport(tjeneste.eksporter(lager, a.analyse_id, a.med_kilder, include_csv=a.med_csv, legacy_format=a.gammelt_format))
    raise TjenesteFeil(f"Ukjent kommando {k}")


if __name__ == "__main__":
    sys.exit(main())
