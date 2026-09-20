# Systematic Document Analysis

**Analyse documents against agreed criteria, with source quotations, human review and an audit trail. Work in English or Norwegian, in Codex or Claude Code.**

Codex and Claude Code are useful across a wide range of tasks: exploring questions, inspecting files, writing code and making reasoned decisions. Some work needs more control and traceability than an ordinary conversation conveniently provides. When the same criteria must be applied to dozens of reports, offers, workbooks or records, you need to know exactly what each reader received, which settings it used, what it answered and how a person reviewed it.

**Systematic Document Analysis adds that structure to the tools you already use.** Keep the host's conversational workflow, tools and judgment; add versioned criteria, explicit model choices, consistent document processing and a source-to-result audit trail. The assistant can suggest how to handle an unforeseen file problem within your instructions. Explicit choices about models, priorities, scope and reporting stay visible and take precedence. Reader calls are deliberately bounded, so host flexibility does not mean unrestricted tools in every worker call.

Apply one agreed analysis routine to a list of files with a shared structure: reports, documents, workbooks or tabular records. Define the common fields, criteria and interpretation rules before execution. File format determines extraction and source references, not the analysis method. Discuss the question in your app, agree on a plan, choose a reader and inspect its answers. Each document gets a separate recorded attempt. Export the results for Excel or further reporting. Examples and simulation are optional.

[Norsk veiledning](README.no.md) · [Start here](START_HERE.md) · [Start her på norsk](START_HER.md)

Created and developed by **Emil Mathias Strøm Halseth**, with development assistance from **OpenAI Codex** and **Anthropic Claude Code**.

## Download and install

- **[Latest release](https://github.com/emilmsh/systematic-document-analysis/releases/latest)**
- **[Windows ZIP for both apps](https://github.com/emilmsh/systematic-document-analysis/releases/latest/download/systematic-document-analysis-windows.zip)**

This repository is private. Colleagues need repository access to download from GitHub; you can also share the ZIP directly. It contains fictional example files, but no credentials, private source documents or analysis data.

1. Extract the ZIP and run `installer.cmd`. Choose Claude Code, Codex or both. No manual Python installation is required: an existing suitable Python is reused, or a private runtime is downloaded without changing system Python or PATH.
2. The installer prepares the plugin and installs a missing host CLI. For a subscription reader, double-click `reader_setup.cmd`, choose Codex or Claude Code and complete the vendor's sign-in yourself. API readers are optional; use `settings.cmd` to open a prepared local key file.
3. Start a new local conversation with **Systematic Document Analysis** enabled. First use downloads Python dependencies. For scanned PDFs, run `ocr_setup.cmd` once.

The installer keeps separate copies in `%LOCALAPPDATA%/systematic-document-analysis/plugins/<app>/systematic-document-analysis`, registered under `systematic-document-analysis-local`. Keep these installed copies; the extracted download can be removed. Run a new release's installer to update. Conflicting registrations are reported without replacement.

Plugins can also be installed and shared through the vendors' app interfaces and marketplaces. This project's verified route is the Windows local installer for Codex and Claude Code. It is not yet published to a workspace or public app catalog. App-native distribution can remove manual ZIP handling, but a local service still needs a local runtime and reader credentials. See [simple setup and app sharing](docs/SETUP_AND_SHARING.md).

## Two independent choices

| Layer | Choices | Role |
|---|---|---|
| Host / orchestrator | Codex desktop local plugin, or Claude Code | Conversation, criteria, planning, approval and review |
| Reader | Codex CLI, Claude Code CLI, OpenAI API, Anthropic API, OpenRouter, compatible API | One document and one recorded attempt at a time |

Both hosts use the same MCP tools and workflow. This package runs a local MCP service. Codex desktop and Claude Code are the verified hosts; a ChatGPT web conversation alone cannot launch this Windows service. Claude Desktop Code and ChatGPT/Codex plugin interfaces offer app installation routes, subject to their catalog, workspace and local-runtime support. Reader model settings do not inherit the host conversation's settings.

CLI readers include the vendor's agent harness, with context and tools restricted by the adapter. API readers make direct calls without a model tool loop. Shared local extraction, OCR and bounded reading prepare inputs for both. The same model name and effort do not guarantee equivalent behaviour across these paths.

## Start with your documents

Supply a list of local files or a normal folder. PDF, DOCX, XLSX, CSV/TSV, TXT and Markdown are supported. No Git repository or special filenames are required. Folder import includes supported files directly inside the folder; supply subfolders separately. Each whole file is one analysis unit. Inspect source profiles and extracted units (`inspect_source` can also save a complete Markdown inspection copy). Discuss likely challenges: scans, tables, formula caches, cross-references, long appendices and important sections. Agree how structural differences and uncertainty will be handled. See [supported formats and extraction scope](docs/SOURCE_FORMATS.md).

```text
My analysis/
  documents/
    report-a.pdf
    report-b.pdf
  criteria.json       # the assistant can create this with you
```

Open this working folder in the host app and grant it access to your documents and permission to write the criteria file. The plugin itself is installed elsewhere.

> Use Systematic Document Analysis on the files in [absolute folder path]. Investigate [question]. Help me define criteria and answer options. Use codex_cli with gpt-5.6-terra and high reasoning effort. Write commentary in English. Discuss expected file challenges and sections worth prioritising. Show the plan, text coverage and exact input package before I approve execution. Then run the documents, show answers with quotations and source locations, and export the results. Do not register human review on my behalf.

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

Run **`settings.cmd`**. It opens a prepared file in Notepad; paste a key after the appropriate `=`, save and close. Leave unused providers empty. The file lives outside the project and plugin at `%LOCALAPPDATA%/systematic-document-analysis/settings/providers.env`. It is read when needed, so no host restart is required for file edits. Existing files are never overwritten. The [blank template](docs/providers.env.example) contains no secrets.

Windows environment variables remain an advanced alternative and override file values. Do not paste keys into chat, criteria or plans, and do not ask an assistant to read the completed file. A local plaintext file is **not an encrypted vault**: other processes running as your user can read it. Keep it outside shared/cloud-synced folders; never include it in a ZIP or commit. `show_setup` reports availability, never the key. API use is billed separately by the chosen provider.

Keys authenticate requests and are excluded from stored inputs and exports; known key echoes are masked. CLI subprocesses strip API keys and require subscription sign-in. Configuring a key does not switch the selected reader.

API plans show the recipient endpoint, explicit model, effort and output-token budget (default 16384). The exact request body without authentication headers is previewed, hashed and exported. Reported model, request ID and usage are retained when available. Unsupported parameters fail visibly instead of being silently removed.

OpenRouter accepts an optional `provider`; otherwise it chooses the provider for the named model. Requests require parameter support and disable provider fallbacks. Automatic model routing and model variant suffixes are unsupported. Requested effort may be translated by OpenRouter. Anthropic uses adaptive thinking when explicit effort is requested, requiring a model that supports it.

For `kompatibel_api`, set an explicit HTTPS `base_url`, e.g. `https://provider.example/v1`. The provider must implement `/chat/completions` and JSON-schema `response_format`, plus `reasoning_effort` when requested. Compatibility is not a claim that every provider or model has been tested. Redirects and environment proxy settings are disabled.

Errors, quota stops, timeouts and cancellation stop the queue without automatic retry or engine switching. A cancelled connection does not guarantee the provider stopped processing or billing. API adapters are locally checked with fake HTTP transport; no paid calls were made for these checks.

## Local data and upgrades

The default analysis store is `%LOCALAPPDATA%/systematic-document-analysis`. Both hosts share it. `SDA_DATA` explicitly selects another directory. Version 0.8 removes former brand aliases and automatic discovery of earlier data locations. To use an earlier store, point `SDA_DATA` at it before starting the host; no existing store is moved, merged or deleted. `show_setup` displays the actual directory.

Advanced overrides are `SDA_PYTHON`, `SDA_CODEX_BIN`, `SDA_CLAUDE_BIN`, `SDA_TESSERACT_BIN` and `SDA_SETTINGS_DIR`. Internal module `kildeanalyse`, SQLite filename, technical engine IDs and recorded schemas remain stable. Historical source copies and raw attempts are not rewritten.

## Limits and optional examples

Windows is supported. PDF supports local OCR; run `ocr_setup.cmd` once to install Tesseract with English/Norwegian language data. MCP import defaults to `ocr_mode=auto`; `force` reads every page image, and `off` uses only existing text. Word uses body paragraphs/tables; Excel uses cell contents and stored formula caches. Charts, photographs and other embedded objects are not semantically analysed.

New plans automatically split oversized input into bounded reading calls followed by a synthesis of checked findings. The plan records `document_processing=auto`, `input_budget_bytes=60000` and `max_chunks=100`; call counts and fragment ranges are visible before approval. The byte budget is not an exact model context limit. Excessive instructions or synthesis input cause an explicit stop. Old plans retain their original single-call behaviour. See [OCR, limits and audit trail](docs/DOCUMENT_PROCESSING.md).

Optional `priority_terms` and `priority_locations` reorder chunk reading by matching text and source locators. All source fragments remain required for full coverage. Express substantive interpretation priorities in `additional_instructions`; agree any narrower source scope separately. The host can propose preparation or conversion using its own tools, but should preserve originals and record the transformation. It must not silently change the reader, model, effort or analysis scope.

Row/sheet selection as separate runs and cross-document synthesis are not implemented. CLI restrictions do not provide full operating-system isolation. The host runs as the same local user and can access the data directory outside MCP.

**[Explore five use cases](examples/README.md):** policy reports (including scanned PDF), supplier offers (DOCX), project portfolios (XLSX), bilingual consultations (Markdown/TXT) and incident registers (CSV/TSV). Each includes files, draft criteria and start prompts.

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

Primary documentation and new public interfaces are English. Norwegian user instructions remain available. Persisted audit fields stay stable; obsolete product-brand aliases are not supported.
