# Systematic Document Analysis

Codex og Claude Code er anvendelige til et stort spenn av oppgaver. Ved systematiske, repetitive analyser trenger vi ofte mer kontroll og etterprøvbarhet enn en vanlig samtale enkelt gir. Denne pluginen beholder appenes dialog, verktøy og vurderingsevne, og legger til felles kriterier, eksplisitte modellvalg, dokumenterte lesekjøringer, sitater og menneskelig kontroll.

Bruk egne rapporter, tilbud, dokumenter, regneark eller registre. Definer hva som skal vurderes likt på tvers av filene, diskuter forventede filproblemer og prioriteringer, og godkjenn planen før lesing. Modellen skal følge direkte valg om modell, tenkenivå, omfang og rapportering; skjønn brukes innenfor disse rammene. Automatisk validering er ikke menneskelig kontroll.

- [Last ned siste Windows-pakke for begge apper](https://github.com/emilmsh/systematic-document-analysis/releases/latest)
- [Start her](START_HER.md): automatisk Python, CLI-innlogging og valgfri lokal nøkkelfil.
- [Fem eksempelmapper](examples/README.md): PDF/skanning, Word, Excel, tekst og tabeller.
- [Filformater](docs/SOURCE_FORMATS.md), [OCR og store dokumenter](docs/DOCUMENT_PROCESSING.md), [oppsett og deling](docs/SETUP_AND_SHARING.md).

Repoet er privat. Kollegaer trenger tilgang for GitHub-nedlasting, eller du kan dele ZIP-filen direkte. Den inneholder fiktive eksempler, ingen private analyser eller nøkler. Ingen manuell Python-installasjon er nødvendig. Innlogging i abonnementet og innliming av eventuelle API-nøkler fullfører brukeren selv.

PDF, DOCX, XLSX, CSV/TSV, TXT og Markdown støttes. PDF kan OCR-behandles lokalt. Store kilder deles i begrensede lesekall før kontrollerte funn sammenstilles. Prioriteringer endrer leserekkefølgen, ikke kravet om full dekning. Bilder, diagrammer og utelatte Word-objekter er ikke fullstendig tolket; formler blir ikke beregnet. Begrensninger skal fram i planen.

Vert og lesemotor velges uavhengig: Codex eller Claude Code som vert; Codex CLI, Claude Code CLI eller valgfri OpenAI-, Anthropic-, OpenRouter- eller kompatibel API-leser. ChatGPT web alene kan ikke starte denne lokale Windows-tjenesten. Appbasert plugin-deling er mulig innenfor leverandørenes kataloger og regler; pakken er foreløpig verifisert med lokal installasjon i Codex og Claude Code.

Versjon 0.8 fjerner tidligere merkevarealiaser og automatisk gjenfinning av eldre datamapper. Bruk `SDA_DATA` dersom du vil velge et tidligere lager uttrykkelig. Ingen eksisterende data flyttes eller slettes. Full dokumentasjon og utviklingsveiledning står i [README](README.md).
