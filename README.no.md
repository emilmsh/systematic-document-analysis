# Systematic Document Analysis

Systematisk dokumentanalyse med kriterier, kildebelegg og kontrollhistorikk. Dette er det nye navnet på OE Kildeanalyse. Du kan arbeide på norsk eller engelsk, i Codex eller Claude Code, med egne dokumenter.

**[Last ned siste release](https://github.com/emilmsh/systematic-document-analysis/releases/latest)** · **[Start her](START_HER.md)** · **[Full dokumentasjon på engelsk](README.md)**

Diskuter problemstillingen i appen, avtal kriterier, og velg motor, modell, tenkenivå og språk. Hvert dokument leses etter samme plan i en separat kjøring. Inspiser sitater, registrer reell menneskelig kontroll og eksporter resultatene. Appen du arbeider i og motoren som leser dokumentene er uavhengige valg.

Arbeidsagentene kan bruke Codex CLI, Claude Code CLI eller API fra OpenAI, Anthropic, OpenRouter og kompatible leverandører. API er valgfritt og separat betalt. Modellvalget i app-samtalen arves ikke automatisk av arbeidsagentene.

Språkvalget `nb` gir norske kommentarer og merknader. `en` gir engelske. Sitater beholdes på originalspråket og svaralternativer gjengis ordrett. Endringer gir en ny planversjon; historiske svar bevares. Automatisk validering er ikke menneskelig kontroll.

En vanlig mappe med PDF-er med tekstlag er tilstrekkelig. Assistenten hjelper deg å skrive kriteriefilen. Pluginen trenger ikke ligge i arbeidsmappen. Ingen simulering eller eksempelgjennomgang er påkrevd.

Windows er foreløpig støttet. OCR og automatisk oppdeling av store dokumenter er ikke implementert. API-adapterne er kontrollert lokalt uten betalte modellkall; faktisk modellstøtte og faglig kvalitet må vurderes ved bruk.

Eksisterende analyser brukes fra sin opprinnelige datamappe. Nye installasjoner bruker `%LOCALAPPDATA%/systematic-document-analysis`; `SDA_DATA` kan overstyre. Gamle miljøvariabler og verktøynavn virker fortsatt. Eksporten har engelske og norske lesefiler samt uendrede rådata. Se README for detaljer.
