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

    @server.tool(description='Show local configuration, projects and available reading engines. API key checks are local only. Explain legacy diagnostic messages in the user’s language.')
    def show_setup() -> str:
        return call(tjeneste.oppsett)

    @server.tool(description='Create a project for documents and analyses.')
    def create_project(name: str) -> str:
        return call(tjeneste.opprett_prosjekt, name)

    @server.tool(description='Import local PDF, DOCX, XLSX, CSV/TSV, TXT or Markdown files, or folders of supported files. Subfolders are not imported automatically. Report extraction scope and structural differences before agreeing a shared plan.')
    def import_documents(project_id: str, paths: list[str]) -> str:
        return call(tjeneste.importer_dokumenter, project_id, paths)

    @server.tool(description='Create a draft analysis. language=en or nb controls reader commentary; quotes and answer labels remain verbatim. criteria_file accepts English or Norwegian fields. Explicit engine: codex_cli, claude_cli, openai_api, anthropic_api, openrouter_api, kompatibel_api; simulert only on request. API requires model ID and local key, with separate billing. Never pass keys in settings. API settings: max_output_tokens, timeout_seconds, base_url for compatible API, provider for OpenRouter. Reasoning effort standard omits API effort; other levels depend on model.')
    def create_analysis(project_id: str, name: str, request: str, criteria_file: str,
                        engine: str, model: str = '', language: str = 'en', reasoning_effort: str = '',
                        engine_settings: dict | None = None, purpose: str = '',
                        additional_instructions: str = '', allow_pages_without_text: bool = False) -> str:
        return call(tjeneste.opprett_analyse, project_id, name, request, criteria_file, motor=engine,
                    modell=model, sprak=language, tenkenivaa=reasoning_effort or None, motorinnstillinger=engine_settings,
                    formaal=purpose, tilleggsinstruks=additional_instructions, tillat_sider_uten_tekst=allow_pages_without_text)

    @server.tool(description='Show all plan versions, language, model, effort, engine settings and runs. Present the plan in the user’s language.')
    def show_plan(analysis_id: str) -> str:
        return call(tjeneste.vis_plan, analysis_id)

    @server.tool(description='Show the exact input package for a run, including instructions, text, wire-format schema, API request and hash. Never translate schema keys or quotes.')
    def show_input_package(run_id: str) -> str:
        return call(tjeneste.vis_inputpakke, run_id)

    @server.tool(description='Approve a draft plan only when the user requests it. Requires the responsible person’s name. Does not approve model answers.')
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

    @server.tool(description='Add one planned run per selected document, or all project documents. This makes no model calls.')
    def add_runs(analysis_id: str, document_ids: list[str] | None = None) -> str:
        return call(tjeneste.legg_til_kjoringer, analysis_id, document_ids)

    @server.tool(description='Start planned runs for an approved plan in the background. Follow show_status. A subset is optional; no automatic engine switching.')
    def start_runs(analysis_id: str, run_ids: list[str] | None = None, maximum: int | None = None) -> str:
        return call(tjeneste.start_i_bakgrunnen, analysis_id, run_ids, maximum)

    @server.tool(description='Stop the queue and request cancellation of the active attempt. Provider processing and billing may continue.')
    def stop_runs(analysis_id: str) -> str:
        return call(tjeneste.stopp, analysis_id)

    @server.tool(description='Resume stopped work. Completed runs are skipped; uncertain attempts are never retried automatically.')
    def resume_runs(analysis_id: str) -> str:
        return call(tjeneste.gjenoppta, analysis_id, i_bakgrunnen=True)

    @server.tool(description='Show progress, errors and review status. Translate technical status codes for the user without changing recorded values.')
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

    @server.tool(description='Export results, evidence, plan history and audit files. English CSV/README accompany legacy audit files. Quotes and answer labels remain in their recorded language.')
    def export_results(analysis_id: str, include_sources: bool = False) -> str:
        return call(tjeneste.eksporter, analysis_id, include_sources)
