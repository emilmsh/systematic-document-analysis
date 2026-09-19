# Systematic Document Analysis

**Analyse documents against agreed criteria, with source quotations, human review and an audit trail. Work in English or Norwegian, in Codex or Claude Code.**

Apply one agreed analysis routine to a list of files with a shared structure: reports, documents, workbooks or tabular records. Define the common fields, criteria and interpretation rules before execution. File format determines extraction and source references, not the analysis method. Discuss the question in your app, agree on a plan, choose a reader and inspect its answers. Each document gets a separate recorded attempt. Export the results for Excel or further reporting. Examples and simulation are optional.

[Norsk veiledning](README.no.md) · [Start here](START_HERE.md) · [Start her på norsk](START_HER.md)

## Download and install

- **[Latest release](https://github.com/emilmsh/systematic-document-analysis/releases/latest)**
- **[Windows ZIP for both apps](https://github.com/emilmsh/systematic-document-analysis/releases/latest/download/systematic-document-analysis-windows.zip)**

This repository is private. Colleagues need repository access to download from GitHub; you can also share the ZIP directly. It contains no credentials, source documents or analysis data.

1. Install Python 3.12+ and the CLI for your host app: Codex and/or Claude Code. The CLI must be on PATH. Sign in with your own account.
2. Extract the ZIP and run `installer.cmd`. Choose Claude Code, Codex or both. PowerShell alternatives: `./installer.cmd claude`, `./installer.cmd codex`, `./installer.cmd both`.
3. Start a new local conversation with **Systematic Document Analysis** enabled. The first server start installs Python dependencies from PyPI.

The installer keeps separate copies in `%LOCALAPPDATA%/systematic-document-analysis/plugins/<app>/systematic-document-analysis`, registered under `systematic-document-analysis-local`. Keep these installed copies; you can delete the extracted download after installation. To update, run the new installer and start a new conversation. A conflicting marketplace registered from another directory is reported without replacing it.

**Upgrading from OE Kildeanalyse:** install the new package, then disable the old plugin in each app to avoid loading two servers. Existing analysis databases are reused in their original location; they are not moved or rewritten. Old tool names, criteria fields and environment variables remain supported. See [compatibility](#data-and-compatibility).

## Two independent choices

| Layer | Choices | Role |
|---|---|---|
| Host / orchestrator | Codex desktop local plugin, or Claude Code | Conversation, criteria, planning, approval and review |
| Reader | Codex CLI, Claude Code CLI, OpenAI API, Anthropic API, OpenRouter, compatible API | One document and one recorded attempt at a time |

Both hosts use the same MCP tools and workflow. This is a local Codex plugin, not an integration into ordinary ChatGPT web chat or Claude Desktop. Reader model settings do not inherit the host conversation's settings.

CLI readers include the vendor's agent harness, with context and tools restricted by the adapter. API readers make a direct call without a tool loop. The same model name and effort do not guarantee equivalent behaviour across these paths.

## Start with your documents

Supply a list of local files or a normal folder. PDF, DOCX, XLSX, CSV/TSV, TXT and Markdown are supported. No Git repository or special filenames are required. Folder import includes supported files directly inside the folder; supply subfolders separately. Each whole file is one analysis unit. Inspect the source profiles and agree how structural differences will be handled. See [supported formats and extraction scope](docs/SOURCE_FORMATS.md).

```text
My analysis/
  documents/
    report-a.pdf
    report-b.pdf
  criteria.json       # the assistant can create this with you
```

Open this working folder in the host app and grant it access to your documents and permission to write the criteria file. The plugin itself is installed elsewhere.

> Use Systematic Document Analysis on the files in [absolute folder path]. Investigate [question]. Help me define criteria and answer options. Use codex_cli with gpt-5.6-terra and high reasoning effort. Write commentary in English. Show the plan, text coverage and exact input package before I approve execution. Then run the documents, show answers with quotations and source locations, and export the results. Do not register human review on my behalf.

For Claude, you can choose `claude_cli`, model `sonnet`, effort `high`. Either reader works from either host.

## Languages and criteria

The assistant responds in your language. Each plan records `language: en` or `nb` for reader commentary and notes. Quotations remain verbatim in the source language; answer labels stay exactly as agreed. A language change creates a new plan version. Older plans without a language field are treated as Norwegian.

Criteria files can use English or existing Norwegian keys. For example:

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

`not_mentioned` and `not_reported` require full document coverage, like their Norwegian equivalents. The legacy marker `<heltall>` allows integer answers. English tools accept `engine_settings` with `max_output_tokens`, `timeout_seconds`, `base_url` and `provider`; existing Norwegian setting names also work. Do not supply API keys through tools or criteria files.

English MCP tools are the primary interface. Norwegian tools remain as compatibility aliases. Some stored status codes and diagnostics are still Norwegian; the assistant explains them in your language. The internal Python module and audit schema retain their original names for compatibility.

## Models, review and export

| Reader engine | Default model | Default effort |
|---|---|---|
| `claude_cli` | `sonnet` | `high` |
| `codex_cli` | `gpt-5.6-terra` | `high` |
| `openai_api`, `anthropic_api`, `openrouter_api`, `kompatibel_api` | Explicit provider model ID required | `standard` (parameter omitted) |

Choose model and effort in the plan. Supported requested levels depend on the engine and model: `low`, `medium`, `high`, `xhigh`, `max`; Codex CLI also allows `ultra`. OpenAI/OpenRouter/compatible APIs additionally accept `none` and `minimal` where supported. An alias such as `sonnet` is not a pinned model version. The requested settings are recorded; actual effort remains unknown when the provider does not report it. The default timeout is 600 seconds per document.

Inspect and approve the plan before execution. Changes create a new version without changing earlier attempts. Automatic checks validate answer labels, source quotes and coverage of extracted source units; they do not establish human review. A person can approve, correct or reject assessments with a recorded reason. Original answers remain available.

Exports include English `results.csv`, `evidence.csv`, `attempts.csv`, `reviews.csv`, `README.md` and `plan-summary.md`, alongside legacy files and the raw audit trail. CSV uses semicolons and UTF-8 with BOM. English CSV headers are translated; recorded labels, quotations and status codes are preserved, with a legend in the export README. Editing an export does not alter the authoritative database.

## Optional API keys

| Reader | Local environment variable | Protocol |
|---|---|---|
| `openai_api` | `OPENAI_API_KEY` | OpenAI Responses |
| `anthropic_api` | `ANTHROPIC_API_KEY` | Anthropic Messages |
| `openrouter_api` | `OPENROUTER_API_KEY` | OpenRouter Chat Completions |
| `kompatibel_api` | `SDA_CUSTOM_API_KEY` | OpenAI-compatible Chat Completions |

Set keys using Windows **user environment variables**, then fully restart the host app. Do not paste keys into conversations, criteria or plans. `show_setup` checks local availability without API calls. Environment variables are local configuration, not an encrypted vault. API use is billed separately by the chosen provider.

Keys authenticate requests and are excluded from stored inputs and exports; known key echoes are masked. CLI subprocesses strip API keys and require subscription sign-in. Configuring a key does not switch the selected reader.

API plans show the recipient endpoint, explicit model, effort and output-token budget (default 16384). The exact request body without authentication headers is previewed, hashed and exported. Reported model, request ID and usage are retained when available. Unsupported parameters fail visibly instead of being silently removed.

OpenRouter accepts an optional `provider`; otherwise it chooses the provider for the named model. Requests require parameter support and disable provider fallbacks. Automatic model routing and model variant suffixes are unsupported. Requested effort may be translated by OpenRouter. Anthropic uses adaptive thinking when explicit effort is requested, requiring a model that supports it.

For `kompatibel_api`, set an explicit HTTPS `base_url`, e.g. `https://provider.example/v1`. The provider must implement `/chat/completions` and JSON-schema `response_format`, plus `reasoning_effort` when requested. Compatibility is not a claim that every provider or model has been tested. Redirects and environment proxy settings are disabled.

Errors, quota stops, timeouts and cancellation stop the queue without automatic retry or engine switching. A cancelled connection does not guarantee the provider stopped processing or billing. API adapters are locally checked with fake HTTP transport; no paid calls were made for these checks.

## Data and compatibility

Fresh installations use `%LOCALAPPDATA%/systematic-document-analysis` for analysis data. Both hosts share this store. `SDA_DATA` selects a different directory. If the legacy `%LOCALAPPDATA%/oe-kildeanalyse/kildeanalyse.sqlite` exists, it is reused. If both default stores contain databases, choose explicitly with `SDA_DATA`; neither is merged or deleted.

Legacy `OE_KILDEANALYSE_DATA` and `OE_KILDEANALYSE_CUSTOM_API_KEY` remain fallback aliases. Advanced runtime overrides `OE_KILDEANALYSE_PYTHON`, `OE_KILDEANALYSE_CODEX_BIN` and `OE_KILDEANALYSE_CLAUDE_BIN` retain their names. The internal module `kildeanalyse`, SQLite filename, technical engine IDs and recorded schemas remain stable. Imported source copies and historical raw attempts are not rewritten. Use `show_setup` to see the actual data directory; export returns its exact output path.

## Limits and optional examples

Windows is supported. Extraction limits differ by format: Word uses body paragraphs/tables, Excel uses cell contents and stored formula caches, and PDF requires a text layer. Images and embedded objects are not analysed. OCR, automatic chunking of large files, row/sheet selection as separate runs and cross-document synthesis are not implemented. Entire extracted documents are sent to the reader and may exceed its context window; long previews can be truncated. CLI restrictions do not provide full operating-system isolation. The host runs as the same local user and can access the data directory outside MCP.

Five optional Norwegian annual reports are listed in [the source manifest](eksempler/arsrapporter-2024/kilder.json), with a [Norwegian starting task](eksempler/arsrapporter-2024/STARTPROMPT.md). Download using `python bin/hent_arsrapporter.py`; PDFs stay outside Git and releases. The selection is illustrative, not representative. Synthetic fixtures are developer aids, never mandatory for normal work.

## Development

- `src/kildeanalyse/`: shared engine, storage, validation and export; `adaptere/` contains readers.
- `skills/systematic-document-analysis/SKILL.md`: bilingual host workflow, written in English.
- `bin/installer.py`: common installer; `bin/lag_release.py`: clean Windows ZIP and SHA-256.
- `tests/`: local checks; `dist/v<version>/`: generated packages, ignored by Git.
- [DEVELOPMENT.md](DEVELOPMENT.md): current decisions and development guide. [Test log](tests/TESTLOGG.md): verification history.

```powershell
./oppsett.cmd
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe bin/lag_release.py
.venv/Scripts/python.exe tests/prov_plugin.py
.venv/Scripts/python.exe tests/prov_installasjon.py
```

Primary documentation and new public interfaces are English. Norwegian user instructions remain available. Legacy internal names are migrated only when there is a concrete benefit and a compatibility path.
