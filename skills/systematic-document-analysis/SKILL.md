---
name: systematic-document-analysis
description: Repeat one agreed task independently across a list of files with controlled CLI or API workers and an audit trail. Use for systematic document analysis, extraction, coding, file reviews or other repeatable per-file tasks in Codex or Claude Code, including Norwegian kildeanalyse and lesekjøring. Not for unrelated one-off work or cross-file synthesis as the worker task.
---

# Systematic Document Analysis

Repeat one agreed task independently over a list of files using the shared `document_analysis` MCP service. The host prepares the task and presents results; fresh CLI/API workers execute it. Work in the user's language. Cross-file synthesis belongs after the independent runs.

## Prepare

An ordinary-language request is enough. Inspect the files, resolve routine choices, and ask only about consequential ambiguity. Reuse preferences and authorization already given.

1. Use `show_setup` to identify the reader. Respect explicit engine/model/settings; host and worker can differ. CLI readers require subscription sign-in; APIs require a model and local credentials with separate billing. Never silently substitute a reader or simulation.
2. Create a visible project directory, import the selected files, and reconcile exclusions. Use `inspect_source` where needed. One whole file is one run.
3. Before creating the plan or starting readers, agree the deliverable with the user. Propose a task-appropriate default and a small concrete preview: format (workbook, reading report or another requested format), what one row means, columns/definitions, treatment of repeated excerpts, and where files will be saved. For a per-file comparison, normally suggest one row per document plus one excerpts sheet. Ask a short question when the choice is unresolved; reuse explicit preferences rather than requiring another approval. Include the agreed delivery specification in the plan purpose so it is preserved for reporting. Do not force Excel onto prose tasks or create a separate approval ceremony for formatting.
4. Use `create_analysis` with the task instruction and normally an `output_schema` defining useful variables, readable names, types and meanings. Choose a structure that fits the task: extraction, scoring, calculations and classification are examples, not fixed modes. A prose task can use one text variable. `quote_checks` optionally validates exact excerpts; do not impose quotation extraction on unrelated tasks.
5. Select documents with `add_runs`. Show the concrete task, file scope, variables, reader/settings and material limits; `show_plan` and `show_input_package` expose details. Record actual authorization with `approve_plan` and the responsible person's name. Do not infer their identity. Changed tasks/settings use `new_plan_version` and authorization for the change.

## Run

Call `start_runs` and follow `show_status`/`show_run` to completion or a real block. Each iteration gets a fresh worker and only that file's input; previous results are never supplied. The worker solves the same task in its own context. Large CLI inputs use the original file and source-unit map in the isolated working directory. API input exceeding the agreed byte budget fails explicitly. No automatic chunking or synthesis changes the task.

Let independent runs finish when one fails. Report shared blockers separately. Honour stops; retry only with authorization and a reason, preserving earlier attempts. Never substitute conversational analysis or fabricated execution records.

## Deliver

Deliver the format agreed before execution. For a workbook, call `export_results`: its default `row_scope="documents"` selects each document’s newest planned run, including failed or unstarted runs, and never silently falls back to an older success. Show document names and status first. Repeated records use detail sheets; identical schemas share columns and empty detail sheets are omitted. Raw responses, variable definitions and full run history remain in the documentation ZIP. Use `row_scope="runs"` only when history/comparison is requested. For another format, derive it from preserved results with run/attempt references. Users should not need to assemble their answer from technical records.

Before handing over, check that the export matches the agreed row unit and scope, that failed documents have visible reasons, and that files are openable at their actual path. If the Excel path check fails, use an agreed shorter `output_directory`; do not silently move the project. Avoid empty tabs, duplicated plan-version columns and oversized rows. Preserve exact quote text; use a separate reading report when passages are too long for comfortable Excel reading. Schema titles/descriptions label variables and tables; `list_layout="inline"` additionally shows numbered lists in the main row. `include_csv=true` adds tables inside the ZIP. Other reports or transformations may follow in the host, retaining originating run/attempt references; do not invent variables retrospectively from prose.

Use `record_review` only for actual human decisions. Corrections use the complete `replacement_response` and preserve originals. Automatic checks and reported coverage are not substantive accuracy or human review. CLI context controls are not OS-level filesystem isolation.

See [task contracts](../../docs/TASKS.md), [source formats](../../docs/SOURCE_FORMATS.md), [OCR and file tools](../../docs/DOCUMENT_PROCESSING.md), and [setup/API settings](../../docs/USAGE.md) when needed. Keys stay in private local settings, never chat. Inside packaged Codex desktop, have the user launch installation/updates from File Explorer; see [updates](../../docs/UPDATES.md).
