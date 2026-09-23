# Development guide

Systematic Document Analysis is a controlled for-loop over files. The conversation stays in Codex or Claude Code; both use one local MCP interface. Each file gets the same agreed task through a fresh CLI/API worker. See [core design](docs/CORE_REDESIGN.md) and [task contracts](docs/TASKS.md).

## Architecture

`modell.py` defines plans; `tjeneste.py` exposes operations; `kjoring.py` owns the queue; `lager.py` owns SQLite. `prompt.py` builds exact inputs, `execution.py` prepares one call per file, and `adaptere/` implements readers. `task_contract.py` validates the declared response; `task_results.py` applies actual reviews without replacing originals.

`source_formats.py` and `ocr.py` extract source units. CLI workers can inspect the original file using `reader_files.py`. Large CLI inputs reference that file; oversized API inputs fail explicitly. There is no automatic extraction/synthesis pipeline.

`task_dataset.py` maps arbitrary nested results into variables and related collections. `task_workbook.py` writes one main row per run and appropriate detail sheets. `task_export.py` stages and publishes a workbook, start file and documentation ZIP. `file_io.py` handles Windows extended paths for export and file copies.

The task, sources, settings and result schema are versioned. Preserve exact input, raw replies, errors and corrections. No automatic retries, reader switches or paid fallback. Never register machine validation as human review. Unknown telemetry remains unknown. API credentials stay outside plans, inputs and exports.

Use English public interfaces and documentation; Norwegian user guides and result language remain supported. There is one task model and no criteria compatibility path. Existing internal Norwegian identifiers need not be renamed mechanically. Earlier design/release notes describe history, not current contracts.

## Verification and packaging

Run `python -m pytest -q` with the project environment. Tests use local fixtures and fake transports, with no model calls. On Windows use a fresh, short `--basetemp` if the host restricts old temporary directories. `tests/prov_plugin.py` exercises a clean bootstrap, MCP and restart; it downloads dependencies. `tests/prov_installasjon.py` registers both hosts under temporary configurations.

Build with `python bin/lag_release.py`. The allowlist excludes credentials, analysis data, environments and downloaded reports. Validate manifests and the skill before release; update package/manifests together when releasing. Installation into an active user profile and publication are separate from local development verification.

CLI controls isolate conversational context and working copies, not all filesystem reads by the same OS user. Offline tests do not establish live provider access, billing, model quality or semantic completeness. Preserve these limits in verification reports.
