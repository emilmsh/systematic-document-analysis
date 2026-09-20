# Development guide

This is the current development guide for **Systematic Document Analysis**. Earlier decisions and verification reports are archived in [UTVIKLINGSSTRATEGI.md](UTVIKLINGSSTRATEGI.md); its superseded restrictions describe history; current product naming is used throughout.

## Product and architecture

The product is a working plugin for users' own documents. Simulation, synthetic fixtures and example reports are optional. The conversation stays in Codex or Claude Code. Both hosts use the same local MCP service; readers are independent CLI or API adapters. Do not introduce a second chat UI.

The authoritative flow is project → imported document → versioned plan → run → attempt → review → export. Plans contain the original request, criteria, reader, model, effort, settings and language. Plan changes create new versions. Preserve source copies, exact inputs, raw answers and corrections. Never register machine validation as human review.

CLI readers use subscription sign-in and the vendor's harness. API readers use separate provider credentials and billing. No automatic retry, engine switch or paid fallback. Never accept secrets as plan/settings arguments. Provider bodies are previewed and hashed without authentication headers. Known key echoes are masked before storage.

## Version 0.6.0: name and languages

- Product: Systematic Document Analysis; plugin/repository slug: `systematic-document-analysis`.
- English primary documentation and public MCP tools; Norwegian user guides and legacy tools retained.
- Plans select `en` or `nb`. Quotes and answer labels are never translated. Existing plans default to Norwegian; earlier records are not rewritten.
- English criteria and engine-setting aliases normalize at the boundary. Persistent identifiers, Python module `kildeanalyse` and raw response schemas stay stable.
- English export reading copies accompany legacy audit files. Historical attempt files are copied without modification. A plan summary renders the current instruction template; the exact historical instruction is in each attempt's `systeminstruks.txt` and input.json.
- Current data directory uses the product slug. Version 0.8 removes former automatic store discovery; use SDA_DATA for an explicitly selected store. No silent move, merge or deletion.
- One Windows distribution supports both hosts. Rebranding changes the plugin ID, so disable the old plugin after installing the new one.

## Contributor map

`modell.py` describes persistent plans; `tjeneste.py` implements operations; `kjoring.py` owns the queue; `lager.py` owns SQLite. `prompt.py` creates inputs; `validering.py` checks evidence; `adaptere/` implements readers. `languages.py` and `english_tools.py` provide the English boundary. `eksport.py` and `english_export.py` write audit and reading copies.

Write new documentation and public interfaces in English. Use `README.no.md` and `START_HER.md` for Norwegian onboarding. Avoid mechanical renaming of storage fields or old code identifiers: preserve compatibility and keep migration work separate from behavioural changes.

## Local checks and packaging

Run `python -m pytest -q` using the project virtual environment. These tests use synthetic local files and fake provider transports, with no model calls. `tests/prov_plugin.py` bootstraps a clean package and exercises MCP; `tests/prov_installasjon.py` registers and updates both hosts under temporary configurations. Bootstrap downloads Python dependencies.

Build with `python bin/lag_release.py`. The allowlist excludes credentials, analysis data, environments and downloaded reports. Validate plugin manifests and the skill before release. Update version in pyproject, package and manifests together. Publish the ZIP and SHA256SUMS with the release; README links use a stable asset filename.

## Open limits

CLI flags restrict model context and tools; they are not full OS isolation. The host can access the store as the same local user. OCR and bounded per-document reading are implemented. Cross-document synthesis and rows/sheets as separate runs remain future work. Mock transport tests do not verify account access, real provider parameter interpretation, billing or substantive analysis quality. Record these boundaries alongside verification results.


## Version 0.7.0: format-independent routine

The product applies one shared procedure to comparable files, not only PDFs. source_formats.py adapts DOCX, XLSX, CSV/TSV and text into numbered source units and locators. PDF keeps its physical page references. Extraction scope/structure is stored with the source and shown before approval. Existing response fields carry source-unit IDs; resolved locations accompany evidence. An additive metadata column preserves compatibility. One whole file remains one run; row/sheet selection remains separate future work; version 0.8 adds bounded reading. See [format scope](docs/SOURCE_FORMATS.md).

## Version 0.8.0: approachable setup and controlled document processing

Private Python bootstrap, optional reader installation/login helpers and a local key-file editor reduce manual setup. Never log keys, include completed settings files in packages or read them into a conversation. Runtime/helper downloads are pinned and checksum-verified; update these pins deliberately. OCR uses local Tesseract and preserves source copies. Source inspection can produce Markdown with stable locators.

New plans carry byte budgets, maximum chunk count and optional priorities. Oversized sources are read in bounded extraction calls, followed by one synthesis of validated findings. All exact calls, raw answers and provenance travel through history/export. Priority changes order, never coverage. The synthesis may exceed budget and must fail visibly rather than truncate. No silent retry, recursive summary, model switch or paid fallback. Source directives stay untrusted data.

The host exercises judgment inside user instructions and discusses file-specific difficulties. Explicit model, effort, source-scope and reporting choices take precedence. Five fictional use cases demonstrate the ordinary workflow across formats; they are optional product examples, not mandatory tests.
