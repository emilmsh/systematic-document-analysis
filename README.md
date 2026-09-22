# Systematic Document Analysis

Apply agreed criteria to your own documents, with source quotations, visible reader settings and an audit trail. Works with Claude Code and Codex, in English and Norwegian.

**[Download for Windows / Last ned for Windows](https://github.com/emilmsh/systematic-document-analysis/releases/latest/download/systematic-document-analysis-windows.zip)** — private repository; sign in with access or use a ZIP shared by a colleague.

## Start here

1. Extract the Windows ZIP and double-click **installer.cmd** in File Explorer. Choose **1 — Install**, then Claude Code, Codex or both. Use an ordinary Windows terminal or Explorer, outside the Codex app.
2. Continue in the same window. Setup prepares the required runtime and file tools, checks OCR and lets you set up Codex, Claude Code or both for subscription reading. Existing sign-ins are reused. No manual PATH setup is needed.
3. Start a new local conversation with the plugin enabled, open your document folder and describe your task:

   > Use Systematic Document Analysis. How do these annual reports describe their use of AI?

The assistant helps define criteria and shows the selected documents and plan for your approval before reading. Your source files, results and settings stay separate from the plugin installation.

Open **installer.cmd** again and choose **Sign-in and settings** for reader sign-in or API keys, or **Update or repair** for maintenance. For update checks and update policy, use the menu in the **installed plugin folder**; its location is shown after installation. Never paste API keys into chat.

**Moving from 0.8.7 or earlier:** install the new ZIP once. The older updater expects files removed from the simplified package. Existing analysis data and settings are retained; the previous plugin copy is backed up. Later updates use the new menu.

[Detailed guide](docs/USAGE.md) · [Supported formats](docs/SOURCE_FORMATS.md) · [Updates and recovery](docs/UPDATES.md)

## Start her

1. Pakk ut Windows-ZIP-en og dobbeltklikk **installer.cmd** i Filutforsker. Velg **1 — Installer**, deretter Claude Code, Codex eller begge. Kjør utenfor Codex-appen.
2. Fortsett i samme vindu. Oppsettet klargjør nødvendige filverktøy, kontrollerer OCR og lar deg sette opp Codex, Claude Code eller begge for abonnementslesing. Eksisterende innlogginger brukes videre. Du trenger ikke ordne PATH selv.
3. Start en ny lokal samtale med pluginen aktivert, åpne dokumentmappen og beskriv oppgaven:

   > Bruk Systematic Document Analysis. Hvordan beskriver disse årsrapportene bruken av KI?

Assistenten hjelper med kriterier og viser dokumentutvalget og planen til godkjenning før lesingen starter. Kilder, resultater og innstillinger lagres separat fra plugininstallasjonen.

Åpne **installer.cmd** igjen og velg **Innlogging og innstillinger** for lesermotor eller API-nøkler, eller **Oppdater eller reparer** for vedlikehold. Oppdateringer styres fra menyen i **den installerte pluginmappen**, som vises etter installasjon. Ikke lim API-nøkler inn i chatten.

**Fra 0.8.7 eller eldre:** installer den nye ZIP-en én gang. Den gamle oppdatereren forventer filer som er fjernet fra den ryddede pakken. Analysedata og innstillinger beholdes, og forrige pluginkopi sikkerhetskopieres.

[Utfyllende veiledning](docs/USAGE.no.md) · [Oppsett og deling](docs/SETUP_AND_SHARING.md)

## Package contents

Start with **installer.cmd** and this **README.md**. `bin`, `src`, `skills`, plugin manifests, `.mcp.json` and `pyproject.toml` are supporting files; keep them with the installer. `docs` contains the detailed user guides. Development files, tests and optional examples remain in the [repository](https://github.com/emilmsh/systematic-document-analysis).

Created and developed by **Emil Mathias Strøm Halseth**, with development assistance from **OpenAI Codex** and **Anthropic Claude Code**.
