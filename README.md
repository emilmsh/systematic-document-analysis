# Systematic Document Analysis

A plugin for Claude Code and Codex that reads a set of documents against criteria you define, one document at a time, and keeps a record of what the model was given, what it answered, which passages it cited and how a person checked the result.

[Norsk](README.no.md) · [Start here](START_HERE.md) · [Installation and updates](docs/UPDATES.md)

## Quick install — Windows

1. Download the **[Windows ZIP](https://github.com/emilmsh/systematic-document-analysis/releases/latest/download/systematic-document-analysis-windows.zip)** and extract it under Downloads. The current release is **[0.8.5](https://github.com/emilmsh/systematic-document-analysis/releases/tag/v0.8.5)**. Private repository: sign in with access, or use a ZIP shared by a colleague.
2. Open the extracted folder in File Explorer, double-click **installer.cmd**, and choose **1 = Claude Code, 2 = Codex, or 3 = both**. Run as your ordinary Windows user, outside the Codex terminal.
3. For subscription-based reading, double-click **reader_setup.cmd**, choose Claude Code or Codex, and complete sign-in.
4. Start a **new local conversation** in Claude Code's **Code tab** or in Codex and write: **“Use Systematic Document Analysis on the documents in [folder]. Help me choose criteria and show the plan before running.”**

First-time setup requires internet access. The installer provides Python and installs the selected app's command-line tool if it is missing; you do not need to use the terminal yourself.

## Project folder and results

Choose a visible project folder in the conversation. Plans and input previews are saved there
before execution; results arrive in a new snapshot with one Excel workbook, a plan, a start
file, source copies and a separate audit folder. CSV is optional. Start in `START_HERE.md`.
Excel edits do not update recorded results. See [Project files and exports](docs/PROJECT_FILES.md).

## Why use it

A chat assistant can read one report and answer questions about it. It is less useful when the same questions must be answered for forty reports, a stack of tender offers or a folder of workbooks, and the answers will be used later. Then you need to know that every document was read with the same instructions, model and settings, that each answer is tied to a quotation you can look up, and that someone has actually checked the result. Ordinary conversations do not give you that. This plugin does, without leaving the app you already work in.

## What it does

- **Reads files from a folder you choose.** PDF, DOCX, XLSX, CSV/TSV, TXT and Markdown. Scanned PDFs can be OCR-processed locally. Large files are read in bounded pieces and the findings are then combined in one further call, with every call recorded.
- **Applies criteria you define.** A small JSON file lists the questions, the allowed answers and interpretation rules. The assistant helps you write it in conversation; you do not need to write JSON yourself.
- **Runs one document per attempt with fixed settings.** The plan records reader, model, reasoning effort, language and instructions. A named person approves it before anything is read. Changing it creates a new version; earlier attempts are untouched.
- **Stores the evidence.** For every attempt: the exact input, the raw answer, verbatim quotations with their location (PDF page, Word block, sheet and cell range, text line or CSV record), and automatic checks of answer labels, quotations and coverage.
- **Records human review.** A person approves, corrects or rejects each assessment with a reason. Automatic checks are never recorded as human review.
- **Exports to Excel.** One workbook for results, evidence, attempts and reviews, with a separate full audit trail. CSV is optional.

The conversation stays in Claude Code or Codex. The plugin adds the record keeping and the repeatable reading; the assistant still helps you think about the question, the criteria and problem files.

## What it does not do

- It does not summarise across documents. Each file is one unit; comparison is your job, or the assistant's, using the exported results.
- It does not retry, switch model or fall back to a paid API on its own. Errors and timeouts stop the queue and are shown.
- It does not read charts, photographs or embedded objects, and does not recalculate spreadsheet formulas.
- It runs on Windows only and needs a local Python runtime, which the installer provides.

## Installation

The repository is private. Downloading from GitHub needs repository access; a colleague can also be given the ZIP directly.

### Let your assistant do it

Paste one of these into a new conversation. The assistant downloads and verifies the release, and either runs the installer or hands you the one step it must not do itself.

Claude Code:

> Install Systematic Document Analysis for Claude Code. Release page: https://github.com/emilmsh/systematic-document-analysis/releases/latest (private repository; use the existing gh login, or ask me to download the ZIP if you cannot). Download systematic-document-analysis-windows.zip and SHA256SUMS.txt, verify the checksum, extract the ZIP to a folder under my Downloads, run `installer.cmd claude --non-interactive` from that folder and show me the output. Then run `claude plugin list` and confirm that systematic-document-analysis is enabled. Do not change other plugins, settings or files, and do not run reader_setup.cmd or settings.cmd unless I ask.

ChatGPT desktop / Codex:

> Install Systematic Document Analysis for Codex. Release page: https://github.com/emilmsh/systematic-document-analysis/releases/latest (private repository; use the existing gh login, or ask me to download the ZIP if you cannot). Download systematic-document-analysis-windows.zip and SHA256SUMS.txt, verify the checksum and extract the ZIP to a folder under my Downloads. Show me the folder path so I can double-click installer.cmd in File Explorer and choose Codex. Leave that installation step to me. When I confirm, run `codex plugin list` and check that systematic-document-analysis is enabled. Do not change other plugins, settings or files.

After installation, start a new conversation so the app loads the plugin.

### By hand

1. Download the [Windows ZIP](https://github.com/emilmsh/systematic-document-analysis/releases/latest/download/systematic-document-analysis-windows.zip) from the [latest release](https://github.com/emilmsh/systematic-document-analysis/releases/latest) and extract it.
2. Double-click `installer.cmd` in File Explorer and choose Claude Code, Codex or both. It prepares Python 3.12 or newer, installs a missing host CLI, registers the plugin and reports the installation folder.
3. Double-click `reader_setup.cmd` to sign in for subscription-based reading, then start a new local conversation. The first start installs the Python dependencies.

Reading with your subscription uses the app's own CLI. If the CLI is missing, `reader_setup.cmd` installs it; you complete the vendor's sign-in yourself. `ocr_setup.cmd` installs local OCR for scanned PDFs. `settings.cmd` opens a local file for optional API keys.

### Updates

Run `update.cmd` from the installed folder to check for a newer release, install it, or choose notify only (default), automatic or off. Start a new conversation after updating. See [installation and updates](docs/UPDATES.md) for settings and troubleshooting.

## Using it

Put the documents in a folder and open that folder in the app. Then describe the task, for example:

> Use Systematic Document Analysis on the files in C:\Users\me\Documents\Annual reports\documents. I want to know how each organisation reports on its own use of AI. Help me define criteria and answer options. Use codex_cli with gpt-5.6-terra and high reasoning effort, commentary in English. Show the plan, text coverage and the exact input before I approve. Then run all documents, show the answers with quotations and locations, and export the results. Do not record human review on my behalf.

The assistant inspects the extracted text, proposes criteria, shows the plan and the exact input package, and waits for your approval. Runs are then executed one document at a time. You can stop, resume and inspect individual attempts, record your review, and export.

### Hosts and readers

The app you talk to and the model that reads the documents are chosen separately.

| Host (conversation) | Reader (reads each document) |
|---|---|
| Claude Code, Codex desktop | `claude_cli` (default `sonnet`, high), `codex_cli` (default `gpt-5.6-terra`, high), or `openai_api`, `anthropic_api`, `openrouter_api`, `kompatibel_api` with an explicit model ID |

CLI readers use your subscription sign-in and the vendor's agent harness with restricted context and tools. API readers make direct calls and are billed by the provider. The requested model and effort are recorded; whether a provider honoured the effort is only known if it reports it.

### Criteria file

```json
{
  "name": "AI governance",
  "version": "1",
  "criteria": [{
    "id": "ai_policy",
    "name": "Documented AI policy",
    "question": "Does the report explicitly describe an adopted AI policy?",
    "allowed_answers": ["yes", "no", "not_mentioned"],
    "evidence_required_for": ["yes", "no"],
    "rule": "Use no only for an explicit statement that no policy exists."
  }]
}
```

`not_mentioned` requires that the whole document was read. Quotations are kept in the source language; answer labels are stored exactly as agreed. Plans record `language: en` or `nb` for the commentary.

### API keys (optional)

`settings.cmd` opens `%LOCALAPPDATA%\systematic-document-analysis\settings\providers.env` in Notepad. Paste a key after `OPENAI_API_KEY=`, `ANTHROPIC_API_KEY=`, `OPENROUTER_API_KEY=` or `SDA_CUSTOM_API_KEY=` and save. The file is plain text outside the project; do not share it, commit it or ask an assistant to read it. Keys are only used to authenticate requests and are excluded from stored inputs and exports. Environment variables with the same names override the file.

### Data

Analysis data is stored in `%LOCALAPPDATA%\systematic-document-analysis` and shared by both apps. `SDA_DATA` selects another directory. Nothing is moved or deleted automatically; `show_setup` displays the directory in use.

## Documentation

- [Start here](START_HERE.md) and [Start her (norsk)](START_HER.md)
- [Installation and updates](docs/UPDATES.md)
- [Setup and sharing](docs/SETUP_AND_SHARING.md)
- [Supported formats and extraction scope](docs/SOURCE_FORMATS.md)
- [OCR, large documents and the audit trail](docs/DOCUMENT_PROCESSING.md)
- [Five example folders](examples/README.md) with fictional files, draft criteria and prompts. Optional; the plugin is meant for your own documents.

## Development

`src/kildeanalyse/` holds the engine, storage, validation and export, with readers in `adaptere/`. `skills/systematic-document-analysis/SKILL.md` is the host workflow. `bin/installer.py` installs and recovers; `bin/lag_release.py` builds the release ZIP. Tests are in `tests/`; the verification history is in [tests/TESTLOGG.md](tests/TESTLOGG.md). See [DEVELOPMENT.md](DEVELOPMENT.md).

```powershell
./oppsett.cmd
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe bin/lag_release.py
```

Created and developed by Emil Mathias Strøm Halseth, with development assistance from OpenAI Codex and Anthropic Claude Code.
