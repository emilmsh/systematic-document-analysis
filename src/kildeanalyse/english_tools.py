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

    @server.tool(description='Create a draft repeatable per-file task. Without criteria_file, request is the task instruction unless task_instructions expands it. Default result is readable Markdown; optional output_schema describes result inside the execution envelope. Inline closed JSON objects need all properties required. Optional quote_checks: [{path: JSON Pointer to an array in result, quote_field: field name, unit_field: field name}] checks exact source substrings. No task-type profile or workbook is required. criteria_file is the mutually exclusive legacy classification option. language=en/nb. Explicit engine: codex_cli, claude_cli, openai_api, azure_foundry_api, anthropic_api, openrouter_api, kompatibel_api; simulert only on request. APIs require model and local credentials, with separate billing; never pass keys in settings. Azure also needs base_url and api_format. Large files use task-aware map-reduce by default.')
    def create_analysis(project_id: str, name: str, request: str, criteria_file: str | None = None,
                        engine: str = '', model: str = '', language: str = 'en', reasoning_effort: str = '',
                        engine_settings: dict | None = None, purpose: str = '',
                        additional_instructions: str = '', allow_pages_without_text: bool = False,
                        task_instructions: str | None = None, output_schema: dict | None = None,
                        quote_checks: list[dict] | None = None) -> str:
        return call(tjeneste.opprett_analyse, project_id, name, request, criteria_file, motor=engine,
                    modell=model, sprak=language, tenkenivaa=reasoning_effort or None, motorinnstillinger=engine_settings,
                    formaal=purpose, tilleggsinstruks=additional_instructions, tillat_sider_uten_tekst=allow_pages_without_text,
                    task_instructions=task_instructions, output_schema=output_schema, quote_checks=quote_checks)

    @server.tool(description='Show plan versions, task/result contract, language, reader settings and runs. Summarize the task, selected files/exclusions, expected deliverable and checks, reader/recipient and material limits before approval; link the saved plan and input preview.')
    def show_plan(analysis_id: str) -> str:
        return call(tjeneste.vis_plan, analysis_id)

    @server.tool(description='Show the exact input package for a run, including instructions, text, wire-format schema, API request and hash. Never translate schema keys or quotes.')
    def show_input_package(run_id: str) -> str:
        return call(tjeneste.vis_inputpakke, run_id)

    @server.tool(description='Approve a draft plan only after actual user approval of the displayed concrete plan and file scope. A vague request to analyse or decide is not approval of unseen criteria. Requires the responsible person’s name; never infer it from an account or folder. Reuse valid approval already given. Does not approve model answers.')
    def approve_plan(analysis_id: str, approved_by: str, plan_version_id: str | None = None) -> str:
        return call(tjeneste.godkjenn_plan, analysis_id, approved_by, plan_version_id)

    @server.tool(description='Create a draft plan version, preserving earlier attempts. Change task_instructions, output_schema or quote_checks as needed. reset_output_schema=true returns to Markdown; quote_checks=[] clears quote checks. criteria_file switches to legacy classification. Language/reader changes are versioned too; changing engines resets engine-specific settings. Never supply keys.')
    def new_plan_version(analysis_id: str, change_note: str, request: str | None = None,
                         criteria_file: str | None = None, engine: str | None = None, model: str | None = None,
                         language: str | None = None, reasoning_effort: str | None = None,
                         engine_settings: dict | None = None, purpose: str | None = None,
                         additional_instructions: str | None = None, allow_pages_without_text: bool | None = None,
                         task_instructions: str | None = None, output_schema: dict | None = None,
                         quote_checks: list[dict] | None = None, reset_output_schema: bool = False) -> str:
        return call(tjeneste.ny_planversjon, analysis_id, change_note, oppgavetekst=request,
                    kriteriefil=criteria_file, motor=engine, modell=model, sprak=language,
                    tenkenivaa=reasoning_effort, motorinnstillinger=engine_settings, formaal=purpose,
                    tilleggsinstruks=additional_instructions, tillat_sider_uten_tekst=allow_pages_without_text,
                    task_instructions=task_instructions, output_schema=output_schema, quote_checks=quote_checks,
                    reset_output_schema=reset_output_schema)

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

    @server.tool(description='Show compact progress, errors, non-blocking run_warnings and review status. details=true includes full source and attempt data; use show_run for per-call evidence. Warnings do not stop the queue. If workflow_block is present, report the pause, reason and corrective next step. Translate diagnostics without changing recorded values.')
    def show_status(analysis_id: str, details: bool = False) -> str:
        return call(tjeneste.vis_status, analysis_id, details=details)

    @server.tool(description='Inspect a run: actual task result and response, original raw answers, attempts, validation scope, model calls, usage and human reviews. User-defined result keys are preserved. Legacy plans expose assessments.')
    def show_run(run_id: str) -> str:
        return call(tjeneste.vis_kjoring, run_id)

    @server.tool(description='Request a new attempt with a reason, retaining the old attempt. Requires subsequent user approval.')
    def retry_run(run_id: str, reason: str) -> str:
        return call(tjeneste.nytt_forsok, run_id, reason)

    @server.tool(description='Record actual human review: approved, corrected or rejected. For general tasks review the whole result; corrections require replacement_response containing result, source_units_read and limitations. The replacement is validated and the original retained. Legacy corrections use criterion_id, new_answer and new_evidence [{page: source_unit_id, quote: text}]. Never invent human review.')
    def record_review(attempt_id: str, reviewer: str, action: str, reason: str,
                      criterion_id: str | None = None, new_answer: str | None = None,
                      new_evidence: list[dict] | None = None, replacement_response: dict | None = None) -> str:
        actions = {'approved':'godkjent', 'corrected':'rettet', 'rejected':'avvist'}
        if action not in actions:
            return json.dumps({'error':'Choose approved, corrected or rejected.'})
        evidence = None if new_evidence is None else [{'side':b.get('page'), 'sitat':b.get('quote')} for b in new_evidence]
        return call(tjeneste.registrer_kontroll, attempt_id, reviewer, actions[action], reason,
                    kriterium_id=criterion_id, nytt_svar=new_answer, nytt_belegg=evidence,
                    replacement_response=replacement_response)

    @server.tool(description='Export a portable snapshot in the project directory. General tasks: actual results as Markdown and original-shape JSON per file, plan, optional sources and full audit/attempt history. Returns entrypoint and results_directory; no imposed workbook columns. The host may derive a suitable presentation with run/attempt provenance. Criteria plans retain Excel export; include_csv and legacy_format apply only there. Export edits neither write back nor count as human review.')
    def export_results(analysis_id: str, include_sources: bool = True, include_csv: bool = False, legacy_format: bool = False) -> str:
        return call(tjeneste.eksporter, analysis_id, include_sources, include_csv=include_csv, legacy_format=legacy_format)
