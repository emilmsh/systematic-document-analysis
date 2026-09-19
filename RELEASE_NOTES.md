# v0.4.0 – én pakke for Claude Code og Codex

Last ned **oe-kildeanalyse-windows.zip**, pakk ut og start **installer.cmd**. Velg Claude Code, Codex eller begge. Python 3.12+ og valgt CLI med egen abonnementskonto er nødvendig. Start en ny lokal samtale etter installasjon.

- Felles installasjonsmeny med separate vedvarende kopier for hver app. Maskinspesifikke stier dannes hos mottakeren.
- Arbeidsflyt med egne PDF-dokumenter, avtalte kriterier, eksplisitt modell og tenkenivå, kildebelegg, kontrollhistorikk og CSV/JSON/Markdown-eksport.
- Oppdatert README og START_HER. Eksempeloppgave med fem offentlige årsrapporter og nedlastingsskript; rapportfilene følger ikke med ZIP-en.
- Gjenbrukbar releasebygger som pakker bare definerte filer og skriver SHA256SUMS.txt.

Repoet er privat: GitHub-nedlasting krever tilgang. ZIP-filen kan deles direkte med kolleger. Den inneholder verken brukerdata, innlogging eller API-nøkler.

Teknisk verifikasjon: 34 lokale tester; ny og gjentatt installasjon i begge CLI-er med midlertidige appkonfigurasjoner. Ingen modellkall. Windows er støttet; macOS/Linux, OCR, full OS-isolasjon og automatisk oppdeling av store dokumenter er ikke implementert.
