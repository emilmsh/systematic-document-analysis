"""MCP-server for Claude Code-pluginen. Start: python -m kildeanalyse.mcp_server

Verktøyene returnerer lesbar tekst. Kjørekomponenten håndhever reglene; verten (Claude
Code) kan ikke skrive direkte til lagringen gjennom disse verktøyene.
"""
from __future__ import annotations

import json
import sys
from typing import Any

from mcp.server.mcpserver import MCPServer

from . import VERSJON, tjeneste, visning
from .konfig import datamappe
from .lager import Lager, LagerFeil
from .tjeneste import TjenesteFeil

server = MCPServer(
    name="kildeanalyse",
    version=VERSJON,
    instructions=(
        "OE Kildeanalyse: registrerte, etterprøvbare lesekjøringer (ett dokument per kjøring). "
        "Rekkefølge: vis_oppsett → opprett_prosjekt → importer_dokumenter → opprett_analyse → vis_plan "
        "→ legg_til_kjoringer → vis_inputpakke → godkjenn_plan → start_kjoringer → vis_status → vis_kjoring → registrer_kontroll → eksporter. "
        "Resultater fra motoren «simulert» er alltid merket SIMULERT."
    ),
)


def _lager() -> Lager:
    return Lager(datamappe())


def _feil(e: Exception) -> str:
    return f"Feil: {e}"


def _json_arg(verdi: Any, navn: str) -> Any:
    if isinstance(verdi, str) and verdi.strip():
        try:
            return json.loads(verdi)
        except json.JSONDecodeError as e:
            raise TjenesteFeil(f"Argumentet «{navn}» er ikke gyldig JSON: {e}") from e
    return verdi


@server.tool(description="Vis oppsett: datamappe, motorer med støttekontroll (innlogging, blokkeringer) og prosjekter. Start alltid her.")
def vis_oppsett() -> str:
    try:
        return visning.md_oppsett(tjeneste.oppsett(_lager()))
    except Exception as e:  # noqa: BLE001
        return _feil(e)


@server.tool(description="Opprett et prosjekt som kan inneholde dokumenter og analyser.")
def opprett_prosjekt(navn: str) -> str:
    try:
        p = tjeneste.opprett_prosjekt(_lager(), navn)
        return f"Prosjekt {p['id']} «{p['navn']}» er opprettet. Importer dokumenter med importer_dokumenter."
    except (TjenesteFeil, LagerFeil) as e:
        return _feil(e)


@server.tool(description="Importer PDF-filer (eller alle PDF-er i en mappe) til et prosjekt. Kopien bevares, teksten trekkes ut per fysisk side, og lesbarhet rapporteres.")
def importer_dokumenter(prosjekt_id: str, stier: list[str]) -> str:
    try:
        return visning.md_import(tjeneste.importer_dokumenter(_lager(), prosjekt_id, stier))
    except (TjenesteFeil, LagerFeil) as e:
        return _feil(e)


@server.tool(description=(
    "Opprett en analyse med planversjon 1 (utkast). kriteriefil er en sti til en JSON-fil med «kriterier» "
    "(id, navn, spørsmål, tillatte_svar, krever_belegg_ved, regel). motor: «simulert» (ingen modellkall), «claude_cli» "
    "(Claude-abonnement) eller «codex_cli» (ChatGPT-innlogging i Codex CLI). Velg motor eksplisitt. "
    "modell angir modellnavn/ID; tomt gir sonnet for Claude og gpt-5.6-terra for Codex. "
    "tenkenivaa: low, medium, high, xhigh, max (og ultra for Codex); standard high. Støtte avhenger av valgt modell. "
    "Bruk prosjektets dokumenter og kriterier. Hjelp brukeren å formulere kriterier i JSON fra bestillingen."
))
def opprett_analyse(prosjekt_id: str, navn: str, oppgavetekst: str, kriteriefil: str, formaal: str = "", motor: str = "",
                    modell: str = "", tilleggsinstruks: str = "", tillat_sider_uten_tekst: bool = False,
                    motorinnstillinger_json: str = "", tenkenivaa: str = "") -> str:
    try:
        r = tjeneste.opprett_analyse(_lager(), prosjekt_id, navn, oppgavetekst, kriteriefil, formaal=formaal, motor=motor, modell=modell,
                                     tilleggsinstruks=tilleggsinstruks, tillat_sider_uten_tekst=tillat_sider_uten_tekst,
                                     motorinnstillinger=_json_arg(motorinnstillinger_json, "motorinnstillinger_json") or None,
                                     tenkenivaa=tenkenivaa or None)
        return (f"Analyse {r['analyse']['id']} «{r['analyse']['navn']}» er opprettet med planversjon {r['planversjon']['versjon']} (utkast). "
                "Se planen med vis_plan, kontroller en inputpakke med vis_inputpakke, og godkjenn med godkjenn_plan.")
    except (TjenesteFeil, LagerFeil) as e:
        return _feil(e)


@server.tool(description="Vis arbeidsplanen: bestilling, kriterier, motor, modell, tenkenivå, planversjoner og kjøringsoversikt.")
def vis_plan(analyse_id: str) -> str:
    try:
        return visning.md_plan(tjeneste.vis_plan(_lager(), analyse_id))
    except (TjenesteFeil, LagerFeil) as e:
        return _feil(e)


@server.tool(description="Vis nøyaktig hva som sendes til motoren for én kjøring: fastlagt instruks, dokumenttekst per fysisk side og svarskjema.")
def vis_inputpakke(kjoring_id: str) -> str:
    try:
        return visning.md_inputpakke(tjeneste.vis_inputpakke(_lager(), kjoring_id))
    except (TjenesteFeil, LagerFeil) as e:
        return _feil(e)


@server.tool(description="Godkjenn siste planversjon med status utkast. Krever navn på ansvarlig. Kan ikke gjøres mens køen kjører.")
def godkjenn_plan(analyse_id: str, ansvarlig: str) -> str:
    try:
        v = tjeneste.godkjenn_plan(_lager(), analyse_id, ansvarlig)
        return f"Planversjon {v['versjon']} for analyse {analyse_id} er godkjent av {v['godkjent_av']} ({v['godkjent']}). Legg til kjøringer med legg_til_kjoringer."
    except (TjenesteFeil, LagerFeil) as e:
        return _feil(e)


@server.tool(description=(
    "Lag en ny planversjon (utkast) fra gjeldende plan med angitte endringer og et endringsnotat. Startede kjøringer beholder gammel versjon; "
    "nye kjøringer må legges til for den nye versjonen etter godkjenning. Bruk dette når instruks, kriterier, motor, modell eller tenkenivaa skal endres. "
    "motorinnstillinger_json endrer bare angitte felt, for eksempel tidsavbrudd_sek."
))
def ny_planversjon(analyse_id: str, endringsnotat: str, oppgavetekst: str = "", formaal: str = "", kriteriefil: str = "", motor: str = "",
                   modell: str = "", tilleggsinstruks: str = "", tillat_sider_uten_tekst: str = "",
                   tenkenivaa: str = "", motorinnstillinger_json: str = "") -> str:
    try:
        r = tjeneste.ny_planversjon(
            _lager(), analyse_id, endringsnotat, oppgavetekst=oppgavetekst or None, formaal=formaal or None, kriteriefil=kriteriefil or None,
            motor=motor or None, modell=modell or None, tilleggsinstruks=tilleggsinstruks or None,
            tenkenivaa=tenkenivaa or None,
            motorinnstillinger=_json_arg(motorinnstillinger_json, "motorinnstillinger_json") or None,
            tillat_sider_uten_tekst=None if tillat_sider_uten_tekst == "" else tillat_sider_uten_tekst.lower() in ("ja", "true", "1"),
        )
        v = r["planversjon"]
        tekst = f"Planversjon {v['versjon']} (utkast) er opprettet for analyse {analyse_id}. Godkjenn med godkjenn_plan og legg til kjøringer for den."
        if r["aktive_kjoringer_paa_forrige"]:
            tekst += f" Aktive kjøringer på forrige versjon fortsetter uendret: {', '.join(r['aktive_kjoringer_paa_forrige'])}."
        return tekst
    except (TjenesteFeil, LagerFeil) as e:
        return _feil(e)


@server.tool(description="Legg til kjøringer (én per dokument) for gjeldende planversjon. Uten dokument_ider tas alle dokumenter i prosjektet.")
def legg_til_kjoringer(analyse_id: str, dokument_ider: list[str] | None = None) -> str:
    try:
        r = tjeneste.legg_til_kjoringer(_lager(), analyse_id, dokument_ider)
        return (f"Planversjon {r['planversjon_id']}: {len(r['nye'])} nye kjøringer ({', '.join(k['id'] for k in r['nye']) or 'ingen'})."
                + (f" Fantes allerede for dokument: {', '.join(r['finnes_allerede'])}." if r["finnes_allerede"] else ""))
    except (TjenesteFeil, LagerFeil) as e:
        return _feil(e)


@server.tool(description=(
    "Start planlagte (og stoppede) kjøringer for godkjent plan, én om gangen, i bakgrunnen. Motorens støtte kontrolleres først; "
    "blokkeringer (for eksempel API-nøkkel satt eller manglende innlogging) stopper starten med forklaring. Følg med via vis_status. "
    "Bruk maks for å prøve et utvalg først."
))
def start_kjoringer(analyse_id: str, kjoring_ider: list[str] | None = None, maks: int | None = None) -> str:
    try:
        r = tjeneste.start_i_bakgrunnen(_lager(), analyse_id, kjoring_ider, maks)
        return (f"Køen for analyse {analyse_id} er startet i bakgrunnen med motor {r['motor']} ({visning._merk(r['simulert'])}). "
                + " ".join(r["meldinger"]) + " Bruk vis_status for fremdrift og stopp for å stanse.")
    except (TjenesteFeil, LagerFeil) as e:
        return _feil(e)


@server.tool(description="Be om stopp: ingen nye motorkall startes, og aktivt forsøk avbrytes. Lover ikke at leverandørens behandling stopper.")
def stopp(analyse_id: str) -> str:
    try:
        r = tjeneste.stopp(_lager(), analyse_id)
        return (f"Stopp er forespurt for analyse {analyse_id}. Aktiv arbeider: {r['aktiv_arbeider'] or 'ingen'}. "
                f"Aktive forsøk som avbrytes: {', '.join(r['aktive_forsok']) or 'ingen'}. Fullførte resultater beholdes.")
    except (TjenesteFeil, LagerFeil) as e:
        return _feil(e)


@server.tool(description="Gjenoppta etter stopp eller avbrudd: uavklarte forsøk fra døde arbeidere merkes, fullførte kjøringer hoppes over, resten startes i bakgrunnen.")
def gjenoppta(analyse_id: str) -> str:
    try:
        r = tjeneste.gjenoppta(_lager(), analyse_id, i_bakgrunnen=True)
        return (f"Gjenopptatt i bakgrunnen. Uavklarte forsøk merket: {', '.join(r.get('ryddet_uavklart') or []) or 'ingen'}. "
                "Kjøringer med status «uavklart» sendes ikke på nytt automatisk; bruk nytt_forsok for dem. Følg med via vis_status.")
    except (TjenesteFeil, LagerFeil) as e:
        return _feil(e)


@server.tool(description="Vis status for alle kjøringer i en analyse: status, forsøk, motor, kontrollstatus, feil og siste hendelser.")
def vis_status(analyse_id: str) -> str:
    try:
        return visning.md_status(tjeneste.vis_status(_lager(), analyse_id))
    except (TjenesteFeil, LagerFeil) as e:
        return _feil(e)


@server.tool(description="Vis én kjøring i detalj: alle forsøk, svar per kriterium med belegg (fysisk side og sitat), validering, kontrollhistorikk og forbruk.")
def vis_kjoring(kjoring_id: str) -> str:
    try:
        return visning.md_kjoring(tjeneste.vis_kjoring(_lager(), kjoring_id))
    except (TjenesteFeil, LagerFeil) as e:
        return _feil(e)


@server.tool(description="Bestill nytt forsøk for en kjøring (feilet, uavklart, stoppet eller med valideringsfeil). Krever begrunnelse. Gammelt forsøk beholdes; ny godkjenning kreves.")
def nytt_forsok(kjoring_id: str, begrunnelse: str) -> str:
    try:
        return tjeneste.nytt_forsok(_lager(), kjoring_id, begrunnelse)["melding"]
    except (TjenesteFeil, LagerFeil) as e:
        return _feil(e)


@server.tool(description=(
    "Registrer menneskelig kontroll på et forsøk: handling «godkjent», «rettet» eller «avvist», med ansvarlig og begrunnelse. "
    "«rettet» krever kriterium_id, nytt_svar og ved beleggkrav nytt_belegg_json som liste av {\"side\": n, \"sitat\": \"...\"}; "
    "sitatet må finnes på siden i bevart kopi. Uten kriterium_id gjelder godkjenning/avvisning hele forsøket. Originalsvaret bevares alltid."
))
def registrer_kontroll(forsok_id: str, ansvarlig: str, handling: str, begrunnelse: str, kriterium_id: str = "",
                       nytt_svar: str = "", nytt_belegg_json: str = "") -> str:
    try:
        r = tjeneste.registrer_kontroll(_lager(), forsok_id, ansvarlig, handling, begrunnelse, kriterium_id=kriterium_id or None,
                                        nytt_svar=nytt_svar or None, nytt_belegg=_json_arg(nytt_belegg_json, "nytt_belegg_json") or None)
        ko = r["kontroll"]
        linjer = [f"Kontroll {ko['id']} registrert: {ko['handling']} {ko['kriterium_id'] or '(hele forsøket)'} av {ko['ansvarlig']} {ko['tid']}.", ""]
        linjer += [f"- {kid}: {v['svar']} ({v['kilde']}, {v['kontrollstatus']})" for kid, v in r["vurderinger"].items()]
        return "\n".join(linjer)
    except (TjenesteFeil, LagerFeil) as e:
        return _feil(e)


@server.tool(description="Eksporter resultatpakke (CSV med «;», LESMEG.md, plan.md, resultater.json, manifester per forsøk, valgfritt kildekopier).")
def eksporter(analyse_id: str, med_kilder: bool = False) -> str:
    try:
        return visning.md_eksport(tjeneste.eksporter(_lager(), analyse_id, med_kilder))
    except (TjenesteFeil, LagerFeil) as e:
        return _feil(e)


def main() -> None:
    # stdio-transport: stdout er reservert for protokollen; all logging går til stderr.
    print(f"kildeanalyse MCP-server {VERSJON} starter (datamappe {datamappe()})", file=sys.stderr, flush=True)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
