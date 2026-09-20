# Setup and sharing for ordinary desktop users

## What the installer handles

Download and extract the release, then run `installer.cmd`. It reuses Python 3.12+ or downloads a private Python via a pinned, checksum-verified uv bootstrap. Python stays in the user's local application data; no system Python, PATH or Python registry change is needed. The service installs its dependencies into a private virtual environment. Internet is needed for downloads; organisational restrictions may require IT assistance.

The installer prepares separate Claude Code and Codex plugin copies and installs a missing host CLI. Double-click `reader_setup.cmd` to choose a reader and sign in. Command-line alternatives are `reader_setup.cmd codex --login` and `reader_setup.cmd claude --login`. Codex can use a private standalone binary; Claude uses the official winget package. Installed versions are reused rather than silently upgraded. Login opens the vendor's authentication flow, which the user must complete. A desktop subscription is not proof that its standalone CLI is installed or signed in. A compatible CLI version is still required; `show_setup` reports capability errors before reading.

The host assistant can run these local setup helpers when it has terminal permissions. It cannot grant itself permissions, bypass workspace policy, authenticate as the user or turn an ordinary web chat into a local service. Claude's Code desktop interface and CLI share the underlying engine; the plugin uses a standalone CLI subprocess for worker calls. See [Claude Desktop Code](https://code.claude.com/docs/en/desktop), [Claude installation](https://code.claude.com/docs/en/setup) and [Codex CLI](https://learn.chatgpt.com/docs/codex/cli).

For an existing installation, version checks and source selection happen before files are replaced. `update.cmd` in the installed folder controls update checks and optional automatic installation. See [installation and updates](UPDATES.md) for source conflicts, backups, private GitHub access and command-line options.

## Optional API keys without environment-variable setup

Double-click `settings.cmd`. A prepared file opens in Notepad outside the project, at `%LOCALAPPDATA%/systematic-document-analysis/settings/providers.env`. Fill only the provider you want, save and close. An existing file is preserved. Blank providers stay disabled; CLI subscription reading requires no API key.

The assistant may open the editor but should never read the completed file, print it or ask you to paste its contents into chat. The file is plaintext, not a password vault, and other software running as your user can read it. Keep it outside synced/shared folders, do not commit or share it, and revoke a key with the provider if exposed. Shared templates must always be empty. Environment variables override file values for advanced installations. File edits are picked up on subsequent checks/calls without restarting the app.

Keys are used only for authentication. Plans, previews, history and exports exclude authentication headers; known key echoes in provider responses are masked. CLI subprocesses do not receive API keys. API charges are separate from the host subscription.

## App-native installation and sharing

The vendors support app-facing plugin installation, so manual ZIP delivery need not be the final distribution model:

- **Claude Code / Desktop Code:** users can install plugins from configured marketplaces through the Plugins interface; a shared Git marketplace can distribute this repository. Private Git access still needs authentication. See [Claude plugin discovery](https://code.claude.com/docs/en/discover-plugins).
- **ChatGPT and Codex:** the Plugins catalog supports personal, shared and workspace plugins. Workspace publication requires an administrator and may be restricted by policy. Plugin compatibility depends on the app surface and available runtime. See [Plugins in ChatGPT and Codex](https://learn.chatgpt.com/docs/plugins) and [building and publishing plugins](https://developers.openai.com/plugins/build/plugins).

This release contains compatible plugin manifests and a local marketplace. Its verified installation route is **Windows local Codex and Claude Code through installer.cmd**. It has not been published to a workspace catalog/public directory, and direct installation into every ChatGPT or Claude surface has not been tested. A local Windows MCP process needs a local runtime; publishing its manifest does not deploy a web server. Public-directory distribution can require different hosting and review. Keep the repository private unless its owner explicitly chooses otherwise.

For a colleague today: share the ZIP and `START_HER.md`/`START_HERE.md`, or grant access to the private repository's Releases. Share neither installed app profiles nor the analysis data/settings directories. For a team catalog later: have a workspace administrator publish an approved package and verify local startup in the target app before offering a one-click workflow.

## Documents and first run

Choose any ordinary working folder. Put source files in a subfolder and let the assistant help create criteria beside it. Inspect extraction before agreeing the plan. Run `ocr_setup.cmd` once for scanned PDFs; it installs local Tesseract and English/Norwegian data. [Supported formats](SOURCE_FORMATS.md) and [document processing](DOCUMENT_PROCESSING.md) explain extraction limits, source previews and large-file budgets. The [example gallery](../examples/README.md) provides optional starting material.

If setup fails, retain the visible error and ask the assistant to diagnose it. Do not share a completed key file or authentication tokens. A missing CLI after winget installation may require reopening the terminal to refresh PATH. Restart the host conversation after a plugin update.
