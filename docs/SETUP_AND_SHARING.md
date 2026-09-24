# Setup and sharing for ordinary desktop users

## What the installer handles

Download and extract the release, then run `installer.cmd`. It reuses Python 3.12+ or downloads a private Python via a pinned, checksum-verified uv bootstrap. Python stays in the user's local application data; no system Python, PATH or Python registry change is needed. The service installs its dependencies into a private virtual environment. Internet is needed for downloads; organisational restrictions may require IT assistance.

The installer prepares separate Claude Code and Codex plugin copies and installs a missing host CLI. In the same window, choose a subscription reader (Codex or Claude Code), independently of the host app, or skip for API access/later setup. The installer installs a missing reader CLI, reuses existing subscription sign-in, or opens the vendor's authentication flow for you to complete. It checks sign-in again before reporting success. Codex can use a private standalone binary; Claude uses the official winget package. Installed versions are reused rather than silently upgraded. A desktop subscription is not proof that its standalone CLI is installed or signed in. A compatible CLI version is still required; `show_setup` reports capability errors before reading.

`installer.cmd reader` remains available for skipped or cancelled sign-in and later reader changes. To explicitly sign in again or switch accounts, run `installer.cmd reader codex --login` or `installer.cmd reader claude --login`. Failed or cancelled sign-in leaves the installed plugin in place; finish reader setup without reinstalling. `installer.cmd --non-interactive` skips reader setup by default. Adding `--reader codex` or `--reader claude` in that mode installs a missing reader CLI and checks existing sign-in, but never opens a login flow; missing sign-in returns an error with instructions. Automatic updates, recovery and package preparation do not start reader setup.

The host assistant can run these local setup helpers when it has terminal permissions, with one exception: a terminal inside the packaged Codex desktop app has file-system virtualization, so anything written below `%LOCALAPPDATA%` lands in the app's LocalCache and later masks the real installation. `installer.cmd` and `installer.cmd update` detect this and refuse. In the ChatGPT/Codex app, let the assistant download, verify and extract the release, then double-click `installer.cmd` yourself. The detailed user guides (USAGE.md and USAGE.no.md) contain ready-made setup prompts for both apps. The assistant cannot grant itself permissions, bypass workspace policy, authenticate as the user or turn an ordinary web chat into a local service. Claude's Code desktop interface and CLI share the underlying engine; the plugin uses a standalone CLI subprocess for worker calls. See [Claude Desktop Code](https://code.claude.com/docs/en/desktop), [Claude installation](https://code.claude.com/docs/en/setup) and [Codex CLI](https://learn.chatgpt.com/docs/codex/cli).

For an existing installation, version checks and source selection happen before files are replaced. `installer.cmd update` in the installed folder controls update checks and optional automatic installation. See [installation and updates](UPDATES.md) for source conflicts, backups, private GitHub access and command-line options.

## Optional API keys without environment-variable setup

Double-click `installer.cmd` and choose Sign-in and settings → API settings, or run `installer.cmd settings` in a terminal. A prepared file opens in Notepad outside the project, at `%LOCALAPPDATA%/systematic-document-analysis/settings/providers.env`. Fill only the provider you want, save and close. An existing file is preserved. Blank providers stay disabled; CLI subscription reading requires no API key.

The assistant may open the editor but should never read the completed file, print it or ask you to paste its contents into chat. The file is plaintext, not a password vault, and other software running as your user can read it. Keep it outside synced/shared folders, do not commit or share it, and revoke a key with the provider if exposed. Shared templates must always be empty. Environment variables override file values for advanced installations. File edits are picked up on subsequent checks/calls without restarting the app.

Keys are used only for authentication. Plans, previews, history and exports exclude authentication headers; known key echoes in provider responses are masked. CLI subprocesses do not receive API keys. API charges are separate from the host subscription.

## App-native installation and sharing

The vendors support app-facing plugin installation, so manual ZIP delivery need not be the final distribution model:

- **Claude Code / Desktop Code:** users can install plugins from configured marketplaces through the Plugins interface; a shared Git marketplace can distribute this repository. Private Git access still needs authentication. See [Claude plugin discovery](https://code.claude.com/docs/en/discover-plugins).
- **ChatGPT and Codex:** the Plugins catalog supports personal, shared and workspace plugins. Workspace publication requires an administrator and may be restricted by policy. Plugin compatibility depends on the app surface and available runtime. See [Plugins in ChatGPT and Codex](https://learn.chatgpt.com/docs/plugins) and [building and publishing plugins](https://developers.openai.com/plugins/build/plugins).

This release contains compatible plugin manifests and a local marketplace. Its verified installation route is **Windows local Codex and Claude Code through installer.cmd**. It has not been published to a workspace catalog/public directory, and direct installation into every ChatGPT or Claude surface has not been tested. A local Windows MCP process needs a local runtime; publishing its manifest does not deploy a web server. Public-directory distribution can require different hosting and review.

For a colleague: share the public Releases link or the ZIP with its short bilingual `README.md`. Share neither installed app profiles nor the analysis data/settings directories. For a team catalog later: have a workspace administrator publish an approved package and verify local startup in the target app before offering a one-click workflow.

## Documents and first run

Choose any ordinary working folder. Put source files in a subfolder and let the assistant help create criteria beside it. Inspect extraction before agreeing the plan. Normal installation includes Tesseract OCR and verifies English/Norwegian data; `installer.cmd ocr` repairs OCR if setup was interrupted. Local reader sessions include file parsing, PDF page images and OCR tools in a fresh per-call workspace. [Supported formats](SOURCE_FORMATS.md) and [document processing](DOCUMENT_PROCESSING.md) explain extraction limits, source previews and large-file budgets. The [example gallery in the repository](https://github.com/emilmsh/systematic-document-analysis/tree/main/examples) provides optional starting material; it is not installed with the plugin.

Reader discovery checks the running process's PATH, the current Windows machine/user PATH, standard private/WinGet/native/npm locations and the reader's WinGet package directory. The installer and plugin use the same lookup, including immediately after installation, so an old PATH in an already-open app does not require manual PATH editing. Setup prints the selected executable before checking sign-in. SDA does not change the global PATH. An explicit `SDA_CLAUDE_BIN` or `SDA_CODEX_BIN` override takes precedence.

If setup fails, retain the visible error and ask the assistant to diagnose it. Do not share a completed key file or authentication tokens. Restart the host conversation after a plugin update.
