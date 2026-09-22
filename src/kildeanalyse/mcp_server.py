"""Felles MCP-server for ChatGPT desktop/Codex og Claude Code.

Verktøyene returnerer lesbar tekst. Kjørekomponenten håndhever reglene; vertsappene
kan ikke skrive direkte til lagringen gjennom disse verktøyene.
"""
from __future__ import annotations

import json
import sys
import anyio
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.stdio import stdio_server

from . import VERSJON, tjeneste, visning
from .konfig import datamappe
from .lager import Lager, LagerFeil
from .tjeneste import TjenesteFeil
from .maintenance import maintenance_lock, update_pending, request_drain, draining
from .stdio_input import PipeInput


class UpdatingMCPServer(MCPServer):
    """Finish active tool calls and workers before closing the plugin connection."""
    active_calls = 0

    async def call_tool(self, name, arguments, context=None):
        if draining() or update_pending():
            request_drain()
            raise ToolError('Plugin update in progress. Start a new conversation after installation finishes.')
        self.active_calls += 1
        try:
            return await super().call_tool(name, arguments, context)
        finally:
            self.active_calls -= 1

    async def run_stdio_async(self):
        # Also protect direct `python -m ...` launches, not only start_server.py.
        with maintenance_lock(shared=True):
            async with anyio.create_task_group() as group:
                async def watch_update():
                    while True:
                        if update_pending():
                            request_drain()
                        if draining() and not self.active_calls and not any(
                                worker.is_alive() for worker in list(tjeneste._traader.values())):
                            print('[Systematic Document Analysis] Connection closed for update. '
                                  'Start a new conversation after installation.', file=sys.stderr, flush=True)
                            group.cancel_scope.cancel()
                            return
                        await anyio.sleep(0.2)
                group.start_soon(watch_update)
                try:
                    async with stdio_server(stdin=PipeInput()) as (reader, writer):
                        await self._lowlevel_server.run(reader, writer,
                            self._lowlevel_server.create_initialization_options())
                finally:
                    group.cancel_scope.cancel()


server = UpdatingMCPServer(
    name="systematic-document-analysis",
    version=VERSJON,
    instructions=(
        "Systematic Document Analysis: auditable reading, one document per run. Respond in the user's language. "
        "Check shared startup prerequisites: service/tools, sign-in, specified criteria, source selection, reader/settings and plan approval. "
        "Missing prerequisites block startup; follow workflow_block in show_status. "
        "During execution, record individual problems and let other runs finish: unreadable/changed sources, timeouts, call/quota errors, "
        "invalid answers/evidence and uncertain attempts are follow-up items, not reasons to stop the whole queue. "
        "Do not call stop_runs for an individual failure. Failed chunks block only their dependent document synthesis. "
        "Report progress and summarize failures after other runs finish; preserve raw evidence, never invent completion or retry automatically. "
        "Permitted uncertainty answers are valid findings. Human review is required before claiming reviewed results. "
        "CLI sign-in is a hard stop: if the selected reader is unavailable, auth_gate is blocked, "
        "or CLI_AUTH_REQUIRED is reported, do not dispatch new dependent calls and explain recovery. A generic CLI error is not proof of missing sign-in. "
        "Never substitute host analysis, subagents, an alternative script, API calls, simulation or replacement result files. "
        "Criteria, extraction checks and plan preparation may continue. Recheck show_setup after user login; "
        "resume only after verification and a user request to continue. A different reader requires an explicitly approved new plan. "
        "A short ordinary-language request is enough to begin: restate the goal, inspect the specified files, "
        "propose criteria and routine settings, and ask only for missing details that materially change the analysis. "
        "Reuse answers already given. Distinguish user requirements, your proposals and unresolved assumptions. "
        "Do not silently choose the research question, infer negative findings from missing evidence, or force uncertain evidence into yes/no. "
        "Report skipped/failed imports and resolve relevant scope gaps. Use explicit document/run IDs for subsets. "
        "Present a concise plain-language plan with file scope, criteria, uncertainty rules, output location, reader/settings/recipient "
        "and material limitations, with links to the detailed plan and input preview. Actual approval of that concrete plan and scope "
        "is required before reader execution; never invent the responsible person's name. Offer an optional pilot for exploratory criteria. "
        "Prefer the English tools: show_setup → create_project → import_documents → create_analysis → show_plan "
        "→ add_runs → show_input_package → approve_plan → start_runs → show_status → show_run → record_review → export_results. "
        "Choose a visible project directory with create_project(directory=...) or set_project_directory; show the returned path. "
        "Plans and input previews are saved there before execution. Export XLSX snapshots there after execution; CSV is optional. "
        "Choose language en or nb explicitly in the plan. Use the user's own documents; simulation is optional. "
        "Never translate source quotes or answer labels. Explain legacy diagnostics/status codes in the user's language. "
        "Norwegian tool names remain available for compatibility."
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
def opprett_prosjekt(navn: str, mappe: str | None = None) -> str:
    try:
        p = tjeneste.opprett_prosjekt(_lager(), navn, mappe)
        return f"Prosjekt {p['id']} «{p['navn']}» er opprettet i {p['directory']}. Start med START_HERE.md. Importer dokumenter med importer_dokumenter."
    except (TjenesteFeil, LagerFeil, ValueError) as e:
        return _feil(e)


@server.tool(description='Velg ny eller tom prosjektmappe for planer, input og eksport. Eksisterende analysedata og gamle eksporter beholdes på opprinnelig sted.')
def sett_prosjektmappe(prosjekt_id: str, mappe: str) -> str:
    try:
        return json.dumps(tjeneste.set_project_directory(_lager(), prosjekt_id, mappe), ensure_ascii=False)
    except (TjenesteFeil, LagerFeil, ValueError, OSError) as e:
        return _feil(e)


@server.tool(description="Importer PDF, DOCX, XLSX, CSV/TSV, TXT eller Markdown (eller støttede filer i en mappe) til et prosjekt. Kopien bevares, innholdet trekkes ut med kildeplasseringer, og lesbarhet rapporteres.")
def importer_dokumenter(prosjekt_id: str, stier: list[str], ocr_mode: str = 'auto', ocr_languages: str = 'eng+nor') -> str:
    try:
        return visning.md_import(tjeneste.importer_dokumenter(_lager(), prosjekt_id, stier, ocr_mode=ocr_mode, ocr_languages=ocr_languages))
    except (TjenesteFeil, LagerFeil, ValueError) as e:
        return _feil(e)


@server.tool(description=(
    "Opprett en analyse med planversjon 1 (utkast). kriteriefil er en sti til en JSON-fil med «kriterier» "
    "(id, navn, spørsmål, tillatte_svar, krever_belegg_ved, regel). motor: «simulert» (ingen modellkall), «claude_cli» "
    "(Claude-abonnement), «codex_cli» (ChatGPT-innlogging), eller API: «openai_api», «azure_foundry_api», «anthropic_api»,  "
    "«openrouter_api», «kompatibel_api». API krever eksplisitt modell-ID og lokal nøkkel; separat betaling. "
    "API-innstillinger: maks_output_tokens, tidsavbrudd_sek; kompatibel_api krever base_url; OpenRouter har valgfri provider. Azure Foundry: base_url (resource endpoint), modell=deployment name, api_format=responses/chat_completions/anthropic_messages. "
    "API-tenkenivå standard utelater effort; øvrige nivåer avhenger av modellen. Aldri send nøkkelverdier til verktøyet. Velg motor eksplisitt. "
    "CLI-modell: tomt gir sonnet for Claude og gpt-5.6-terra for Codex. "
    "CLI-tenkenivaa: low, medium, high, xhigh, max (og ultra for Codex); CLI-standard high. Støtte avhenger av valgt modell. "
    "Bruk prosjektets dokumenter og kriterier. Hjelp brukeren å formulere kriterier i JSON fra bestillingen."
))
def opprett_analyse(prosjekt_id: str, navn: str, oppgavetekst: str, kriteriefil: str, formaal: str = "", motor: str = "",
                    modell: str = "", tilleggsinstruks: str = "", tillat_sider_uten_tekst: bool = False,
                    motorinnstillinger_json: str = "", tenkenivaa: str = "", sprak: str = "nb") -> str:
    try:
        r = tjeneste.opprett_analyse(_lager(), prosjekt_id, navn, oppgavetekst, kriteriefil, formaal=formaal, motor=motor, modell=modell,
                                     tilleggsinstruks=tilleggsinstruks, tillat_sider_uten_tekst=tillat_sider_uten_tekst,
                                     motorinnstillinger=_json_arg(motorinnstillinger_json, "motorinnstillinger_json") or None,
                                     tenkenivaa=tenkenivaa or None, sprak=sprak)
        return (f"Analyse {r['analyse']['id']} «{r['analyse']['navn']}» er opprettet med planversjon {r['planversjon']['versjon']} (utkast). "
                "Se planen med vis_plan, kontroller en inputpakke med vis_inputpakke, og godkjenn med godkjenn_plan.")
    except (TjenesteFeil, LagerFeil, ValueError) as e:
        return _feil(e)


@server.tool(description="Vis arbeidsplanen: bestilling, kriterier, motor, modell, tenkenivå, planversjoner og kjøringsoversikt.")
def vis_plan(analyse_id: str) -> str:
    try:
        return visning.md_plan(tjeneste.vis_plan(_lager(), analyse_id))
    except (TjenesteFeil, LagerFeil, ValueError) as e:
        return _feil(e)


@server.tool(description="Vis nøyaktig hva som sendes til motoren for én kjøring: fastlagt instruks, innhold per kildeenhet og svarskjema.")
def vis_inputpakke(kjoring_id: str) -> str:
    try:
        return visning.md_inputpakke(tjeneste.vis_inputpakke(_lager(), kjoring_id))
    except (TjenesteFeil, LagerFeil, ValueError) as e:
        return _feil(e)


@server.tool(description="Godkjenn siste planversjon med status utkast bare etter brukerens faktiske godkjenning av den viste planen og dokumentutvalget. Krever navn på ansvarlig; ikke utled navnet fra konto eller mappe. Kan ikke gjøres mens køen kjører.")
def godkjenn_plan(analyse_id: str, ansvarlig: str) -> str:
    try:
        v = tjeneste.godkjenn_plan(_lager(), analyse_id, ansvarlig)
        return f"Planversjon {v['versjon']} for analyse {analyse_id} er godkjent av {v['godkjent_av']} ({v['godkjent']}). Legg til kjøringer med legg_til_kjoringer."
    except (TjenesteFeil, LagerFeil, ValueError) as e:
        return _feil(e)


@server.tool(description=(
    "Lag en ny planversjon (utkast) fra gjeldende plan med angitte endringer og et endringsnotat. Startede kjøringer beholder gammel versjon; "
    "nye kjøringer må legges til for den nye versjonen etter godkjenning. Bruk dette når instruks, kriterier, motor, modell eller tenkenivaa skal endres. "
    "motorinnstillinger_json endrer bare angitte felt, for eksempel tidsavbrudd_sek."
))
def ny_planversjon(analyse_id: str, endringsnotat: str, oppgavetekst: str = "", formaal: str = "", kriteriefil: str = "", motor: str = "",
                   modell: str = "", tilleggsinstruks: str = "", tillat_sider_uten_tekst: str = "",
                   tenkenivaa: str = "", motorinnstillinger_json: str = "", sprak: str = "") -> str:
    try:
        r = tjeneste.ny_planversjon(
            _lager(), analyse_id, endringsnotat, oppgavetekst=oppgavetekst or None, formaal=formaal or None, kriteriefil=kriteriefil or None,
            motor=motor or None, modell=modell or None, tilleggsinstruks=tilleggsinstruks or None,
            tenkenivaa=tenkenivaa or None, sprak=sprak or None,
            motorinnstillinger=_json_arg(motorinnstillinger_json, "motorinnstillinger_json") or None,
            tillat_sider_uten_tekst=None if tillat_sider_uten_tekst == "" else tillat_sider_uten_tekst.lower() in ("ja", "true", "1"),
        )
        v = r["planversjon"]
        tekst = f"Planversjon {v['versjon']} (utkast) er opprettet for analyse {analyse_id}. Godkjenn med godkjenn_plan og legg til kjøringer for den."
        if r["aktive_kjoringer_paa_forrige"]:
            tekst += f" Aktive kjøringer på forrige versjon fortsetter uendret: {', '.join(r['aktive_kjoringer_paa_forrige'])}."
        return tekst
    except (TjenesteFeil, LagerFeil, ValueError) as e:
        return _feil(e)


@server.tool(description="Legg til kjøringer (én per dokument) for gjeldende planversjon. Uten dokument_ider tas alle dokumenter i prosjektet.")
def legg_til_kjoringer(analyse_id: str, dokument_ider: list[str] | None = None) -> str:
    try:
        r = tjeneste.legg_til_kjoringer(_lager(), analyse_id, dokument_ider)
        return (f"Planversjon {r['planversjon_id']}: {len(r['nye'])} nye kjøringer ({', '.join(k['id'] for k in r['nye']) or 'ingen'})."
                + (f" Fantes allerede for dokument: {', '.join(r['finnes_allerede'])}." if r["finnes_allerede"] else ""))
    except (TjenesteFeil, LagerFeil, ValueError) as e:
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
    except (TjenesteFeil, LagerFeil, ValueError) as e:
        return _feil(e)


@server.tool(description="Be om stopp: ingen nye motorkall startes, og aktivt forsøk avbrytes. Lover ikke at leverandørens behandling stopper.")
def stopp(analyse_id: str) -> str:
    try:
        r = tjeneste.stopp(_lager(), analyse_id)
        return (f"Stopp er forespurt for analyse {analyse_id}. Aktiv arbeider: {r['aktiv_arbeider'] or 'ingen'}. "
                f"Aktive forsøk som avbrytes: {', '.join(r['aktive_forsok']) or 'ingen'}. Fullførte resultater beholdes.")
    except (TjenesteFeil, LagerFeil, ValueError) as e:
        return _feil(e)


@server.tool(description="Gjenoppta etter stopp eller avbrudd: uavklarte forsøk fra døde arbeidere merkes, fullførte kjøringer hoppes over, resten startes i bakgrunnen.")
def gjenoppta(analyse_id: str) -> str:
    try:
        r = tjeneste.gjenoppta(_lager(), analyse_id, i_bakgrunnen=True)
        return (f"Gjenopptatt i bakgrunnen. Uavklarte forsøk merket: {', '.join(r.get('ryddet_uavklart') or []) or 'ingen'}. "
                "Kjøringer med status «uavklart» sendes ikke på nytt automatisk; bruk nytt_forsok for dem. Følg med via vis_status.")
    except (TjenesteFeil, LagerFeil, ValueError) as e:
        return _feil(e)


@server.tool(description="Vis status for alle kjøringer i en analyse: status, forsøk, motor, kontrollstatus, feil og siste hendelser.")
def vis_status(analyse_id: str) -> str:
    try:
        return visning.md_status(tjeneste.vis_status(_lager(), analyse_id))
    except (TjenesteFeil, LagerFeil, ValueError) as e:
        return _feil(e)


@server.tool(description="Vis én kjøring i detalj: alle forsøk, svar per kriterium med belegg (fysisk side og sitat), validering, kontrollhistorikk og forbruk.")
def vis_kjoring(kjoring_id: str) -> str:
    try:
        return visning.md_kjoring(tjeneste.vis_kjoring(_lager(), kjoring_id))
    except (TjenesteFeil, LagerFeil, ValueError) as e:
        return _feil(e)


@server.tool(description="Bestill nytt forsøk for en kjøring (feilet, uavklart, stoppet eller med valideringsfeil). Krever begrunnelse. Gammelt forsøk beholdes; ny godkjenning kreves.")
def nytt_forsok(kjoring_id: str, begrunnelse: str) -> str:
    try:
        return tjeneste.nytt_forsok(_lager(), kjoring_id, begrunnelse)["melding"]
    except (TjenesteFeil, LagerFeil, ValueError) as e:
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
    except (TjenesteFeil, LagerFeil, ValueError) as e:
        return _feil(e)


@server.tool(description="Eksporter et nytt øyeblikksbilde i prosjektmappen: Excel med fem ark, én plan/startfil, kilder og komplett kontrollspor. med_csv gir ekstra tabeller; gammelt_format gir tidligere tospråklig CSV-eksport. Excel-endringer registreres ikke som menneskelig kontroll.")
def eksporter(analyse_id: str, med_kilder: bool = True, med_csv: bool = False, gammelt_format: bool = False) -> str:
    try:
        return visning.md_eksport(tjeneste.eksporter(_lager(), analyse_id, med_kilder, include_csv=med_csv, legacy_format=gammelt_format))
    except (TjenesteFeil, LagerFeil, ValueError) as e:
        return _feil(e)


from .english_tools import register

@server.tool(description='Undersøk uttrekk og kildeenheter før planlegging. Lag eventuelt en komplett Markdown-lesekopi. Diskuter filutfordringer, prioriteringer og avgrensning med brukeren.')
def inspiser_kilde(dokument_id: str, enheter: list[int] | None = None, maks_enheter: int = 10, lag_markdown: bool = False) -> str:
    try:
        return json.dumps(tjeneste.inspect_source(_lager(), dokument_id, enheter, maks_enheter, lag_markdown), ensure_ascii=False, indent=2)
    except Exception as exc:
        return _feil(exc)

register(server, _lager)


def main() -> None:
    # stdio-transport: stdout er reservert for protokollen; all logging går til stderr.
    print(f"kildeanalyse MCP-server {VERSJON} starter (datamappe {datamappe()})", file=sys.stderr, flush=True)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
