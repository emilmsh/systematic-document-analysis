# Systematic Document Analysis

En plugin for Claude Code og Codex som leser en samling dokumenter mot kriterier du bestemmer, ett dokument om gangen, og tar vare på hva modellen fikk, hva den svarte, hvilke sitater den bygde på og hvordan et menneske kontrollerte resultatet.

[English](README.md) · [Start her](START_HER.md) · [Installasjon og oppdateringer](docs/UPDATES.md)

## Hurtiginstallasjon — Windows

1. Last ned **[Windows-ZIP-en](https://github.com/emilmsh/systematic-document-analysis/releases/latest/download/systematic-document-analysis-windows.zip)** og pakk den ut under Nedlastinger. Gjeldende utgave er **[0.8.5](https://github.com/emilmsh/systematic-document-analysis/releases/tag/v0.8.5)**. Privat repo: logg inn med tilgang, eller bruk en ZIP du har fått fra en kollega.
2. Åpne den utpakkede mappen i Filutforsker, dobbeltklikk **installer.cmd**, og velg **1 = Claude Code, 2 = Codex eller 3 = begge**. Kjør som din vanlige Windows-bruker, utenfor terminalen i Codex.
3. For lesing med abonnementet ditt: dobbeltklikk **reader_setup.cmd**, velg Claude Code eller Codex og fullfør innloggingen.
4. Start en **ny lokal samtale** i **Code-fanen** i Claude eller i Codex og skriv: **«Bruk Systematic Document Analysis på dokumentene i [mappe]. Hjelp meg med kriterier og vis planen før kjøring.»**

Førstegangsoppsett krever internett. Installasjonsprogrammet ordner Python og installerer den valgte appens kommandolinjeverktøy hvis det mangler; du trenger ikke bruke terminalen selv.

## Prosjektmappe og resultater

Velg en synlig prosjektmappe i samtalen. Planer og inputforhåndsvisninger lagres der før kjøring.
Hver eksport får en ny mappe med én Excel-arbeidsbok, én plan, én startfil, kildekopier og et eget
område for kontrollsporet. CSV er valgfritt. Begynn i `START_HERE.md` i prosjektmappen.
Excel-endringer endrer ikke registrerte resultater eller menneskelig kontroll.
Se [Prosjektfiler og eksportformater](docs/PROJECT_FILES.md).

## Hvorfor

En samtaleassistent kan lese én rapport og svare på spørsmål om den. Det holder ikke når de samme spørsmålene skal besvares for førti årsrapporter, en bunke tilbud eller en mappe regneark, og svarene skal brukes senere. Da må du vite at alle dokumentene ble lest med samme instruks, modell og innstillinger, at hvert svar er knyttet til et sitat du kan slå opp, og at noen faktisk har kontrollert resultatet. Det gir ikke en vanlig samtale. Det gjør denne pluginen, uten at du forlater appen du allerede bruker.

## Hva den gjør

- **Leser filer fra en mappe du velger.** PDF, DOCX, XLSX, CSV/TSV, TXT og Markdown. Skannede PDF-er kan OCR-behandles lokalt. Store filer leses i avgrensede deler før funnene settes sammen i ett ekstra kall, og alle kallene lagres.
- **Bruker kriterier du definerer.** En liten JSON-fil lister spørsmålene, tillatte svar og tolkningsregler. Assistenten hjelper deg å skrive den i samtalen.
- **Kjører ett dokument per forsøk med faste innstillinger.** Planen lagrer lesemotor, modell, tenkenivå, språk og instruks. En navngitt person godkjenner den før noe leses. Endringer gir en ny versjon; tidligere forsøk står urørt.
- **Lagrer beleggene.** For hvert forsøk: nøyaktig input, råsvar, ordrette sitater med plassering (PDF-side, Word-blokk, ark og celleområde, tekstlinje eller CSV-rad) og automatiske kontroller av svaretiketter, sitater og dekning.
- **Registrerer menneskelig kontroll.** En person godkjenner, korrigerer eller avviser hver vurdering med begrunnelse. Automatiske kontroller registreres aldri som menneskelig kontroll.
- **Eksporterer til Excel.** Resultater, belegg, forsøk og kontroller samles i én arbeidsbok, med kontrollsporet i en egen mappe. CSV kan velges ved behov.

Samtalen foregår i Claude Code eller Codex. Pluginen legger til bokføringen og den repeterbare lesingen; assistenten hjelper fortsatt med spørsmålet, kriteriene og vanskelige filer.

## Hva den ikke gjør

- Den sammenstiller ikke på tvers av dokumenter. Hver fil er én enhet; sammenligningen gjør du eller assistenten ut fra eksporten.
- Den prøver ikke på nytt, bytter ikke modell og faller ikke tilbake til betalt API på egen hånd. Feil og tidsavbrudd stopper køen og vises.
- Den leser ikke diagrammer, bilder eller innebygde objekter, og beregner ikke regnearkformler.
- Den kjører bare på Windows og trenger et lokalt Python-miljø, som installasjonsprogrammet ordner.

## Installasjon

Repoet er privat. Nedlasting fra GitHub krever tilgang; en kollega kan også få ZIP-filen direkte.

### La assistenten gjøre det

Lim én av disse inn i en ny samtale. Assistenten laster ned og verifiserer utgaven, og kjører enten installasjonen eller gir deg det ene steget den ikke skal gjøre selv.

Claude Code:

> Installer Systematic Document Analysis for Claude Code. Utgivelsesside: https://github.com/emilmsh/systematic-document-analysis/releases/latest (privat repo; bruk eksisterende gh-innlogging, eller be meg laste ned ZIP-en hvis du ikke får tilgang). Last ned systematic-document-analysis-windows.zip og SHA256SUMS.txt, verifiser sjekksummen, pakk ut ZIP-en i en mappe under Nedlastinger, kjør `installer.cmd claude --non-interactive` fra den mappen og vis meg utskriften. Kjør deretter `claude plugin list` og bekreft at systematic-document-analysis er aktivert. Ikke endre andre plugins, innstillinger eller filer, og ikke kjør reader_setup.cmd eller settings.cmd uten at jeg ber om det.

ChatGPT-appen / Codex:

> Installer Systematic Document Analysis for Codex. Utgivelsesside: https://github.com/emilmsh/systematic-document-analysis/releases/latest (privat repo; bruk eksisterende gh-innlogging, eller be meg laste ned ZIP-en hvis du ikke får tilgang). Last ned systematic-document-analysis-windows.zip og SHA256SUMS.txt, verifiser sjekksummen og pakk ut ZIP-en i en mappe under Nedlastinger. Vis meg mappestien, slik at jeg kan dobbeltklikke installer.cmd i Filutforsker og velge Codex. Overlat selve installasjonssteget til meg. Når jeg bekrefter, kjør `codex plugin list` og sjekk at systematic-document-analysis er aktivert. Ikke endre andre plugins, innstillinger eller filer.

Start en ny samtale etterpå, slik at appen laster pluginen.

### Manuelt

1. Last ned [Windows-ZIP-en](https://github.com/emilmsh/systematic-document-analysis/releases/latest/download/systematic-document-analysis-windows.zip) fra [siste utgave](https://github.com/emilmsh/systematic-document-analysis/releases/latest) og pakk den ut.
2. Dobbeltklikk `installer.cmd` i Filutforsker og velg Claude Code, Codex eller begge. Programmet klargjør Python 3.12 eller nyere, installerer et manglende kommandolinjeverktøy for appen, registrerer pluginen og viser installasjonsmappen.
3. Dobbeltklikk `reader_setup.cmd` for å logge inn til lesing med abonnementet ditt, og start deretter en ny lokal samtale. Første oppstart installerer Python-avhengighetene.

Lesing med abonnementet ditt bruker appens egen CLI. Mangler den, installerer `reader_setup.cmd` den; innloggingen fullfører du selv. `ocr_setup.cmd` installerer lokal OCR for skannede PDF-er. `settings.cmd` åpner en lokal fil for valgfrie API-nøkler.

### Oppdateringer

Kjør `update.cmd` fra den installerte mappen for å se etter en nyere utgave, installere den eller velge bare varsle (standard), automatisk eller av. Start en ny samtale etter oppdatering. Se [installasjon og oppdateringer](docs/UPDATES.md) for innstillinger og feilsøking.

## Bruk

Legg dokumentene i en mappe og åpne mappen i appen. Beskriv så oppgaven, for eksempel:

> Bruk Systematic Document Analysis på filene i C:\Users\meg\Documents\Årsrapporter\dokumenter. Jeg vil vite hvordan hver virksomhet rapporterer om egen bruk av KI. Hjelp meg å definere kriterier og svaralternativer. Bruk codex_cli med gpt-5.6-terra og tenkenivå high, kommentarer på norsk. Vis planen, tekstdekningen og nøyaktig input før jeg godkjenner. Kjør deretter alle dokumentene, vis svarene med sitater og plassering, og eksporter resultatene. Ikke registrer menneskelig kontroll på mine vegne.

Assistenten inspiserer den uttrukne teksten, foreslår kriterier, viser planen og den nøyaktige inputpakken, og venter på din godkjenning. Dokumentene kjøres så ett om gangen. Du kan stoppe, gjenoppta og se enkeltforsøk, registrere kontroll og eksportere.

Vert og lesemotor velges uavhengig: Claude Code eller Codex som samtaleapp; `claude_cli` (standard `sonnet`, high), `codex_cli` (standard `gpt-5.6-terra`, high) eller en API-motor med eksplisitt modell-ID som leser. CLI-motorene bruker abonnementsinnloggingen din; API-motorer faktureres av leverandøren. Ønsket modell og tenkenivå lagres; om leverandøren faktisk fulgte tenkenivået, vet vi bare når den rapporterer det.

Valgfrie API-nøkler legges i filen `settings.cmd` åpner, utenfor prosjektet. Del den ikke, og be ikke en assistent lese den. Analysedata lagres i `%LOCALAPPDATA%\systematic-document-analysis` og deles av begge appene; `SDA_DATA` velger en annen mappe.

## Dokumentasjon

- [Start her](START_HER.md)
- [Installasjon og oppdateringer](docs/UPDATES.md)
- [Oppsett og deling](docs/SETUP_AND_SHARING.md)
- [Filformater](docs/SOURCE_FORMATS.md) og [OCR og store dokumenter](docs/DOCUMENT_PROCESSING.md)
- [Fem eksempelmapper](examples/README.md) med fiktive filer. Valgfritt; pluginen er laget for dine egne dokumenter.

Full dokumentasjon og utviklingsveiledning står i den engelske [README](README.md) og [DEVELOPMENT.md](DEVELOPMENT.md).

Skapt og utviklet av Emil Mathias Strøm Halseth, med utviklingshjelp fra OpenAI Codex og Anthropic Claude Code.
