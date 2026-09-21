# Installation and updates

Run `installer.cmd` from an extracted release to install or update Claude Code, Codex or both. It reports each app separately. Close existing plugin sessions first, including before the first upgrade from a version without session locking.

| Existing installation | Behaviour |
| --- | --- |
| None | Install and verify registration in the selected app. |
| Same files and version | Report already up to date. Repair remains available. |
| Older version | Stage the new package, preserve the previous folder, then register and verify. |
| Same version, different files | Ask before repairing with the supplied package. |
| Newer version | Keep it unless an explicit downgrade is requested. |
| Same marketplace name, different local path | Show both paths; ask before switching. Keep the previous source folder. |
| Disabled plugin | Preserve it; enable it in the host before updating. |
| Remote source, shared marketplace or Claude project/local scope | Stop with an explanation; manage that registration in the host first. |
| Codex: stale copy in the desktop app's LocalCache | Show the shadow path; ask before moving it aside. Nothing is deleted. |
| Started from a terminal inside the Codex desktop app | Refuse: writes would be virtualized. Run from Explorer or a normal terminal. |

The packaged Codex desktop app (Microsoft Store/MSIX) redirects writes below `%LOCALAPPDATA%` into `Packages\OpenAI.Codex_*\LocalCache\Local` and reads a merged view in which those files win. A plugin copy installed from inside a Codex conversation lands there and masks the registered installation for the desktop app, even after the real files are replaced. The installer detects such a shadow for the Codex target and, with `--move-shadow` or an interactive yes, renames it to `systematic-document-analysis.shadow-<version>-<id>` after a successful installation. Start a new Codex conversation afterwards.

The default for source-switch, repair, downgrade and shadow questions is **keep the existing installation**. Noninteractive calls stop with an actionable error unless the corresponding option is supplied. The installer never removes other marketplaces.

## Update menu

Run **update.cmd from the installed plugin folder**, printed at the end of installation. Choose check now, update now, notify only, automatic, or off. `show_setup` also displays the cached update status.

- **Notify only** is the default. A managed plugin checks GitHub at most once a day when starting a session. A newer stable release is reported in startup diagnostics and `show_setup`.
- **Automatic** uses the same checks, downloads the release and verifies its SHA-256 against that release's `SHA256SUMS.txt`. It installs only a newer stable version, only into the currently registered managed copy, and only when no other plugin session or analysis worker holds the shared lock. Local edits block automatic replacement. A failed attempt is not repeated for that installation until the next day; a manual update retries immediately.
- **Off** disables automatic checks and installations. Manual checks still work.

Policy applies to both apps, but each installed copy updates when that app next starts the plugin. The Codex desktop app starts the plugin inside its own package, where writes are virtualized, so a session started by the desktop app only reports the new version and defers installation; run `update.cmd` from Explorer or a normal terminal instead. Sessions started by the Codex CLI in a normal terminal, and Claude Code sessions, can install automatically. There is no background service or scheduled task. Development copies are not automatically checked or updated. After installation, start a new conversation so the host reloads skills and tools; a startup that just applied an automatic update ends with this instruction.

This repository is private. Remote checks/downloads use the **existing GitHub CLI (`gh`) login** when available. The account must have repository access. The updater does not request, read or save a token and never changes repository visibility. Without access, checks report that they are unavailable and the installed plugin continues to work. You can always install a shared ZIP instead. Public repositories can also be checked without `gh`.

Network failure does not prevent ordinary plugin startup. Only published stable releases are eligible; a source commit alone does not trigger an update. ZIP checks reject unexpected versions, unsafe paths, symlinks, duplicate paths and excessive archive sizes. A checksum detects damaged or mismatched downloads; it is not an independent publisher signature.

## Backups and recovery

Installation stages a complete package beside the destination before replacing it. Previous files are retained under `<base>/<app>/backups/<id>/systematic-document-analysis`. Failed copies are retained as `failed-install-<id>` for diagnosis. Routine registration failures restore the previous files and registration; the console reports if recovery itself failed.

A process killed during installation can leave `<base>/<app>/pending-install.json`. This journal records the state before the installation started: the previous source, the backup location, the previous version and whether the plugin was registered. The installer refuses further changes and a managed server refuses to start from that incomplete transaction. Preserve the listed folders; do not delete the record as a shortcut. Backups are not automatically deleted.

Resolve the interruption with `installer.cmd <app> --recover` from any release package. Recovery reads the journal and restores the state it describes: the previous files return from the backup, an incomplete copy is kept as `failed-install-<id>`, and the previous marketplace and plugin registration are restored through the host CLI and verified. A fresh installation that was interrupted ends with nothing registered. If every step had completed except closing the record, recovery verifies the installed copy and closes the record without changing files. Each recovery writes `recovery-<id>.json` beside the journal with the record and the actions taken. If the previous files or source are missing, recovery stops and keeps the record for manual restoration. Analysis data, provider settings and other marketplaces are never touched. Run `installer.cmd` again afterwards to install the package.

Analysis data, provider settings and reader login are outside the managed program copy. Claude reinstalls use `--keep-data`. Run manifests retain the application version and, for managed sessions, the installed package fingerprint. The updater does not upgrade the Claude/Codex host CLI.

Update policy and the shared OS lock live under `%USERPROFILE%/.systematic-document-analysis/maintenance`. Using the user profile avoids different LocalAppData paths in Windows Store apps. `SDA_MAINTENANCE_DIR` is an advanced/test override; every cooperating process must use the same directory. OS locks release automatically after a crash.

## Command-line options

```powershell
.\installer.cmd both
.\installer.cmd codex --replace-source
.\installer.cmd both --repair
.\installer.cmd codex --allow-downgrade
.\installer.cmd codex --move-shadow
.\installer.cmd both --non-interactive
.\installer.cmd claude --recover
.\update.cmd --check
.\update.cmd --install
.\update.cmd --mode notify
.\update.cmd --mode auto
.\update.cmd --mode off
```

Use `--base-dir <folder>` for a custom install location. `--replace-source` changes only this plugin's single-plugin local marketplace registration, after checking both paths. `--repair` replaces same-version files deliberately; `--allow-downgrade` authorises an older version. `--recover` resolves an interrupted installation and installs nothing. `--move-shadow` moves aside a stale Codex desktop copy after installing. These options are independent.

Implementation starts in `bin/installer.py` and `bin/update_plugin.py`; shared process locking and cached diagnostics are in `src/kildeanalyse/maintenance.py`. `tests/test_installer_updates.py` tests transactions and simulated releases; `tests/test_installer_recovery.py` interrupts every installer step and recovers. `tests/prov_installasjon.py` exercises real host CLIs in temporary profiles, including recovery, without using models or user registrations.
