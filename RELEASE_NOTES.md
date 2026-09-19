# v0.5.0 – valgfrie API-motorer i begge vertsappene

Last ned **oe-kildeanalyse-windows.zip**, pakk ut og start **installer.cmd**. Velg Claude Code, Codex eller begge. Python 3.12+ og valgt CLI med egen abonnementskonto er nødvendig. Start en ny lokal samtale etter installasjon.

- Samme arbeidsflyt i ChatGPT desktop/Codex og Claude Code, med motorvalg uavhengig av vertsappen.
- Beholder Codex CLI og Claude Code CLI med abonnement. Legger til OpenAI Responses, Anthropic Messages, OpenRouter og eksplisitt HTTPS-adresse til kompatibelt Chat Completions API.
- API-valg, mottaker, modell, tenkenivå og tokenbudsjett vises i planen. Forespørselen uten autentisering inngår i inputhash, historikk og eksport.
- Nøkler hentes lokalt fra miljøvariabler og fjernes fra CLI-underprosessene. API bruker separat betaling; ingen automatisk fallback eller retry.
- Oppdatert README, START_HER og arbeidsveiledning. Egne dokumenter er normal arbeidsflyt; eksemplene er valgfrie.

Repoet er privat: GitHub-nedlasting krever tilgang. ZIP-filen kan deles direkte med kolleger. Den inneholder verken brukerdata, innlogging eller API-nøkler.

Teknisk verifikasjon: 80 lokale kontroller med falsk HTTP-transport, samt ren MCP-oppstart og planhistorikk for alle motorer. Ingen modellkall. Ekte API-tilgang og klassifiseringskvalitet er ikke verifisert. Modellens støtte for strukturerte svar og tenkenivå varierer. Windows er støttet; macOS/Linux, OCR, full OS-isolasjon og automatisk oppdeling av store dokumenter er ikke implementert.
