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
