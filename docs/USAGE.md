# Systematic Document Analysis

A controlled for-loop over files in Claude Code or Codex: one agreed task, one independent CLI/API worker per file, and an audit trail from result back to source, instruction, settings and raw response. The task determines the deliverable. See [task contracts and examples](TASKS.md).

[Norsk](USAGE.no.md) · [Start here](../README.md) · [Installation and updates](UPDATES.md)

## Quick install — Windows

**You only need to double-click `installer.cmd`.** It installs the plugin and any missing command-line tool (CLI), lets you choose a reader, and checks subscription sign-in. If the CLI is not signed in with a subscription, it starts sign-in for you to complete in your browser. Existing subscription sign-in is reused. Being signed in to the desktop app does not confirm that the CLI is signed in.

1. Download the **[Windows ZIP](https://github.com/emilmsh/systematic-document-analysis/releases/latest/download/systematic-document-analysis-windows.zip)** and extract it under Downloads. See the [latest published release](https://github.com/emilmsh/systematic-document-analysis/releases/latest).
2. Open the extracted folder in File Explorer, double-click **installer.cmd**, choose **1 = Install**, then **1 = Claude Code, 2 = Codex, or 3 = both**. Run as your ordinary Windows user, outside the Codex terminal.
3. **Continue in the same installer window:** choose your reader, **1 = Codex / ChatGPT, 2 = Claude Code or 3 = Both**, and complete any required browser sign-in with the intended account. Wait for the installer to confirm sign-in. Choose **4 = Skip** if you will use an API or set up the reader later. The reader is independent of the app selected in step 2.
4. Open your working folder in Claude Code's **Code tab** or in Codex, start a **new local conversation**, and describe your task: **“Use Systematic Document Analysis. I want to understand how these annual reports describe their use of AI. The files are in [folder].”**

First-time setup requires internet access. The installer provides Python and installs the selected app's command-line tool if it is missing; you do not need to use the terminal yourself.

**`installer.cmd reader` remains a helper for later use**, for example if you skipped or cancelled sign-in. You do not need to reinstall the plugin. To switch accounts, run `installer.cmd reader claude --login` or `installer.cmd reader codex --login` in a terminal.

## Project folder and results

Choose a visible project folder in the conversation. Plans and input previews are saved there
before execution. The default result is a workbook: one row per run, with generated variables
in columns. Nested objects become columns; repeated records have linked detail sheets.
Errors and retries have sheets when relevant; variables are explained in the workbook. Start in `START_HERE.md`.
One documentation ZIP preserves the plan, original results, source copies and audit trail.
Export edits do not update recorded results. See [Project files and exports](PROJECT_FILES.md).

## Why use it

When one task is repeated across forty reports, offers or workbooks, you need to trace each result to the instruction, source and settings that produced it. The plugin keeps those runs separate and records both errors and results. It also distinguishes actual human review from automated checks, while the conversation stays in your existing app.

## What it does

- **Works on files from a folder you choose.** PDF, DOCX, XLSX, CSV/TSV, TXT and Markdown have automatic extraction; other files are preserved for file-capable CLI workers. Scanned PDFs can be OCR-processed locally. A large CLI file remains available to one worker with searchable source copies; oversized API input fails visibly.
- **Repeats the task you define.** A plain instruction is enough; task-defined result schemas and relevant checks are optional. The assistant helps make the instruction repeatable.
- **Runs one document per attempt with fixed settings.** The plan records reader, model, reasoning effort, language and instructions. The assistant can inspect source text during preparation; a named person approves the plan before the reader runs. Changing it creates a new version; earlier attempts are untouched.
- **Stores execution evidence.** Every attempt retains exact input, raw answer, declared checks and their outcomes. Source units have PDF page, Word block, sheet/cell, text line or CSV record locations. Exact-quote checks are optional for general tasks.
- **Records human review.** A person approves, corrects or rejects each assessment with a reason. Automatic checks are never recorded as human review.
- **Delivers a dataset automatically.** One workbook row per run, task-specific variables in columns, and separate sheets for repeated records, errors and retries when relevant. Original results and the full audit trail are preserved in one documentation ZIP.

The conversation stays in Claude Code or Codex. The plugin adds the record keeping and the repeatable reading; the assistant still helps you think about the question, the criteria and problem files.

## What it does not do

- It does not summarise across documents. Each file is one unit; comparison is your job, or the assistant's, using the exported results.
- It does not retry, switch model or fall back to a paid API on its own. Errors and timeouts are reported per run while other runs finish.
- Automatic extraction does not interpret charts, photographs or embedded objects, and does not recalculate spreadsheet formulas. A file-capable CLI worker may inspect the original when its available tools support the task.
- It runs on Windows only and needs a local Python runtime, which the installer provides.

## Installation

The repository and its releases are public on GitHub.

### Let your assistant do it

Paste one of these into a new conversation. The assistant downloads and verifies the release, and either runs the installer or shows you how to start it yourself. **The Claude prompt uses `--non-interactive`, which skips sign-in.** After that route, use `installer.cmd reader` if needed. A normal double-click on `installer.cmd` includes sign-in.

Claude Code:

> Install Systematic Document Analysis for Claude Code. Release page: https://github.com/emilmsh/systematic-document-analysis/releases/latest. Download systematic-document-analysis-windows.zip and SHA256SUMS.txt, verify the checksum, extract the ZIP to a folder under my Downloads, run `installer.cmd claude --non-interactive` from that folder and show me the output. Then run `claude plugin list` and confirm that systematic-document-analysis is enabled. Do not change other plugins, settings or files, and do not run installer.cmd reader or installer.cmd settings unless I ask.

ChatGPT desktop / Codex:

> Install Systematic Document Analysis for Codex. Release page: https://github.com/emilmsh/systematic-document-analysis/releases/latest. Download systematic-document-analysis-windows.zip and SHA256SUMS.txt, verify the checksum and extract the ZIP to a folder under my Downloads. Show me the folder path so I can double-click installer.cmd in File Explorer and choose Codex. Leave that installation step to me. When I confirm, run `codex plugin list` and check that systematic-document-analysis is enabled. Do not change other plugins, settings or files.

If sign-in was skipped, open **installer.cmd**, choose Sign-in and settings → Reader sign-in, then choose your reader. The helper reuses existing subscription sign-in or starts sign-in if needed. Then start a new conversation so the app loads the plugin.

### By hand

1. Download the [Windows ZIP](https://github.com/emilmsh/systematic-document-analysis/releases/latest/download/systematic-document-analysis-windows.zip) from the [latest release](https://github.com/emilmsh/systematic-document-analysis/releases/latest) and extract it.
2. Double-click `installer.cmd` in File Explorer, choose Install, then Claude Code, Codex or both. It prepares Python 3.12 or newer, installs a missing host CLI, registers the plugin and reports the installation folder.
3. In the same window, choose your reader, **1 = Codex / ChatGPT, 2 = Claude Code or 3 = Both**, and complete any required browser sign-in. The installer checks sign-in before reporting setup complete. **4 = Skip** postpones this step or lets you use an API. Then start a new local conversation. The first start installs the Python dependencies.

Subscription reading uses the app's CLI. Normal installation sets up the selected CLI and local OCR with English/Norwegian language data; you complete the vendor's sign-in yourself. CLI discovery handles stale PATH automatically. Reader sessions get file tools, parsers, PDF page images and OCR in a fresh workspace per call. `installer.cmd reader` and `installer.cmd ocr` remain available for later setup or repair. `installer.cmd settings` opens a local file for optional API keys.

### Updates

Run `installer.cmd update` from the installed folder to check for a newer release, install it, or choose notify only (default), automatic or off. Start a new conversation after updating. See [installation and updates](UPDATES.md) for settings and troubleshooting.

## Using it

**Check the prerequisites before starting.** Available tools, reader sign-in, a repeatable task, source selection and an approved plan must be in place. Missing shared prerequisites block startup, with the reason in `show_status`. Correct or clarify the issue and recheck. Reuse existing authorization when applicable. Material plan changes require authorization for the changed plan.

**Individual run problems do not stop the other runs.** Unreadable sources, timeouts, call errors and failed answer/evidence checks are recorded for follow-up. The other runs finish before you review the issues together. Results and available raw evidence are preserved; failed or uncertain attempts are not retried automatically or presented as successful. Shared infrastructure failure or verified loss of reader access can still block new dependent calls.

Allowed answers such as “unclear” or “not mentioned” are valid findings when their evidence and coverage requirements are met. Human review is required before describing results as reviewed.

**CLI sign-in is required before analysis.** The Claude and Codex readers verify subscription sign-in before every CLI call. Missing or unverifiable sign-in blocks new calls; a generic CLI error only fails that run. The assistant must explain how to sign in and may still prepare criteria and the plan, but must not replace the analysis with subagents or direct reading. After sign-in, recheck setup before asking to continue.

Open an ordinary project folder in the app and put your own source files in a `documents` subfolder. No Git repository or example run is needed. Describe the task, for example:

> Use Systematic Document Analysis. I want to understand how these annual reports describe their use of AI. The files are in the documents folder.

You do not need a schema or technical settings. The assistant helps turn your intent into one repeatable instruction, inspects the files and proposes a useful deliverable and checks. It asks about consequential choices, distinguishes your requirements from suggestions and flags files that need a file-capable reader. A small agreed pilot is optional.

Before the reader starts, you receive a short plan covering the task, file selection, generated variables and definitions, checks, uncertainty, reader/model and result location. Approve the concrete plan and identify the responsible person. The assistant normally defines typed task-specific variables before execution. The default deliverable is a workbook with one row per run and generated variables in columns. Nested objects become columns and repeated values can have linked detail sheets. Errors and other auxiliary information have separate sheets when relevant. After completion, export the workbook without waiting for a separate spreadsheet request. Raw responses and JSON are kept in one documentation ZIP. Prose-only tasks retain a text result column.

Runs execute independently per file, with one fresh worker per attempt. Large CLI inputs use file tools; oversized API inputs fail explicitly. You can stop, resume, inspect attempts, record actual human review, and export. Changed tasks/contracts/settings require a new plan version. Afterward, use the host flexibly for tables, reports or further analysis while preserving originating run/attempt references.

### Hosts and readers

The app you talk to and the model that reads the documents are chosen separately. Before execution, the assistant presents the reader, exact requested model ID or deployment name, and reasoning effort for your sign-off together with the task and file scope. Missing choices are proposed explicitly, including relevant time, cost or quality tradeoffs. Material settings such as timeout, output-token limit, input-byte budget, file-tool access and API endpoint/format are included when applicable; provider defaults and unsupported controls are identified. The assistant also asks how many files you want processed at once and proposes a number based on the task (`max_concurrent_runs`, 1–16; one at a time unless agreed). Each file still gets its own independent run. Running several at once shortens waiting time but uses the same quota or API cost, and a quota stop then interrupts several runs. The approved number is a ceiling: a start or resume may use fewer, while more requires a revised, approved plan. One approval covers the concrete plan and settings. Existing approval remains sufficient for the same plan; changes require approval of the revised plan before execution.

| Host (conversation) | Reader (reads each document) |
|---|---|
| Claude Code, Codex desktop | `claude_cli` (default `sonnet`, high), `codex_cli` (default `gpt-5.6-terra`, high), or `openai_api`, `azure_foundry_api`, `anthropic_api`, `openrouter_api`, `kompatibel_api` with an explicit model ID |

CLI readers use your subscription sign-in and the vendor's agent harness with a fresh context per file and access to their built-in tools. API readers make direct calls and are billed by the provider. The requested model and effort are recorded; whether a provider honoured the effort is only known if it reports it.

### API keys (optional)

`installer.cmd settings` opens `%LOCALAPPDATA%\systematic-document-analysis\settings\providers.env` in Notepad. Paste a key after `OPENAI_API_KEY=`, `ANTHROPIC_API_KEY=`, `OPENROUTER_API_KEY=`, `AZURE_AI_API_KEY=` or `SDA_CUSTOM_API_KEY=` and save. The file is plain text outside the project; do not share it, commit it or ask an assistant to read it. Keys are only used to authenticate requests and are excluded from stored inputs and exports. Environment variables with the same names override the file.

### Data

Analysis data is stored in `%LOCALAPPDATA%\systematic-document-analysis` and shared by both apps. `SDA_DATA` selects another directory. Nothing is moved or deleted automatically; `show_setup` displays the directory in use.

## Azure AI Foundry

In **installer.cmd → Sign-in and settings → API settings**, fill `AZURE_AI_API_KEY` locally. Opening settings adds this empty field to older settings files without replacing their existing keys. No Azure SDK or additional installation is needed.

Ask for the **Azure Foundry** reader (`azure_foundry_api`) and provide the resource endpoint and deployment name. These are nonsecret plan settings; the key stays on your computer. Set `api_format` explicitly to match the deployment:

| Deployment interface | `api_format` | Resource base URL |
| --- | --- | --- |
| Responses | `responses` | `https://RESOURCE.services.ai.azure.com/openai/v1` or `https://RESOURCE.openai.azure.com/openai/v1` |
| OpenAI-compatible Chat Completions | `chat_completions` | Same resource URLs as above |
| Claude Messages | `anthropic_messages` | `https://RESOURCE.services.ai.azure.com/anthropic/v1` |

A bare resource URL is also accepted; the selected format supplies the path. For Claude, `/anthropic` is accepted too. Use the resource endpoint, not a `/api/projects/...` project URL. Use your **deployment name** as the model; it can differ from the catalog model ID.

For example, engine `azure_foundry_api`, model `my-deployment`, and settings `{"base_url":"https://my-resource.services.ai.azure.com", "api_format":"chat_completions"}`. Choose `reasoning_effort="standard"` to omit explicit effort; other levels depend on the deployment. The chosen deployment must accept JSON-schema structured output and the requested parameters. Unsupported calls fail visibly; the plugin does not switch format, retry or drop parameters. The endpoint, format and exact request are included in the approval/audit trail, with no tools or web search enabled.

This supports API-key authentication on the listed public Azure resource domains. Entra ID authentication, sovereign-cloud domains and legacy model-inference endpoints are not implemented. Models that require Entra ID cannot use this key-based reader. Billing belongs to the Azure resource. See Microsoft's [v1 API documentation](https://learn.microsoft.com/en-us/azure/foundry/openai/api-version-lifecycle) and [Claude on Foundry documentation](https://learn.microsoft.com/en-us/azure/foundry/foundry-models/how-to/use-foundry-models-claude).

## Documentation

- [Start here](../README.md) and [Start her (norsk)](../README.md)
- [Installation and updates](UPDATES.md)
- [Setup and sharing](SETUP_AND_SHARING.md)
- [Supported formats and extraction scope](SOURCE_FORMATS.md)
- [OCR, large documents and the audit trail](DOCUMENT_PROCESSING.md)
- [Five example folders](https://github.com/emilmsh/systematic-document-analysis/tree/main/examples/README.md) with fictional files, draft criteria and prompts. Optional; the plugin is meant for your own documents.

Agree delivery format, row unit, columns and location before execution; reuse explicit preferences. The default workbook has one row per run. `row_scope="documents"` selects the newest planned run per document, even when it failed; never silently substitute an older success. Use `output_directory` for a shorter export parent without moving the project.
