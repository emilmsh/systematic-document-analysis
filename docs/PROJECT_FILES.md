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
Draft and approved plans are saved under `plans/`, with `Plan.md` and a criteria copy.
`show_input_package` saves the exact returned package under `previews/`.
`inspect_source(export_markdown=true)` puts the extraction inspection copy there too.
These are generated reading copies. Substantive changes must go through a new plan version;
editing a copy does not change the approved plan or historical inputs.

## After execution

`export_results` creates a new snapshot under the project's `exports/` directory:

```text
an1-20260921-120000-<unique-id>/
  START_HER.md                 # START_HERE.md for English
  Resultater.xlsx              # Results.xlsx for English
  Plan.md
  Kilder/                     # Sources/ for English; optional
  Dokumentasjon/              # Documentation/ for English
    analyse.json
    modellkall/
```

The six workbook sheets contain overview, results with comments and status, verbatim evidence
with source locations, actual human review history, attempts including failures, and **Model calls**
(`Modellkall` in Norwegian). The last sheet lists each recorded reader call, including separate
extraction and synthesis calls, across all attempts. It includes session/request IDs, CLI version,
requested/reported model and effort, timestamps, duration, exit/HTTP status, token usage and
diagnostics, with relative links to the exact input, raw reply and manifest. Chunk parents do not
count synthesis twice. Unavailable telemetry is explicitly marked **Not reported**. Historical
timestamps are not inferred; older manifests and raw files are never rewritten.
Header language follows the current plan; quotes and answer labels stay unchanged.
Source strings are written as text, never executable Excel formulas. Strings exceeding Excel
cell limits or containing XML-incompatible characters are preserved in linked text files.
The start file identifies these cases; nothing is silently truncated.

`analyse.json` preserves the structured record. `modellkall/` retains exact requests,
instructions, raw replies and metadata per attempt and extraction/synthesis call. Failed
attempts remain recorded. Internal schema names remain stable for compatibility.
Source copies are included by default. Use `include_sources=false` to omit them; a missing
requested source stops the export.

`show_status` returns compact progress by default. Use `show_status(details=true)` for the previous
full payload or `show_run` for a selected run's `model_calls` and immutable raw manifest. The legacy
Python service and Norwegian Markdown status retain their existing detailed behavior.
`run_warnings` exposes reader stderr diagnostics even on successful calls. Warnings do not block
the queue or change result validation. Status covers the latest attempts; exports retain all attempts.
Complete recorded diagnostics remain in the manifests; status snippets are bounded and indicate truncation.

Recorded reader attempts may be simulated, failed or stopped before dispatch. Session IDs, raw events
and exit status are local execution evidence, not independent vendor attestations. Requested model
settings do not prove the actual model, reported token usage is not an invoice, and available file
tools do not prove the reader used them.

Move the entire snapshot together to preserve relative links. Every export has a timestamp
and unique suffix, so existing files and user edits are not overwritten. Failed exports are
not published as completed snapshots. Active runs must finish before export.

Excel edits do **not** update the authoritative analysis or count as human review.
Use `record_review` for actual approval, rejection or correction with a person and reason.

## Optional formats and compatibility

- `include_csv=true`: four CSV tables under `CSV/`, in the current plan's language only.
- `legacy_format=true`: the previous bilingual CSV/Markdown layout in a new visible snapshot.
- XLSX is the reading surface; JSON/raw files serve audit and machine-processing needs.
  Narrative Word/PDF reports are not automatically generated.

Norwegian tools: `opprett_prosjekt(mappe=...)`, `sett_prosjektmappe`, and
`eksporter(med_csv=..., gammelt_format=...)`. CLI examples:

```text
sda prosjekt "My analysis" --mappe "C:\Projects\Policy analysis"
sda prosjektmappe pr1 "C:\Projects\New policy analysis"
sda eksporter an1
sda eksporter an1 --med-csv
sda eksporter an1 --gammelt-format
sda eksporter an1 --no-med-kilder
```

Migration adds only the project directory field. Earlier analyses, sources, approvals, attempts
and reviews are preserved. Old projects get a visible folder at their first file-producing
operation, or can be assigned one explicitly beforehand.
