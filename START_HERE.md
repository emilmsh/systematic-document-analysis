# Start with Systematic Document Analysis

1. Install Python 3.12+ and Codex CLI or Claude Code CLI; sign in with your own account.
2. Extract the ZIP, run **installer.cmd** and choose your app (or both).
3. Start a new local conversation with **Systematic Document Analysis** enabled. The first server start installs Python dependencies.

A normal folder of local PDFs with text layers is enough. Supply its full path. The assistant helps you write criteria; no special project structure is required. Subfolders must be supplied separately.

> Use Systematic Document Analysis on the PDFs in [absolute folder path]. Investigate [question]. Help me agree criteria and answer options. Use the CLI reader for my host app with high reasoning effort. Write commentary in English and preserve source quotations. Show the model, plan, text coverage and input package before I approve execution. Then run the material and export answers with quotations and PDF page numbers. Do not record human review on my behalf.

The plan records the reader, model, effort and language (`en` or `nb`). These settings do not inherit the conversation's model. Examples and simulation are optional.

For API readers, choose `openai_api`, `anthropic_api`, `openrouter_api` or `kompatibel_api`, with an explicit provider model ID. Set the corresponding key in Windows user environment variables and restart the app; never paste it into the conversation. API use is separately billed. See [README](README.md) for configuration and limits.

Fresh analysis data lives in `%LOCALAPPDATA%/systematic-document-analysis`; existing OE Kildeanalyse data is reused in its original directory. `show_setup` shows the actual location. Exports include English CSV files, a plan summary and the raw audit trail.

To update, download the [latest release](https://github.com/emilmsh/systematic-document-analysis/releases/latest) and run the installer again. When upgrading from the old name, disable the old plugin after installing this one. Keep the installed copies under LocalAppData; the extracted download can then be deleted.

[Norsk: START_HER.md](START_HER.md) · [Full guide](README.md)
