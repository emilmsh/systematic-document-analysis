# Start med Systematic Document Analysis

1. Installer Python 3.12+ og Codex CLI eller Claude Code CLI. Logg inn med egen konto.
2. Pakk ut ZIP-filen, kjør **installer.cmd** og velg appen din eller begge. Menyen er på engelsk.
3. Start en ny lokal samtale med **Systematic Document Analysis** aktivert. Første serverstart installerer Python-avhengigheter.

En vanlig mappe eller liste med PDF, DOCX, XLSX, CSV/TSV, TXT eller Markdown er nok. Avtal felles struktur og kriterier; hver hele fil er én analyseenhet. Oppgi hele mappestien; undermapper oppgis separat. Assistenten hjelper deg å formulere kriteriene og lager kriteriefilen i arbeidsmappen.

> Bruk Systematic Document Analysis på filene i [full mappesti]. Jeg vil undersøke [problemstilling]. Hjelp meg å formulere kriterier og svaralternativer. Bruk CLI-motoren til appen jeg arbeider i, med tenkenivå high. Skriv kommentarer på norsk og behold sitatene på originalspråket. Vis modell, plan, lesedekning og inputpakken før jeg godkjenner oppstart. Kjør deretter materialet og eksporter svar med sitater og kildeplasseringer. Ikke registrer menneskelig kontroll på mine vegne.

Planen lagrer motor, modell, tenkenivå og språk (`nb` for norsk, `en` for engelsk). Modellvalg arves ikke fra app-samtalen. Egne dokumenter er vanlig arbeidsflyt; eksempler og simulering er valgfrie.

API-motorer er `openai_api`, `anthropic_api`, `openrouter_api` og `kompatibel_api`. Oppgi modell-ID og sett nøkkelen lokalt som brukermiljøvariabel i Windows; start hele appen på nytt. Ikke lim nøkkelen inn i samtalen. API innebærer separat betaling. Se [README](README.md) for innstillinger og begrensninger.

Nye analyser lagres som standard i `%LOCALAPPDATA%/systematic-document-analysis`. Har du allerede en database fra OE Kildeanalyse, brukes den i den gamle mappen. `show_setup` viser faktisk datamappe. Eksporten inneholder både engelske og norske CSV-filer og hele kontrollsporet.

Oppdater fra [siste release](https://github.com/emilmsh/systematic-document-analysis/releases/latest). Ved overgang fra det gamle navnet: installer den nye pluginen og deaktiver den gamle i begge appene. Data slettes ikke. Behold installasjonsmappene i LocalAppData; utpakket nedlasting kan slettes etter installasjon.

[Kort norsk oversikt](README.no.md) · [English guide](START_HERE.md)

[Format support and extraction limits / formatstøtte og uttrekksomfang](docs/SOURCE_FORMATS.md).
