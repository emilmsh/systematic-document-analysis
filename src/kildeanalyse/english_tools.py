"""English MCP interface shared by both hosts. Legacy tools remain available."""
import json
from . import tjeneste
from .languages import public_result


def register(server, get_store):
    def settings(value):
        if value is None:
            return None
        aliases = {'max_output_tokens':'maks_output_tokens', 'timeout_seconds':'tidsavbrudd_sek', 'reasoning_effort':'tenkenivaa'}
        result = {}
        for key, item in value.items():
            name = aliases.get(key, key)
            if name in result:
                raise ValueError('Conflicting English and Norwegian engine settings.')
            result[name] = item
        return result

    def call(fn, *args, **kwargs):
        try:
            if 'motorinnstillinger' in kwargs:
                kwargs['motorinnstillinger'] = settings(kwargs['motorinnstillinger'])
            result = fn(get_store(), *args, **kwargs)
            return json.dumps(public_result(result), ensure_ascii=False, indent=2, default=str)
        except Exception as exc:
            return json.dumps({'error': 'Operation failed; explain the details in the user’s language.',
                               'details': str(exc)}, ensure_ascii=False)

    @server.tool(description='Show local configuration, projects and available reading engines. CLI readers require auth_gate.status=verified before classification. A blocked or unavailable reader is a hard stop: explain recovery, never substitute host analysis or subagents. API key checks are local only. Explain diagnostics in the user’s language.')
    def show_setup() -> str:
        return call(tjeneste.oppsett)

    @server.tool(description='Create a project with a visible working directory. Choose an absolute new or empty directory with the user; otherwise a unique folder under Documents/Systematic Document Analysis is used. Plans, input previews and exports go here, never in the plugin installation. Returns the directory.')
    def create_project(name: str, directory: str | None = None) -> str:
        return call(tjeneste.opprett_prosjekt, name, directory)

    @server.tool(description='Choose a new or empty visible directory for an existing project. Original data and earlier exports remain untouched. New plans, previews and exports use this directory; old exports are not moved.')
    def set_project_directory(project_id: str, directory: str) -> str:
        return call(tjeneste.set_project_directory, project_id, directory)

    @server.tool(description='Import local PDF, DOCX, XLSX, CSV/TSV, TXT or Markdown files, or folders of supported files. Subfolders are not imported automatically. Inspect results and skipped entries; report failures, exclusions, extraction scope and structural differences and resolve relevant gaps before agreeing the plan.')
    def import_documents(project_id: str, paths: list[str], ocr_mode: str = 'auto', ocr_languages: str = 'eng+nor') -> str:
        return call(tjeneste.importer_dokumenter, project_id, paths, ocr_mode=ocr_mode, ocr_languages=ocr_languages)

    @server.tool(description='Inspect extracted source units and format/OCR limitations before agreeing the plan. Optionally save a complete Markdown inspection copy with stable source locators. Discuss expected file challenges, relevant sections, priorities and uncertain answers with the user. The preview is limited; no original is changed.')
    def inspect_source(document_id: str, unit_ids: list[int] | None = None, maximum_units: int = 10, export_markdown: bool = False) -> str:
        return call(tjeneste.inspect_source, document_id, unit_ids, maximum_units, export_markdown)

    @server.tool(description='Create a draft analysis. language=en or nb controls reader commentary; quotes and answer labels remain verbatim. criteria_file accepts English or Norwegian fields. Explicit engine: codex_cli, claude_cli, openai_api, azure_foundry_api, anthropic_api, openrouter_api, kompatibel_api; simulert only on request. API requires model ID and local key, with separate billing. Never pass keys in settings. API settings: max_output_tokens, timeout_seconds, base_url for compatible API, provider for OpenRouter. Azure Foundry requires base_url (resource endpoint), deployment name as model and explicit api_format: responses, chat_completions or anthropic_messages. Reasoning effort standard omits API effort; other levels depend on model.')
    def create_analysis(project_id: str, name: str, request: str, criteria_file: str,
                        engine: str, model: str = '', language: str = 'en', reasoning_effort: str = '',
                        engine_settings: dict | None = None, purpose: str = '',
                        additional_instructions: str = '', allow_pages_without_text: bool = False) -> str:
        return call(tjeneste.opprett_analyse, project_id, name, request, criteria_file, motor=engine,
                    modell=model, sprak=language, tenkenivaa=reasoning_effort or None, motorinnstillinger=engine_settings,
                    formaal=purpose, tilleggsinstruks=additional_instructions, tillat_sider_uten_tekst=allow_pages_without_text)

    @server.tool(description='Show all plan versions, language, model, effort, engine settings and runs. Summarize the goal, selected files/exclusions, criteria, uncertainty handling, reader/settings/recipient, output and material limits in ordinary language before approval; link the detailed plan and input preview.')
    def show_plan(analysis_id: str) -> str:
        return call(tjeneste.vis_plan, analysis_id)

    @server.tool(description='Show the exact input package for a run, including instructions, text, wire-format schema, API request and hash. Never translate schema keys or quotes.')
    def show_input_package(run_id: str) -> str:
        return call(tjeneste.vis_inputpakke, run_id)

    @server.tool(description='Approve a draft plan only after actual user approval of the displayed concrete plan and file scope. A vague request to analyse or decide is not approval of unseen criteria. Requires the responsible person’s name; never infer it from an account or folder. Reuse valid approval already given. Does not approve model answers.')
    def approve_plan(analysis_id: str, approved_by: str, plan_version_id: str | None = None) -> str:
        return call(tjeneste.godkjenn_plan, analysis_id, approved_by, plan_version_id)

    @server.tool(description='Create a new draft plan version, preserving earlier attempts. Language changes require a new version too. Changing engines resets engine-specific settings. Keys must never be supplied.')
    def new_plan_version(analysis_id: str, change_note: str, request: str | None = None,
                         criteria_file: str | None = None, engine: str | None = None, model: str | None = None,
                         language: str | None = None, reasoning_effort: str | None = None,
                         engine_settings: dict | None = None, purpose: str | None = None,
                         additional_instructions: str | None = None, allow_pages_without_text: bool | None = None) -> str:
        return call(tjeneste.ny_planversjon, analysis_id, change_note, oppgavetekst=request,
                    kriteriefil=criteria_file, motor=engine, modell=model, sprak=language,
                    tenkenivaa=reasoning_effort, motorinnstillinger=engine_settings, formaal=purpose,
                    tilleggsinstruks=additional_instructions, tillat_sider_uten_tekst=allow_pages_without_text)

    @server.tool(description='Add one planned run per selected document. Omitting document_ids selects ALL project documents, including earlier imports: use explicit IDs for an agreed subset or pilot. This makes no model calls.')
    def add_runs(analysis_id: str, document_ids: list[str] | None = None) -> str:
        return call(tjeneste.legg_til_kjoringer, analysis_id, document_ids)

    @server.tool(description='Start planned runs for an approved plan in the background, only within the approved scope. Missing tools, sign-in or specifications block startup. Individual run errors are reported while other runs finish. Omitting run_ids selects all eligible runs; use IDs for a subset. Follow show_status; explain workflow_block and report run_issues without stopping for individual failures. Never emulate blocked work with host analysis, subagents or another engine.')
    def start_runs(analysis_id: str, run_ids: list[str] | None = None, maximum: int | None = None) -> str:
        return call(tjeneste.start_i_bakgrunnen, analysis_id, run_ids, maximum)

    @server.tool(description='Stop the queue and request cancellation of the active attempt. Provider processing and billing may continue.')
    def stop_runs(analysis_id: str) -> str:
        return call(tjeneste.stopp, analysis_id)

    @server.tool(description='Resume eligible work on an explicit user request, after rechecking shared prerequisites. Completed, failed and uncertain runs are skipped; individual issues do not block other runs. Retrying a failed or uncertain run requires a separate explicit request.')
    def resume_runs(analysis_id: str) -> str:
        return call(tjeneste.gjenoppta, analysis_id, i_bakgrunnen=True)

    @server.tool(description='Show progress, errors and review status. If workflow_block is present, clearly report the pause, its reason, existing results and corrective next step. Do not substitute another analysis. Translate technical status codes for the user without changing recorded values.')
    def show_status(analysis_id: str) -> str:
        return call(tjeneste.vis_status, analysis_id)

    @server.tool(description='Inspect a run: original answers, source quotes, source locations, attempts, validation, usage and human reviews.')
    def show_run(run_id: str) -> str:
        return call(tjeneste.vis_kjoring, run_id)

    @server.tool(description='Request a new attempt with a reason, retaining the old attempt. Requires subsequent user approval.')
    def retry_run(run_id: str, reason: str) -> str:
        return call(tjeneste.nytt_forsok, run_id, reason)

    @server.tool(description='Record an actual human review: approved, corrected or rejected. Never claim human review on the user’s behalf. Corrections require criterion_id, new_answer and evidence as [{page: source_unit_id, quote: text}] where required.')
    def record_review(attempt_id: str, reviewer: str, action: str, reason: str,
                      criterion_id: str | None = None, new_answer: str | None = None,
                      new_evidence: list[dict] | None = None) -> str:
        actions = {'approved':'godkjent', 'corrected':'rettet', 'rejected':'avvist'}
        if action not in actions:
            return json.dumps({'error':'Choose approved, corrected or rejected.'})
        evidence = None if new_evidence is None else [{'side':b.get('page'), 'sitat':b.get('quote')} for b in new_evidence]
        return call(tjeneste.registrer_kontroll, attempt_id, reviewer, actions[action], reason,
                    kriterium_id=criterion_id, nytt_svar=new_answer, nytt_belegg=evidence)

    @server.tool(description='Export a new snapshot in the visible project directory: one XLSX workbook (overview, results, evidence, review and runs), one plan and start file in the plan language, optional source copies and full JSON/raw audit history under Documentation. include_csv adds tables in one language. legacy_format requests the old bilingual CSV layout. Returns entrypoint and workbook paths. Excel edits do not write back or count as human review.')
    def export_results(analysis_id: str, include_sources: bool = True, include_csv: bool = False, legacy_format: bool = False) -> str:
        return call(tjeneste.eksporter, analysis_id, include_sources, include_csv=include_csv, legacy_format=legacy_format)
