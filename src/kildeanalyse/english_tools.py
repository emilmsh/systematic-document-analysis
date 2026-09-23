"""English MCP interface shared by both hosts. One public interface for both hosts."""
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

    @server.tool(description='Show projects, configured readers and reader availability.')
    def show_setup() -> str:
        return call(tjeneste.oppsett)

    @server.tool(description='Create a project in a new or empty visible directory; return its path.')
    def create_project(name: str, directory: str | None = None) -> str:
        return call(tjeneste.opprett_prosjekt, name, directory)

    @server.tool(description='Set the directory for future project outputs. Earlier exports stay in place.')
    def set_project_directory(project_id: str, directory: str) -> str:
        return call(tjeneste.set_project_directory, project_id, directory)

    @server.tool(description='Import PDF, DOCX, XLSX, CSV/TSV, TXT or Markdown files. Folders are non-recursive. Returns imports and exclusions.')
    def import_documents(project_id: str, paths: list[str], ocr_mode: str = 'auto', ocr_languages: str = 'eng+nor') -> str:
        return call(tjeneste.importer_dokumenter, project_id, paths, ocr_mode=ocr_mode, ocr_languages=ocr_languages)

    @server.tool(description='Inspect extracted units, source locations and extraction limits. Optionally save a Markdown reading copy.')
    def inspect_source(document_id: str, unit_ids: list[int] | None = None, maximum_units: int = 10, export_markdown: bool = False) -> str:
        return call(tjeneste.inspect_source, document_id, unit_ids, maximum_units, export_markdown)

    @server.tool(description='After actual visual inspection, record a PDF physical page with no substantive content as blank. This is a source-status check, not human review of analysis results. Image or scan pages remain blocked unless genuinely inspected and verified.')
    def verify_blank_pdf_page(document_id: str, physical_page: int, verified_by: str, visual_evidence: str) -> str:
        return call(tjeneste.verify_blank_pdf_page, document_id, physical_page, verified_by, visual_evidence)

    @server.tool(description='Draft one task for the selected files. request is the instruction unless task_instructions is supplied. output_schema describes result, with readable titles and definitions. quote_checks optionally checks exact text: [{path, quote_field, unit_field}]. Returns a dataset preview.')
    def create_analysis(project_id: str, name: str, request: str,
                        engine: str = '', model: str = '', language: str = 'en', reasoning_effort: str = '',
                        engine_settings: dict | None = None, purpose: str = '',
                        additional_instructions: str = '', allow_pages_without_text: bool = False,
                        task_instructions: str | None = None, output_schema: dict | None = None,
                        quote_checks: list[dict] | None = None) -> str:
        return call(tjeneste.opprett_analyse, project_id, name, request, motor=engine,
                    modell=model, sprak=language, tenkenivaa=reasoning_effort or None, motorinnstillinger=engine_settings,
                    formaal=purpose, tilleggsinstruks=additional_instructions, tillat_sider_uten_tekst=allow_pages_without_text,
                    task_instructions=task_instructions, output_schema=output_schema, quote_checks=quote_checks)

    @server.tool(description='Show the task, result contract, reader settings, versions and runs.')
    def show_plan(analysis_id: str) -> str:
        return call(tjeneste.vis_plan, analysis_id)

    @server.tool(description='Show the exact instructions, source input, schema, settings and hash for one run.')
    def show_input_package(run_id: str) -> str:
        return call(tjeneste.vis_inputpakke, run_id)

    @server.tool(description='Before reader execution, check whether the planned workbook destination fits Excel on Windows. Choose a shorter absolute output_directory if needed and preserve that choice in the plan purpose.')
    def preview_export_destination(analysis_id: str, output_directory: str | None = None) -> str:
        return call(tjeneste.preview_export_destination, analysis_id, output_directory)

    @server.tool(description='Record actual user approval of the concrete task and scope. approved_by identifies the responsible person; this does not review results.')
    def approve_plan(analysis_id: str, approved_by: str, plan_version_id: str | None = None) -> str:
        return call(tjeneste.godkjenn_plan, analysis_id, approved_by, plan_version_id)

    @server.tool(description='Revise the task or settings without rewriting earlier attempts. reset_output_schema clears the schema; quote_checks=[] clears quote checks.')
    def new_plan_version(analysis_id: str, change_note: str, request: str | None = None,
                         engine: str | None = None, model: str | None = None,
                         language: str | None = None, reasoning_effort: str | None = None,
                         engine_settings: dict | None = None, purpose: str | None = None,
                         additional_instructions: str | None = None, allow_pages_without_text: bool | None = None,
                         task_instructions: str | None = None, output_schema: dict | None = None,
                         quote_checks: list[dict] | None = None, reset_output_schema: bool = False) -> str:
        return call(tjeneste.ny_planversjon, analysis_id, change_note, oppgavetekst=request,
                    motor=engine, modell=model, sprak=language,
                    tenkenivaa=reasoning_effort, motorinnstillinger=engine_settings, formaal=purpose,
                    tilleggsinstruks=additional_instructions, tillat_sider_uten_tekst=allow_pages_without_text,
                    task_instructions=task_instructions, output_schema=output_schema, quote_checks=quote_checks,
                    reset_output_schema=reset_output_schema)

    @server.tool(description='Add one run per document. Omitted document_ids selects all project documents.')
    def add_runs(analysis_id: str, document_ids: list[str] | None = None) -> str:
        return call(tjeneste.legg_til_kjoringer, analysis_id, document_ids)

    @server.tool(description='Start approved planned runs in the background. Omitted run_ids selects all eligible runs. Follow show_status.')
    def start_runs(analysis_id: str, run_ids: list[str] | None = None, maximum: int | None = None) -> str:
        return call(tjeneste.start_i_bakgrunnen, analysis_id, run_ids, maximum)

    @server.tool(description='Stop dispatch and request cancellation of the active attempt.')
    def stop_runs(analysis_id: str) -> str:
        return call(tjeneste.stopp, analysis_id)

    @server.tool(description='Resume eligible unfinished work. Failed runs require retry_run.')
    def resume_runs(analysis_id: str) -> str:
        return call(tjeneste.gjenoppta, analysis_id, i_bakgrunnen=True)

    @server.tool(description='Show progress, run issues and any shared blocker. details=true includes full records.')
    def show_status(analysis_id: str, details: bool = False) -> str:
        return call(tjeneste.vis_status, analysis_id, details=details)

    @server.tool(description='Inspect a run, its results, attempts, raw replies, checks and reviews.')
    def show_run(run_id: str) -> str:
        return call(tjeneste.vis_kjoring, run_id)

    @server.tool(description='Request a new attempt with a reason; preserves previous attempts.')
    def retry_run(run_id: str, reason: str) -> str:
        return call(tjeneste.nytt_forsok, run_id, reason)

    @server.tool(description='Record an actual human decision; corrections require replacement_response.')
    def record_review(attempt_id: str, reviewer: str, action: str, reason: str,
                      replacement_response: dict | None = None) -> str:
        actions = {'approved':'godkjent', 'corrected':'rettet', 'rejected':'avvist'}
        if action not in actions:
            return json.dumps({'error':'Choose approved, corrected or rejected.'})
        return call(tjeneste.registrer_kontroll, attempt_id, reviewer, actions[action], reason,
                    replacement_response=replacement_response)

    @server.tool(description='Export a readable workbook and documentation ZIP. Default: one row per document, using its newest planned run (no fallback on failure). row_scope=runs includes history. output_directory selects a shorter export parent when needed. Nested records default to detail sheets; list_layout=inline also shows numbered lists in the main row. include_csv adds data tables inside the ZIP.')
    def export_results(analysis_id: str, include_sources: bool = True, include_csv: bool = False, list_layout: str = 'sheets', row_scope: str = 'documents', output_directory: str | None = None) -> str:
        return call(tjeneste.eksporter, analysis_id, include_sources, include_csv=include_csv, list_layout=list_layout, row_scope=row_scope, output_directory=output_directory)
