# Start here

Systematic Document Analysis applies agreed criteria consistently across your own documents and keeps quotations, model settings, raw answers and human review together.

1. Extract the Windows ZIP. Double-click **installer.cmd** and choose Claude Code, Codex or both. Python is prepared automatically in a private local environment if needed. Internet is needed for first setup.
2. Choose a reader. For your subscription, double-click **reader_setup.cmd**, choose Codex or Claude Code and follow the sign-in window. Advanced alternative: `./reader_setup.cmd codex --login` or `./reader_setup.cmd claude --login`. The helper installs a missing CLI; you complete the vendor's login. For optional API access, double-click **settings.cmd**, paste your key into the provider's line in Notepad, save and close. Never paste it into chat.
3. For scanned PDFs, double-click **ocr_setup.cmd**. It installs local Tesseract OCR and English/Norwegian language data if missing.
4. Start a new local conversation with the plugin enabled. Open an ordinary working folder, e.g. `Documents/My analysis`, with your source files in a `documents` subfolder. No Git repository or technical folder structure is needed.

The plugin is installed elsewhere. Your working folder holds the documents and a criteria file the assistant can help create. Import only the source folder; subfolders are not traversed automatically. Both hosts share the local analysis store; ask `show_setup` for its exact location.

> Use Systematic Document Analysis on [absolute path to documents]. I want to investigate [question] consistently across the files. Help me define criteria. Inspect extraction and discuss scans, tables, formulas, large files and any sections that deserve priority. Use [reader/model/effort] and report in English. Show the plan and exact input before execution. Preserve full coverage unless we explicitly agree otherwise. Export results with quotations and source locations. Do not record human review on my behalf.

If you do not know which reader/model to select, ask the assistant to explain available choices before creating the plan. It can help run setup locally when permitted, but account sign-in and key entry remain yours.

Optional [example gallery](examples/README.md) has five ready-made folders and prompts. Normal use requires no simulation or example run. [Setup and sharing](docs/SETUP_AND_SHARING.md) explains app catalogs, CLI installation, keys and troubleshooting. The completed key file is private plaintext outside the package: never share it.
