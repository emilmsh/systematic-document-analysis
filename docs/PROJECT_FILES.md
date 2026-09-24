# Project files and exports

Choose a visible **new or empty project directory** with `create_project(name, directory=...)`.
The directory is remembered in the database. Without an explicit directory, the plugin creates
a unique folder under `~/Documents/Systematic Document Analysis` and returns the path.
`SDA_PROJECTS_ROOT` can set that default parent. AppData, the database directory and the known
plugin installation are rejected as destinations. Credentials remain in private settings.

Use `set_project_directory(project_id, directory)` for an existing project. It does not move or
delete earlier exports or authoritative data. An ownership marker prevents different projects
or data stores from claiming the same folder.

## Before execution

Open `START_HERE.md` in the project folder for plans, input previews, exports and run status.
Draft and approved plans are saved under `plans/`, with `Plan.md` and `task.json`.
`show_input_package` saves the exact returned package under `previews/`.
`inspect_source(export_markdown=true)` puts the extraction inspection copy there too.
These are generated reading copies. Substantive changes must go through a new plan version;
editing a copy does not change the approved plan or historical inputs.

## After execution

`export_results` creates a new snapshot under the project's `exports/` directory. Tasks deliver a workbook by default, with task-specific variables:

```text
an1-<unique-id>/
  START_HERE.md               # START_HER.md for Norwegian
  Results.xlsx               # Resultater.xlsx for Norwegian
  Documentation.zip          # Dokumentasjon.zip for Norwegian
```

The first sheet has **one row per run by default**, with the document, run ID, status and generated variables. Nested objects become columns. Repeated records default to detail sheets linked by run and parent IDs, with counts in the main row. Set `list_layout="inline"` to additionally display numbered lists in main cells. Independent lists never multiply the main rows or create a Cartesian product. Errors and retries have sheets only when relevant. Variable definitions have a readable sheet. Long text uses a linked sheet inside the same workbook.

Failed, unstarted and rejected runs retain their row with blank result variables; their status is visible in the main sheet and reasons appear in the notes sheet. Prose-only results remain a text variable; export does not invent new findings. Plan approval and automatic validation do not count as human result review.

The ZIP preserves `Plan.md`, original-shape JSON and readable results in `results/`, optional originals in `sources/`, and all attempts, reviews, validation, exact inputs and raw responses in `audit/`. Extract it only when this detail is needed. `include_csv=true` adds the main dataset and detail tables in `datasets/` inside the ZIP. CSV retains raw values, so use the workbook for safe Excel viewing. Export edits do not modify original results. See [task contracts and validation](TASKS.md).

## Status and portability

`show_status` is compact by default. Use `details=true` or `show_run` for exact attempt evidence, diagnostics and reported telemetry. Missing metadata remains unknown. Status covers current attempts; the documentation archive retains all attempts and reviews.

Every export is staged and published with a unique name. Failed exports leave no completed snapshot; existing exports and user edits remain untouched. Move all three deliverable files together. Windows export paths use extended-path filesystem operations without requiring a registry setting.

CLI equivalents include `sda eksporter an1`, `--med-csv`, `--list-layout inline`, and `--no-med-kilder`. Editing Excel does not update the authoritative analysis or count as human review; use `record_review` for actual decisions.

## Delivery selection and Excel paths

Agree the format, row unit, fields and repeated-record layout before reader execution; retain that agreement in the plan purpose. The default `row_scope="runs"` keeps one row per run, including failures and unstarted work. `row_scope="documents"` selects the newest planned run per document by plan version, creation time and numeric run ID; it never falls back to an older success. Identical output schemas share columns; different definitions stay separate. Empty detail sheets are omitted. Error and retry sheets appear only when relevant. Full telemetry and attempt history remain in the ZIP.

Exports use short unique folder names. On Windows the complete XLSX path is checked against a conservative 218-character compatibility budget before files are written. `output_directory` (CLI: `--output-directory`) chooses an absolute parent for this export without moving the project or previous exports. A longer path requires a shorter destination, even if Python can write it.
