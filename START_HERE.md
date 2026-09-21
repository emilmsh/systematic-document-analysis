# Start here

Systematic Document Analysis applies agreed criteria consistently across your own documents and keeps quotations, model settings, raw answers and human review together.

Created and developed by **Emil Mathias Strøm Halseth**, with development assistance from **OpenAI Codex** and **Anthropic Claude Code**.

1. Extract the Windows ZIP. Double-click **installer.cmd** and choose Claude Code, Codex or both. Python is prepared automatically in a private local environment if needed. Internet is needed for first setup. You can also paste one of the setup prompts in the [README](README.md#let-your-assistant-do-it) into Claude Code or the ChatGPT app and let the assistant download and verify the release. Do not run installer.cmd from a terminal inside the Codex app; its files would be redirected to the wrong place, and the installer refuses.
2. **Continue in the same installer window.** Choose your reader: **1 = Codex / ChatGPT, 2 = Claude Code, or 3 = Skip (API or later)**. The installer checks existing subscription sign-in and starts sign-in if needed; you complete it in your browser. Wait for confirmation in the installer window. Normal first-time setup only requires **installer.cmd**. If you skip or cancel sign-in, finish later with **reader_setup.cmd**. To switch accounts: `./reader_setup.cmd codex --login` or `./reader_setup.cmd claude --login`. For optional API access, double-click **settings.cmd**, paste your key into the provider's line in Notepad, save and close. Never paste it into chat.
3. **Installation sets up OCR automatically**, including English and Norwegian. No manual PATH or parser setup is needed. If OCR setup is cancelled or fails, use **ocr_setup.cmd** to repair it.
4. Start a new local conversation with the plugin enabled. Open an ordinary working folder, e.g. `Documents/My analysis`, with your source files in a `documents` subfolder. No Git repository or technical folder structure is needed.

The plugin is installed elsewhere. Your working folder holds the documents and a criteria file the assistant can help create. Import only the source folder; subfolders are not traversed automatically. Both hosts share the local analysis store; ask `show_setup` for its exact location.

> Use Systematic Document Analysis. I want to understand how these annual reports describe their use of AI. The files are in the documents folder.

Describe your own task in ordinary language. You do not need criteria ready: the assistant is instructed to propose an approach and ask necessary follow-up questions using your files. It also suggests a reader, model and a new analysis subfolder with Excel results. Before the reader starts, you receive a short plan to inspect and approve, with links to the details. A small pilot is optional. Identify the person responsible for approval; the assistant must not record human review on your behalf.

Optional [example gallery](examples/README.md) has five ready-made folders and prompts. Normal use requires no simulation or example run. [Setup and sharing](docs/SETUP_AND_SHARING.md) explains app catalogs, CLI installation, keys and troubleshooting. The completed key file is private plaintext outside the package: never share it.
