# 0.10.5 — Codex output schema and shell-policy failures

- Remove unsupported `uniqueItems` from the schema sent to Codex CLI while keeping the original schema and its post-run validation unchanged.
- Treat a Codex file-reading attempt whose shell was blocked by execution policy as a failed run, even if the model returned valid JSON with limitations.
- A live synthetic Claude Code file read succeeded. A live Codex CLI attempt passed schema validation but its shell was blocked by the local execution policy, including in a direct CLI run without this plugin. Codex file reading remains unverified in that environment.

# 0.10.4 — Reader-specific file tools

- Tell Claude Code to use native Glob, Grep and Read for the searchable source chunks, with its fixed helper for parsing and OCR.
- Tell Codex CLI to use its native shell for read-only `rg` searches and file reads inside the assigned workspace, with the fixed helper for parsing and OCR. No extra MCP tool or package is added.
- Keep the same source-unit evidence map and fail-closed checks from 0.10.3.

# 0.10.3 — Searchable source copies for large CLI reads

- Add small, numbered plain-text copies of extracted source units for native Glob, Grep and Read. This works across supported formats without another model tool, dependency or model pass; the original file and exact source-unit map remain authoritative.
- Give Claude file-reading sessions up to 60 tool turns and direct readers to use the bundled helper only for permitted parsing, rendering and OCR commands.
- Report turn-limit, denied-tool, oversized-prompt and provider errors separately. Failed responses remain failed and their raw transcripts remain in the audit trail.
- No change to API input limits, source import records, existing plans or completed results.

# 0.10.2 — Reader update offer during installation

- After interactive plugin installation and reader sign-in, ask whether to check for and install the latest selected reader CLI version. Declining leaves the installed CLI untouched.
- Keep direct installations with an explicit reader and noninteractive installations free of an extra prompt. Update checks run after the installation lock is released; failures leave the plugin and sign-in in place and show the retry command.

# 0.10.1 — Reader CLI updates in the installer

- Add a separate reader CLI update option to the installer menu and direct commands. Reader setup displays the update command.
- Use Claude Code's own updater. For a Codex CLI installed privately by this plugin, fetch the latest official stable Windows release, verify its published SHA-256, check the reported version, and restore the previous executable if verification fails. Leave other installers' Codex executables untouched and explain where to update them.
- Keep reader login and plugin updates separate. When updating both readers, attempt each one and report any failures. No analysis data, model settings or reader permissions change.

# 0.10.0 — One independent task per file

- One general task model and one public MCP interface (19 tools). Removed classification-specific plans, validators/exporters, Norwegian MCP aliases and old database migrations. Development breaking change: no compatibility layer; use a fresh store for analyses from v0.9.0 or earlier. Existing exported artifacts are not rewritten.
- Each iteration creates a fresh adapter and CLI session/API request. Removed automatic chunk extraction and synthesis. Large CLI inputs use the original file and source-unit map; oversized API/text-only requests fail explicitly within the agreed byte budget.
- Deliver Results.xlsx by default: one row per run, scalar/nested-object variables in columns, repeated records in linked detail sheets. Errors, run information and variable definitions are separate. `list_layout=inline` also shows numbered list values in the main row. Task-specific schema labels and optional CSV export remain available.
- Preserve failed/unstarted/rejected rows, nulls, zero/false, long text and literal formula-like strings. A start file and one documentation ZIP collect original results, sources and all attempts/reviews.
- Fix Windows long-path file copying and export staging/ZIP/workbook operations with extended paths, without a registry change.
- Shorten the host skill, server instructions and tool descriptions. Context controls remain distinct from OS filesystem isolation. Release verification uses offline tests and a clean MCP bootstrap; no live model calls or active local plugin update.

# 0.8.12 — Accurate Claude model reporting and consolidated results

- Identify the Claude reader from its own assistant messages instead of the first `modelUsage` entry, which may describe a helper model. Preserve all raw events and usage. Legacy JSON results identify a model only when usage is unambiguous; ambiguous telemetry is shown as unreported with a non-blocking diagnostic. Requested model and effort are unchanged.
- Consolidate Excel exports into four sheets. Results includes verbatim quotations and matching source locations beside each answer. Runs includes all human review events beside their attempts and explicitly marks attempts without review. Plan approval remains separate from result review.
- Preserve previous exports, recorded attempts, raw replies and JSON/CSV audit formats. Historical model fields are not silently rewritten. No new dependencies, database migration or inference calls are needed to apply these changes.

# 0.8.11 — Visible call evidence and compact status

- Preserve raw manifests, CLI events and response schemas unchanged in the English tool interface. In particular, `show_run` no longer translates schema property names while leaving `required` names unchanged.
- Show non-blocking `run_warnings` for CLI diagnostics, including warnings from successful calls. Keep queue failure and authentication rules unchanged; warnings do not stop independent work.
- Add per-call evidence to `show_run`, exported audit JSON and the new Model calls / Modellkall workbook sheet: extraction/synthesis stages, session IDs, CLI version, requested/reported settings, timestamps, duration, process/exit/HTTP information, token usage and links to exact inputs, raw replies and manifests. Preserve historical records and explicitly mark unreported telemetry.
- Make `show_status` compact by default. Set `details=true` for full source/attempt data; legacy Python and Norwegian Markdown status remain compatible.
- No new dependencies, database migration, automatic retries, provider fallbacks or changes to approved analysis settings.

# 0.8.10 — Return to the setup menu

- After each interactive installer action, choose Return to start menu or Exit. Perform several setup or maintenance tasks in the same window, including after an incomplete action.
- Direct commands still run once and preserve their exit status. An earlier failure remains reflected in the interactive session exit status even if a later action succeeds.

# 0.8.9 — Simpler setup and Azure Foundry

- Reduce the setup menu to Install, Sign-in and settings, and Update or repair, with Back available in submenus. Existing direct commands remain available.
- Set up Codex and Claude Code readers together with Both. Reuse verified sign-ins and continue the second reader if the first fails; report incomplete setup without undoing successful sign-ins. Each analysis still selects its reader explicitly.
- Add Azure AI Foundry key-based reading through Responses, OpenAI-compatible Chat Completions and Claude Messages. Require an explicit resource endpoint, deployment name and API format, retained in the approval/audit trail. No automatic protocol fallback, new dependencies or tool access. Deployments must support the requested structured output and parameters; Entra ID and legacy inference endpoints are not included.
- Add an empty `AZURE_AI_API_KEY` field when opening older local settings files, preserving existing keys and comments.

# 0.8.8 — One setup menu and a smaller user package

- Use `installer.cmd` for installation, reader sign-in, OCR, API settings, updates, repair and recovery. Existing host/flag commands still work.
- Keep one short bilingual README at the package root and detailed user guides in `docs`. Omit separate setup launchers, development material, test fixtures and optional examples from the distributed package. No new dependencies.
- This package-layout transition requires installing the new ZIP once when upgrading from 0.8.7 or earlier; their fixed-file-list updater cannot apply the smaller package. Data/settings are retained and previous program files are backed up. Future updates use `installer.cmd update` from the installed folder.

# 0.8.7 — Complete reader setup and document tools

- Find installed Claude Code and Codex readers even when the current shell has an outdated PATH. Refresh child-process paths from Windows settings and report the actual executable found.
- Complete reader selection and subscription sign-in from the installer. Reuse a verified existing login; missing or unconfirmed access blocks dependent reading instead of silently switching engines.
- Prepare local Tesseract OCR with English and Norwegian language data during normal installation. Verify downloaded language data and report incomplete setup explicitly. `--skip-ocr` is available for deliberate minimal installations.
- Give new CLI plans file tools, the preserved original document, PDF rendering, OCR and parsers for supported Word, Excel and text formats. Each call gets a fresh workspace; normal tool iterations can take place inside that session. Web tools and inherited conversations, memories, rules and integrations are disabled through the CLI configuration.
- Preserve the exact input, source checksum, workspace manifest, raw CLI events and file artifacts for review. Evidence must still match the approved source extraction. CLI restrictions are not a claim of complete operating-system isolation; see `docs/DOCUMENT_PROCESSING.md`.
- Block start when required tools, reader access, criteria, document selection or plan approval are missing. Record individual run errors and continue other independent runs; confirmed missing CLI authentication blocks later dependent calls. No automatic retry or alternative reader.

Existing approved plans retain their settings. Create and approve a new CLI plan to use file tools. Install the ZIP or update through `update.cmd`, then start a new conversation. Verification and remaining acceptance limits are recorded in `tests/TESTLOGG.md`.

# 0.8.6 — Start from an ordinary task description

- Guide exploratory requests through a short conversation: propose criteria and routine settings, clarify consequential ambiguity, and distinguish user requirements from suggestions and assumptions.
- Present a plain-language plan with the selected files, uncertainty rules, reader settings and result location before approval. Offer an optional pilot and keep actual human review separate from machine checks.
- Report unsupported files and subfolders omitted during folder import. Explicitly selected children get their own import results; existing source files stay unchanged.
- Simplify the English and Norwegian quick-start examples around the user's own annual reports. Users do not need to prepare criteria or technical parameters before beginning.

Update through `update.cmd` or install the Windows ZIP, then start a new local conversation. Existing analysis data is retained. Verification and limits are recorded in `tests/TESTLOGG.md`; the conversational guidance has not yet been tested with a first-time user.

# 0.8.5 — Visible project folders, Excel exports and controlled session closure

- Choose and remember a visible project directory. Plans and exact input previews are saved there before execution; the start file links to them and to completed exports.
- Export one workbook with overview, results/comments, evidence, actual human reviews and attempts. Quotes and labels stay unchanged; failures and unreviewed results remain visible.
- Keep one start file and plan in the chosen language, source copies and a separate JSON/raw audit folder. CSV is opt-in; the previous bilingual export remains available explicitly.
- Use unique snapshots and staged publication to preserve previous exports and user-edited workbooks. Links remain relative. Excel edits never count as registered human review.
- Preserve long or XML-incompatible cell text in linked text files; source strings are never Excel formulas.
- Add project-directory fields through a non-destructive database migration. Existing data and old exports are not moved.
- Manual installation/update/recovery closes cooperating plugin connections after current work is saved, pauses the remaining document queue and prevents reconnection until installation ends. A 60-second timeout leaves installed files unchanged; no processes are killed. Automatic startup updates continue to defer around active sessions.
- Add cancellable Windows pipe input so idle MCP connections can actually close without waiting for the host to disconnect.
- Put a three-step quick-install guide at the top of both READMEs. Upgrading from 0.8.4 or earlier requires closing the old connections once; those versions do not implement cooperative shutdown.

# 0.8.4 — Plain README, assisted setup and Codex desktop guard

- The README now states plainly what the plugin does, why it is useful, what it does not do and how to install it, in English and Norwegian. It includes two paste-in setup prompts: one for Claude Code, which lets the assistant download, verify and install, and one for the ChatGPT/Codex app, which stops before the installer and asks the user to double-click it.
- The installer, `--recover` and automatic updates refuse to run inside the packaged Codex desktop app. Such processes have virtualized writes below `%LOCALAPPDATA%`, which is how a stale shadow copy masked the real installation earlier. A session started by the Codex desktop app therefore only reports a newer version; run `update.cmd` from Explorer or a normal terminal.
- `update.cmd --check` and `--mode` work while plugin sessions are open; only `--install` needs the other sessions closed.
- Start guides, setup and update documentation and the host skill carry the same instruction: never run `installer.cmd` from a terminal inside the Codex app.

Upgrading from 0.8.2 or 0.8.3 uses the updater (`update.cmd --install`, or the notify/auto policy). Versions through 0.8.1 still need one ZIP installation. Close plugin sessions in both apps before installing, then start a new conversation.

Verification and limits are recorded in `tests/TESTLOGG.md`. No provider/model calls are required for the local regression and packaging checks.

---

# 0.8.3 — Interrupted installation recovery

A forced interruption of `installer.cmd` (a killed process, a closed window, a power loss) leaves a `pending-install.json` journal that blocks further installation and managed startup. This release adds the command that resolves it.

- `installer.cmd <app> --recover` reads the journal and restores the state before the installation began: previous files return from the backup, the incomplete copy is kept as `failed-install-<id>`, and the previous marketplace and plugin registration are restored through the host CLI and verified. A fresh installation that was interrupted ends with nothing registered. An installation that had completed except closing the record is verified and closed without changing files.
- Every recovery writes `recovery-<id>.json` beside the journal with the record and the actions taken. Nothing is deleted; missing previous files or sources stop recovery with the record kept. Journals written by 0.8.2 are accepted.
- New journals record whether the target and plugin registration existed and which package was incoming, so recovery does not have to guess.
- The daily update check runs under the shared session lock, so a second concurrent session also sees the "version available" notice. Installation still requires that no other plugin session or worker is active.
- Startup and installer errors name the recovery command.
- Codex desktop: the installer detects a stale plugin copy in the packaged app's `LocalCache`, which the app reads instead of the registered installation, and moves it aside with `--move-shadow` or an interactive yes. Without this, the desktop app could keep running an old version after an upgrade.

Upgrading from 0.8.2 uses the updater (`update.cmd` or the notify/auto policy). Versions through 0.8.1 still need one ZIP installation. Close existing plugin sessions before installing, then start a new conversation.

Verification and limits are recorded in `tests/TESTLOGG.md`. Interruption at every installer step is tested with a fake host and, for one scenario, with the real Claude Code and Codex CLIs in temporary profiles. A genuine kill of a running installer process is modelled, not executed. No provider/model calls are required for the local regression and packaging checks.

---

# 0.8.2 — Existing installations and release updates

The Windows installer now detects existing versions and marketplace sources before replacing files. A source conflict offers an explicit switch, same-version changes can be repaired, and older packages cannot silently downgrade an installation. Replacements retain a backup and routine registration failures restore the previous installation.

- `update.cmd` provides check now, update now, notify only (default), automatic and off.
- Managed sessions check stable GitHub releases at most daily. Optional automatic installation waits until other plugin sessions and analysis workers are closed; local edits block replacement.
- Private repository downloads use an existing GitHub CLI login. Shared ZIP installation remains available without repository access.
- Downloads require the release checksum; package identities/versions and archive paths are validated. Builds use fresh staging and exclude environments, credentials and analysis data.
- Analysis attempts record the application version and managed package fingerprints.
- Development handover to Claude Code: start with `docs/CLAUDE_HANDOFF.md` and `docs/CLAUDE_STARTPROMPT.md`.

Install this release once from the ZIP to acquire the updater. Versions through 0.8.1 do not have this update mechanism. Close existing plugin sessions, run `installer.cmd`, then start a new conversation. A forced interruption can leave a recovery record requiring manual resolution; do not remove the record or backups as a shortcut. The next real published-version automatic upgrade still needs an end-to-end acceptance test.

Verification and limits are recorded in `tests/TESTLOGG.md`. No provider/model calls are required for the local regression and packaging checks.

---

# 0.7.0 — One routine across comparable files

Systematic Document Analysis now applies a shared analysis plan to PDF, DOCX, XLSX, CSV/TSV, TXT and Markdown sources. The central workflow is a list of comparable files assessed with the same criteria, interpretation rules, model settings and review procedure.

- Source profiles show structure and extraction scope before approval.
- Evidence resolves to PDF pages, Word blocks/tables, text lines, CSV records or workbook sheets/cell ranges.
- Workbook formulas and cached results are distinguished. Missing caches are reported; formulas are not recalculated.
- Source copies, locators and extraction metadata are preserved in input, history and exports. Existing PDF records remain compatible through an additive database migration.

Each whole file is still one run. Automatic splitting of large files and selecting individual worksheet rows/sheets as separate runs are not implemented. Word headers/footers, tracked-change wrappers, images and other embedded content are outside the current extractor; Excel images/charts are also excluded. Coverage refers to extracted units within the displayed scope. See docs/SOURCE_FORMATS.md.

Local verification uses synthetic files and mock readers, with no model calls. It covers format extraction, evidence, formulas, CSV multiline records, exports and old-database compatibility. Install with installer.cmd and start a new conversation in Codex or Claude Code.
