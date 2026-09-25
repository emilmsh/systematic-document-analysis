<img src="assets/icon.svg" alt="Systematic Document Analysis" width="96">

# Systematic Document Analysis

**[⬇ Download for Windows / Last ned for Windows](https://github.com/emilmsh/systematic-document-analysis/releases/latest/download/systematic-document-analysis-windows.zip)** — latest release · [Release notes](https://github.com/emilmsh/systematic-document-analysis/releases/latest) · [Norsk](#start-her)

**A controlled for-loop over files.** Define one task, run an independent CLI or API worker for each file, and trace every result back to its instructions, source, settings and raw response. Works inside Claude Code and Codex, in English and Norwegian.

If one task can be standardized and repeated across a file list, this plugin fits. The default output is a dataset: **one row per iteration/run, with generated variables in columns**, delivered as an Excel workbook. The task determines the variables: extracted entities or passages, scores, topics, sentiment, calculations or other results. Nested objects become meaningful columns; repeated collections can have linked detail sheets. Errors and other auxiliary information have their own sheets. Each file gets one fresh worker; large CLI inputs use file tools, while oversized API inputs fail explicitly.

[Task contracts and examples](docs/TASKS.md) · [Core principles and implementation plan](docs/CORE_REDESIGN.md)

## Start here

1. Extract the Windows ZIP and double-click **installer.cmd** in File Explorer. Choose **1 — Install**, then Claude Code, Codex or both. Use Explorer or an ordinary Windows terminal, outside the Claude and Codex desktop apps.
2. Continue in the same window. Setup prepares the required runtime and file tools, checks OCR and lets you set up Codex, Claude Code or both for subscription reading. Existing sign-ins are reused. The installer then offers to check for and install the latest reader CLI version. No manual PATH setup is needed.
3. Start a new local conversation with the plugin enabled, open your document folder and describe your task:

   > Use Systematic Document Analysis. How do these annual reports describe their use of AI?

The assistant proposes a repeatable task and useful variables, then shows the selected documents, definitions and reader settings for approval before running. After execution it exports the workbook automatically. Start with Results.xlsx; the raw responses, JSON and full audit trail are preserved together in Documentation.zip. Your source files, results and settings stay separate from the plugin installation.

Open **installer.cmd** again and choose **Sign-in and settings** for reader sign-in or API keys, or **Update or repair** for maintenance. Updates are automatic: Claude Code and Codex fetch new releases themselves and load them in a new conversation. Never paste API keys into chat.

[Detailed guide](docs/USAGE.md) · [Supported formats](docs/SOURCE_FORMATS.md) · [Updates and recovery](docs/UPDATES.md)

## Start her

1. Pakk ut Windows-ZIP-en og dobbeltklikk **installer.cmd** i Filutforsker. Velg **1 — Installer**, deretter Claude Code, Codex eller begge. Bruk Filutforsker eller en vanlig Windows-terminal, utenfor Claude- og Codex-appene.
2. Fortsett i samme vindu. Oppsettet klargjør nødvendige filverktøy, kontrollerer OCR og lar deg sette opp Codex, Claude Code eller begge for abonnementslesing. Eksisterende innlogginger brukes videre. Du trenger ikke ordne PATH selv.
3. Start en ny lokal samtale med pluginen aktivert, åpne dokumentmappen og beskriv oppgaven:

   > Bruk Systematic Document Analysis. Hvordan beskriver disse årsrapportene bruken av KI?

Pluginen er en kontrollert for-løkke over filer: én standardisert oppgave og én uavhengig CLI/API-arbeider per fil. Standardleveransen er **et regneark med én rad per kjøring og resultatvariabler i kolonnene**. Oppgaven bestemmer variablene. Nested objekter blir kolonner, mens gjentatte funn kan få koblede detaljfaner. Feil og øvrig tilleggsinformasjon får egne faner. Assistenten foreslår variablene før godkjenning og eksporterer regnearket etter kjøring. Åpne Resultater.xlsx; råsvar, JSON og kontrollsporet ligger samlet i Dokumentasjon.zip. Hver fil får én ny arbeider; store CLI-input leses med filverktøy, mens for store API-input gir en tydelig feil.

Åpne **installer.cmd** igjen og velg **Innlogging og innstillinger** for lesermotor eller API-nøkler, eller **Oppdater eller reparer** for vedlikehold. Oppdateringer skjer automatisk: Claude Code og Codex henter nye utgaver selv og laster dem i en ny samtale. Ikke lim API-nøkler inn i chatten.

[Utfyllende veiledning](docs/USAGE.no.md) · [Oppsett og deling](docs/SETUP_AND_SHARING.md)

## Package contents

Start with **installer.cmd** and this **README.md**. `bin`, `src`, `skills`, `assets`, plugin manifests, `.mcp.json`, `pyproject.toml` and `LICENSE` are supporting files; keep them with the installer. `docs` contains the detailed user guides. Development files, tests and optional examples remain in the [repository](https://github.com/emilmsh/systematic-document-analysis).

Created and developed by **Emil Mathias Strøm Halseth**, with development assistance from **OpenAI Codex** and **Anthropic Claude Code**. Released under the [MIT License](LICENSE).
