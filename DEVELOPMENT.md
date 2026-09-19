# Development guide

This is the current development guide for **Systematic Document Analysis**. Earlier decisions and verification reports are archived in [UTVIKLINGSSTRATEGI.md](UTVIKLINGSSTRATEGI.md); its older names and superseded restrictions describe history.

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
- Fresh default data directory uses the new slug; existing databases in the old directory are reused. Two existing default databases require explicit selection. No silent move, merge or deletion.
- One Windows distribution supports both hosts. Rebranding changes the plugin ID, so disable the old plugin after installing the new one.

## Contributor map

`modell.py` describes persistent plans; `tjeneste.py` implements operations; `kjoring.py` owns the queue; `lager.py` owns SQLite. `prompt.py` creates inputs; `validering.py` checks evidence; `adaptere/` implements readers. `languages.py` and `english_tools.py` provide the English boundary. `eksport.py` and `english_export.py` write audit and reading copies.

Write new documentation and public interfaces in English. Use `README.no.md` and `START_HER.md` for Norwegian onboarding. Avoid mechanical renaming of storage fields or old code identifiers: preserve compatibility and keep migration work separate from behavioural changes.

## Local checks and packaging

Run `python -m pytest -q` using the project virtual environment. These tests use synthetic local files and fake provider transports, with no model calls. `tests/prov_plugin.py` bootstraps a clean package and exercises MCP; `tests/prov_installasjon.py` registers and updates both hosts under temporary configurations. Bootstrap downloads Python dependencies.

Build with `python bin/lag_release.py`. The allowlist excludes credentials, analysis data, environments and downloaded reports. Validate plugin manifests and the skill before release. Update version in pyproject, package and manifests together. Publish the ZIP and SHA256SUMS with the release; README links use a stable asset filename.

## Open limits

CLI flags restrict model context and tools; they are not full OS isolation. The host can access the store as the same local user. Large documents lack chunking/context limits. OCR, DOCX, group input and synthesis remain future work. Mock transport tests do not verify account access, real provider parameter interpretation, billing or substantive analysis quality. Record these boundaries alongside verification results.
