# Installation and updates

Run `installer.cmd` from an extracted release and choose Install to install or update Claude Code, Codex or both. It reports each app separately. Use File Explorer or a normal terminal as your ordinary Windows user. The main menu has three choices: Install, Sign-in and settings, and Update or repair. Reader sign-in and API settings are under Sign-in and settings; updates, plugin/OCR repair and recovery are under Update or repair. Choose 0 in a submenu to go back. After each action, choose 1 to return to the start menu or 0 to exit; this also works after an incomplete action. Direct commands run once and exit. Direct commands remain available; `installer.cmd --help` lists them.

After successful installation, the interactive installer lets you choose Codex, Claude Code, both readers, or skip for API/later setup. It reuses existing subscription sign-in or starts login and verifies the result. It then asks whether to check for and install the latest available reader CLI version. Answering no leaves the CLI as it is; answering yes runs the separate reader updater for the selected reader(s). This happens after the installation lock is released. Failed or cancelled login leaves the plugin installed; finish with `installer.cmd reader`. A failed reader CLI update leaves the installed plugin and completed sign-in in place; retry with `installer.cmd reader <reader> --update`. Direct installations with an explicit `--reader`, noninteractive installations, `installer.cmd update`, automatic updates, `--recover` and `--prepare-only` do not ask this update question.

Normal installation also checks local Tesseract OCR and installs missing English/Norwegian support. `--skip-ocr` explicitly skips that step. Updating an existing installation does not run onboarding; use `installer.cmd ocr` if that installation has not yet set up OCR.

## Closing active plugin connections

A manual installation, recovery or `installer.cmd update --install` asks this plugin's connections to close automatically. It blocks new connections, finishes current tool calls and the current document (including its constituent model calls), saves their results, then stops the queue before the next document. Remaining documents stay pending and can be resumed explicitly after the update. Claude Code and Codex themselves stay open; other plugins are unaffected. Start a new conversation afterwards to load the updated tools and skill.

The installer waits up to **60 seconds** for exclusive access. If work takes longer, it leaves the installed files unchanged and explains how to retry. No process is forcibly terminated. The request is an OS lock that disappears automatically if the installer exits or crashes; it cannot leave a stale shutdown flag. Both host installations share one gate, so connections cannot reopen between the two updates.

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
| Started from a terminal inside the Claude or Codex desktop app | Refuse: writes would be virtualized. Run from Explorer or a normal terminal. |

The packaged Codex desktop app (Microsoft Store/MSIX) redirects writes below `%LOCALAPPDATA%` into `Packages\OpenAI.Codex_*\LocalCache\Local` and reads a merged view in which those files win. A plugin copy installed from inside a Codex conversation lands there and masks the registered installation for the desktop app, even after the real files are replaced. The installer detects such a shadow for the Codex target and, with `--move-shadow` or an interactive yes, renames it to `systematic-document-analysis.shadow-<version>-<id>` after a successful installation. Start a new Codex conversation afterwards. The Claude desktop app is packaged the same way: the installer and updater also refuse to run inside it, but shadow detection currently covers the Codex package only.

The default for source-switch, repair, downgrade and shadow questions is **keep the existing installation**. Noninteractive calls stop with an actionable error unless the corresponding option is supplied. The installer never removes other marketplaces.

## Update menu

Run **installer.cmd update from the installed plugin folder**, printed at the end of installation. Choose check now, update now, notify only, automatic, or off. `show_setup` also displays the cached update status.

- **Notify only** is the default. A managed plugin checks GitHub at most once a day when starting a session. A newer stable release is reported in startup diagnostics and `show_setup`.
- **Automatic** uses the same checks, downloads the release and verifies its SHA-256 against that release's `SHA256SUMS.txt`. It installs only a newer stable version, only into the currently registered managed copy, and only when no other plugin session or analysis worker holds the shared lock. Local edits block automatic replacement. A failed attempt is not repeated for that installation until the next day; a manual update retries immediately.
- **Off** disables automatic checks and installations. Manual checks still work.

Policy applies to both apps, but each installed copy updates when that app next starts the plugin. The Claude and Codex desktop apps start the plugin inside their own packages, where writes are virtualized, so a session started by a desktop app only reports the new version and defers installation; run `installer.cmd update` from Explorer or a normal terminal instead. Sessions started by the Claude Code or Codex CLI in a normal terminal can install automatically. There is no background service or scheduled task. Development copies are not automatically checked or updated. After installation, start a new conversation so the host reloads skills and tools; a startup that just applied an automatic update ends with this instruction.

The repository is public, so update checks and downloads need no GitHub account. When the GitHub CLI (`gh`) is signed in, its existing login is used; the updater never requests, reads or saves a token. Without network access, checks report that they are unavailable and the installed plugin continues to work. You can always install a downloaded ZIP instead.

Network failure does not prevent ordinary plugin startup. Only published stable releases are eligible; a source commit alone does not trigger an update. ZIP checks reject unexpected versions, unsafe paths, symlinks, duplicate paths and excessive archive sizes. A checksum detects damaged or mismatched downloads; it is not an independent publisher signature.

## Backups and recovery

Installation stages a complete package beside the destination before replacing it. Previous files are retained under `<base>/<app>/backups/<id>/systematic-document-analysis`. Failed copies are retained as `failed-install-<id>` for diagnosis. Routine registration failures restore the previous files and registration; the console reports if recovery itself failed.

A process killed during installation can leave `<base>/<app>/pending-install.json`. This journal records the state before the installation started: the previous source, the backup location, the previous version and whether the plugin was registered. The installer refuses further changes and a managed server refuses to start from that incomplete transaction. Preserve the listed folders; do not delete the record as a shortcut. Backups are not automatically deleted.

Resolve the interruption with `installer.cmd <app> --recover` from any release package. Recovery reads the journal and restores the state it describes: the previous files return from the backup, an incomplete copy is kept as `failed-install-<id>`, and the previous marketplace and plugin registration are restored through the host CLI and verified. A fresh installation that was interrupted ends with nothing registered. If every step had completed except closing the record, recovery verifies the installed copy and closes the record without changing files. Each recovery writes `recovery-<id>.json` beside the journal with the record and the actions taken. If the previous files or source are missing, recovery stops and keeps the record for manual restoration. Analysis data, provider settings and other marketplaces are never touched. Run `installer.cmd` again afterwards to install the package.

Analysis data, provider settings and reader login are outside the managed program copy. Claude reinstalls use `--keep-data`. Run manifests retain the application version and, for managed sessions, the installed package fingerprint. `installer.cmd update` updates this plugin. To update a reader CLI separately, choose **Check/update reader CLIs** under **Update or repair**, or run `installer.cmd reader claude --update`, `installer.cmd reader codex --update`, or `installer.cmd reader both --update`. Claude Code uses its own updater and verifies the reported version afterwards. A Codex CLI installed privately by this installer is downloaded from the latest official release and checked against the release asset's SHA-256 before replacement; the previous binary is restored if the new one fails its version check. For a Codex CLI owned by another installer or the desktop app, the command shows the current version and points to that installer's update instructions without replacing its files. The installer also prints the CLI update command during reader setup. Reader CLI updates do not change plugin update policy or login.

Update policy and the shared OS lock live under `%USERPROFILE%/.systematic-document-analysis/maintenance`. Using the user profile avoids different LocalAppData paths in Windows Store apps. `SDA_MAINTENANCE_DIR` is an advanced/test override; every cooperating process must use the same directory. OS locks release automatically after a crash.

## Command-line options

```powershell
.\installer.cmd both
.\installer.cmd claude --reader claude
.\installer.cmd codex --reader none
.\installer.cmd codex --replace-source
.\installer.cmd both --repair
.\installer.cmd codex --allow-downgrade
.\installer.cmd codex --move-shadow
.\installer.cmd both --non-interactive
.\installer.cmd claude --recover
.\installer.cmd update --check
.\installer.cmd update --install
.\installer.cmd update --mode notify
.\installer.cmd update --mode auto
.\installer.cmd update --mode off
.\installer.cmd reader both --update
```

Use `--base-dir <folder>` for a custom install location. `--replace-source` changes only this plugin's single-plugin local marketplace registration, after checking both paths. `--repair` replaces same-version files deliberately; `--allow-downgrade` authorises an older version. `--recover` resolves an interrupted installation and installs nothing. `--move-shadow` moves aside a stale Codex desktop copy after installing. These options are independent.

`--reader claude`, `--reader codex` or `--reader both` selects the subscription reader without the menu; `--reader none` skips reader setup. Without `--reader`, `--non-interactive` skips reader setup and prints follow-up instructions. With an explicit reader, noninteractive mode installs a missing CLI and checks existing subscription sign-in, returning an error if it cannot confirm it; it never opens a browser for login. `--reader` cannot be combined with `--recover` or `--prepare-only`.

Implementation starts in `bin/installer.py` and `bin/update_plugin.py`; shared process locking and cached diagnostics are in `src/kildeanalyse/maintenance.py`. `tests/test_installer_updates.py` tests transactions and simulated releases; `tests/test_installer_recovery.py` interrupts every installer step and recovers. `tests/prov_installasjon.py` exercises real host CLIs in temporary profiles, including recovery, without using models or user registrations.
