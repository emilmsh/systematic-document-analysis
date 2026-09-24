---
name: systematic-document-analysis
description: Run one agreed task independently across a list of files with fresh CLI or API workers, a structured result per run and a readable audit trail. Use for repeatable file tasks in Codex or Claude Code; cross-file synthesis happens after the independent runs.
---

# Systematic Document Analysis

Use the shared `document_analysis` service as a controlled loop: one file and a fresh worker context per run. The host agrees the task, starts and monitors runs, and presents the collected results. Each worker chooses a method suited to the task using the assigned file and available tools; no other file's result enters its context.

1. Check `show_setup`, import the selected files and resolve material exclusions. Respect the user's reader, model and settings. Use `inspect_source` when extraction quality matters. A source limitation is not a negative finding.
2. Turn the request into one repeatable instruction and useful result variables. Default to an object `output_schema` for a dataset; a prose result is also valid. Show the file scope, variables and execution settings through `show_plan` and `show_input_package`, then obtain the sign-off described below. Use sensible delivery defaults and ask only about consequential ambiguity. Preserve the agreed delivery choice in the plan purpose, then record actual authorization with `approve_plan`.
3. Start the approved runs and follow `show_status`/`show_run`. Let other files continue when one fails. A retry needs a reason and preserves previous attempts. Change the task, reader, model or settings through `new_plan_version` and obtain approval of the changed plan before execution; do not silently switch methods or models.
4. Present the results in the agreed form. The default workbook has one row per run, variables in columns, repeated records in linked sheets, and error or retry sheets only when relevant. `row_scope="documents"` selects the newest planned run per file when the user wants one row per file. A workbook destination can be checked with `preview_export_destination` before execution. Give the user a readable deliverable, not a collection of raw JSON files.

## Execution settings and user sign-off

Before starting workers, present a short, concrete proposal covering the reader (`engine`), exact requested model ID or deployment name (`model`), and reasoning effort (`reasoning_effort`). Distinguish these worker choices from the host conversation's model. Preserve choices the user has already supplied. If choices are missing, propose supported settings from `show_setup` and the plan, briefly explaining the quality, time or cost tradeoff; defaults are proposals, not approval.

Include other supported parameters when they materially affect the task: timeout, output-token limit, input-byte budget, file-tool access, and API endpoint/format where applicable. Show concrete configured values and identify provider defaults or unsupported effort controls explicitly; do not invent values or imply that requested effort is guaranteed to be honoured. Do not expose credentials. Keep routine settings in the detailed plan rather than asking the user to configure every field.

Combine these choices with the task and file scope in one approval request. Let the user accept or adjust the proposal, and wait for actual approval of that concrete plan before `approve_plan` and worker execution. A general request to analyse files is not sign-off on settings the user has not seen. Reuse existing explicit authorization when it covers the same plan and settings; do not ask twice. Record the responsible person through `approved_by` without inventing an approver.

CLI workers may use their native tools freely and choose their own method; do not prescribe commands or pass results from another run. Large inputs use the file workspace when supported; oversized API inputs fail visibly. Task-specific checks such as `quote_checks` or visual verification of blank PDF pages are optional. Use `record_review` only for actual human decisions. Automatic validation and reported coverage do not establish substantive correctness or human review. CLI context separation is not full operating-system file isolation.

See [task contracts](../../docs/TASKS.md), [source formats](../../docs/SOURCE_FORMATS.md), [file tools](../../docs/DOCUMENT_PROCESSING.md), and [setup](../../docs/USAGE.md) for details.
