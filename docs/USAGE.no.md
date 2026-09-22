# Systematic Document Analysis

En plugin for Claude Code og Codex for systematisk analyse av dokumenter, regneark og tekstfiler etter avtalte kriterier. Den behandler én fil om gangen og tar vare på hva modellen fikk, hva den svarte, hvilke sitater den bygde på og hvordan et menneske kontrollerte resultatet.

[English](USAGE.md) · [Start her](../README.md) · [Installasjon og oppdateringer](UPDATES.md)

## Hurtiginstallasjon — Windows

**Du trenger bare å dobbeltklikke `installer.cmd`.** Det installerer pluginen og eventuelt manglende kommandolinjeverktøy (CLI), lar deg velge lesemotor og sjekker abonnementsinnloggingen. Er CLI-et ikke innlogget med abonnement, starter innloggingen, og du fullfører den i nettleseren. Eksisterende abonnementsinnlogging brukes videre. At du er innlogget i skrivebordsappen, er ikke en bekreftelse på at CLI-et er innlogget.

1. Last ned **[Windows-ZIP-en](https://github.com/emilmsh/systematic-document-analysis/releases/latest/download/systematic-document-analysis-windows.zip)** og pakk den ut under Nedlastinger. Gjeldende utgave er **[0.8.10](https://github.com/emilmsh/systematic-document-analysis/releases/tag/v0.8.10)**. Privat repo: logg inn med tilgang, eller bruk en ZIP du har fått fra en kollega.
2. Åpne den utpakkede mappen i Filutforsker, dobbeltklikk **installer.cmd**, velg **1 = Installer**, deretter **1 = Claude Code, 2 = Codex eller 3 = begge**. Kjør som din vanlige Windows-bruker, utenfor terminalen i Codex.
3. **Fortsett i samme installasjonsvindu:** velg lesemotor, **1 = Codex / ChatGPT, 2 = Claude Code eller 3 = begge**, og fullfør eventuell innlogging med riktig konto i nettleseren. Vent til installasjonsvinduet bekrefter innloggingen. Velg **4 = hopp over** hvis du skal bruke API eller sette opp lesemotoren senere. Valg av lesemotor er uavhengig av appen du valgte i steg 2.
4. Åpne arbeidsmappen i **Code-fanen** i Claude eller i Codex, start en **ny lokal samtale**, og beskriv oppgaven: **«Bruk Systematic Document Analysis. Jeg vil undersøke hvordan disse årsrapportene omtaler egen bruk av KI. Filene ligger i [mappe].»**

Førstegangsoppsett krever internett. Installasjonsprogrammet ordner Python og installerer den valgte appens kommandolinjeverktøy hvis det mangler; du trenger ikke bruke terminalen selv.

**`installer.cmd reader` er en hjelper for senere bruk**, for eksempel hvis du hoppet over eller avbrøt innloggingen. Du trenger ikke installere pluginen på nytt. For å bytte konto kan du kjøre `installer.cmd reader claude --login` eller `installer.cmd reader codex --login` i en terminal.

Du kan klargjøre og være innlogget i begge lesermotorene samtidig. Hver analyse velger fortsatt én lesermotor uttrykkelig; oppsett av begge aktiverer ikke automatisk bytte mellom dem.

**Azure AI Foundry:** Åpne `installer.cmd` → **Innlogging og innstillinger** → **API-innstillinger**, og fyll inn `AZURE_AI_API_KEY` lokalt. Dette støtter også andre Foundry-modeller enn OpenAI. Oppgi ressursendepunkt, deployment-navn og grensesnitt (`responses`, `chat_completions` eller `anthropic_messages`) i analyseplanen. Modellen må støtte valgt JSON-skjema og innstillinger. Ingen ekstra SDK installeres. Se [Azure-oppsett og avgrensninger](USAGE.md#azure-ai-foundry).

## Prosjektmappe og resultater

Velg en synlig prosjektmappe i samtalen. Planer og inputforhåndsvisninger lagres der før kjøring.
Hver eksport får en ny mappe med én Excel-arbeidsbok, én plan, én startfil, kildekopier og et eget
område for kontrollsporet. CSV er valgfritt. Begynn i `START_HERE.md` i prosjektmappen.
Excel-endringer endrer ikke registrerte resultater eller menneskelig kontroll.
Se [Prosjektfiler og eksportformater](PROJECT_FILES.md).

## Hvorfor

En samtaleassistent kan lese én rapport og svare på spørsmål om den. Det holder ikke når de samme spørsmålene skal besvares for førti årsrapporter, en bunke tilbud eller en mappe regneark, og svarene skal brukes senere. Da må du vite at alle dokumentene ble lest med samme instruks, modell og innstillinger, at hvert svar er knyttet til et sitat du kan slå opp, og at noen faktisk har kontrollert resultatet. Det gir ikke en vanlig samtale. Det gjør denne pluginen, uten at du forlater appen du allerede bruker.

## Hva den gjør

- **Leser filer fra en mappe du velger.** PDF, DOCX, XLSX, CSV/TSV, TXT og Markdown. Skannede PDF-er kan OCR-behandles lokalt. Store filer leses i avgrensede deler før funnene settes sammen i ett ekstra kall, og alle kallene lagres.
- **Bruker kriterier du definerer.** En liten JSON-fil lister spørsmålene, tillatte svar og tolkningsregler. Assistenten hjelper deg å skrive den i samtalen.
- **Kjører ett dokument per forsøk med faste innstillinger.** Planen lagrer lesemotor, modell, tenkenivå, språk og instruks. Assistenten kan inspisere kildetekst under forberedelsen; en navngitt person godkjenner planen før lesemotoren starter. Endringer gir en ny versjon; tidligere forsøk står urørt.
- **Lagrer beleggene.** For hvert forsøk: nøyaktig input, råsvar, ordrette sitater med plassering (PDF-side, Word-blokk, ark og celleområde, tekstlinje eller CSV-rad) og automatiske kontroller av svaretiketter, sitater og dekning.
- **Registrerer menneskelig kontroll.** En person godkjenner, korrigerer eller avviser hver vurdering med begrunnelse. Automatiske kontroller registreres aldri som menneskelig kontroll.
- **Eksporterer til Excel.** Resultater, belegg, forsøk og kontroller samles i én arbeidsbok, med kontrollsporet i en egen mappe. CSV kan velges ved behov.

Samtalen foregår i Claude Code eller Codex. Pluginen legger til bokføringen og den repeterbare lesingen; assistenten hjelper fortsatt med spørsmålet, kriteriene og vanskelige filer.

## Hva den ikke gjør

- Den sammenstiller ikke på tvers av dokumenter. Hver fil er én enhet; sammenligningen gjør du eller assistenten ut fra eksporten.
- Den prøver ikke på nytt, bytter ikke modell og faller ikke tilbake til betalt API på egen hånd. Feil og tidsavbrudd rapporteres per kjøring mens de øvrige kjøringene fullføres.
- Den leser ikke diagrammer, bilder eller innebygde objekter, og beregner ikke regnearkformler.
- Den kjører bare på Windows og trenger et lokalt Python-miljø, som installasjonsprogrammet ordner.

## Installasjon

Repoet er privat. Nedlasting fra GitHub krever tilgang; en kollega kan også få ZIP-filen direkte.

### La assistenten gjøre det

Lim én av disse inn i en ny samtale. Assistenten laster ned og verifiserer utgaven, og kjører enten installasjonen eller viser deg hvordan du starter den selv. **Claude-prompten bruker `--non-interactive`, som hopper over innloggingen.** Etter denne varianten bruker du `installer.cmd reader` ved behov. Ved vanlig dobbeltklikk på `installer.cmd` er innloggingen inkludert.

Claude Code:

> Installer Systematic Document Analysis for Claude Code. Utgivelsesside: https://github.com/emilmsh/systematic-document-analysis/releases/latest (privat repo; bruk eksisterende gh-innlogging, eller be meg laste ned ZIP-en hvis du ikke får tilgang). Last ned systematic-document-analysis-windows.zip og SHA256SUMS.txt, verifiser sjekksummen, pakk ut ZIP-en i en mappe under Nedlastinger, kjør `installer.cmd claude --non-interactive` fra den mappen og vis meg utskriften. Kjør deretter `claude plugin list` og bekreft at systematic-document-analysis er aktivert. Ikke endre andre plugins, innstillinger eller filer, og ikke kjør installer.cmd reader eller installer.cmd settings uten at jeg ber om det.

ChatGPT-appen / Codex:

> Installer Systematic Document Analysis for Codex. Utgivelsesside: https://github.com/emilmsh/systematic-document-analysis/releases/latest (privat repo; bruk eksisterende gh-innlogging, eller be meg laste ned ZIP-en hvis du ikke får tilgang). Last ned systematic-document-analysis-windows.zip og SHA256SUMS.txt, verifiser sjekksummen og pakk ut ZIP-en i en mappe under Nedlastinger. Vis meg mappestien, slik at jeg kan dobbeltklikke installer.cmd i Filutforsker og velge Codex. Overlat selve installasjonssteget til meg. Når jeg bekrefter, kjør `codex plugin list` og sjekk at systematic-document-analysis er aktivert. Ikke endre andre plugins, innstillinger eller filer.

Hvis innloggingen ble hoppet over, åpne **installer.cmd**, velg Innlogging og innstillinger → Lesermotor og innlogging, deretter ønsket lesemotor. Hjelperen bruker eksisterende abonnementsinnlogging eller starter innlogging ved behov. Start deretter en ny samtale, slik at appen laster pluginen.

### Manuelt

1. Last ned [Windows-ZIP-en](https://github.com/emilmsh/systematic-document-analysis/releases/latest/download/systematic-document-analysis-windows.zip) fra [siste utgave](https://github.com/emilmsh/systematic-document-analysis/releases/latest) og pakk den ut.
2. Dobbeltklikk `installer.cmd` i Filutforsker og velg Claude Code, Codex eller begge. Programmet klargjør Python 3.12 eller nyere, installerer et manglende kommandolinjeverktøy for appen, registrerer pluginen og viser installasjonsmappen.
3. I samme vindu velger du lesemotor, **1 = Codex / ChatGPT, 2 = Claude Code eller 3 = begge**, og fullfører eventuell innlogging i nettleseren. Installeringen sjekker innloggingen før den melder at oppsettet er ferdig. **4 = hopp over** utsetter dette steget eller lar deg bruke API. Start deretter en ny lokal samtale. Første oppstart installerer Python-avhengighetene.

Lesing med abonnementet ditt bruker appens egen CLI. Normalinstallasjonen klargjør valgt CLI og lokal OCR med norsk og engelsk språkstøtte; innloggingen fullfører du selv. PATH håndteres automatisk. Lesesesjonene får filverktøy, parsere, PDF-sidebilder og OCR i en egen arbeidsmappe per kjøring. `installer.cmd reader` og `installer.cmd ocr` brukes ved senere oppsett eller reparasjon. `installer.cmd settings` åpner en lokal fil for valgfrie API-nøkler.

### Oppdateringer

Kjør `installer.cmd update` fra den installerte mappen for å se etter en nyere utgave, installere den eller velge bare varsle (standard), automatisk eller av. Start en ny samtale etter oppdatering. Se [installasjon og oppdateringer](UPDATES.md) for innstillinger og feilsøking.

## Bruk

**Kontroller forutsetningene før oppstart.** Tilgjengelige verktøy, innlogging til lesemotoren, spesifiserte kriterier og svaralternativer, dokumentutvalg og en godkjent plan må være på plass. Manglende felles forutsetninger blokkerer oppstart, med årsaken i `show_status`. Rett eller avklar problemet, kontroller på nytt og be uttrykkelig om å fortsette. Planendringer krever ny godkjenning.

**Problemer i én kjøring stopper ikke de andre.** Uleselige kilder, tidsavbrudd, leserfeil og mangelfulle svar eller belegg registreres til oppfølging. De øvrige kjøringene får fullføre før dere gjennomgår problemene samlet. Resultater og tilgjengelige råsvar bevares; feilede eller uavklarte forsøk kjøres ikke automatisk på nytt og fremstilles ikke som vellykkede. Feil i felles infrastruktur eller bekreftet bortfall av lesertilgang kan fortsatt blokkere nye avhengige kall.

Tillatte svar som «uklart» eller «ikke omtalt» er gyldige funn når kravene til belegg og lesedekning er oppfylt. Resultater kan først omtales som menneskelig kontrollert når kontrollen faktisk er gjort.

**Innlogging er en sperre før analysen starter.** Claude- og Codex-leserne kontrollerer abonnementsinnloggingen før hvert CLI-kall. Manglende eller uklar innlogging blokkerer nye kall; en vanlig CLI-feil feiler bare den aktuelle kjøringen. Assistenten skal forklare hvordan du logger inn og kan fortsatt forberede kriterier og plan, men skal ikke erstatte analysen med egne underagenter eller direkte lesing. Etter innlogging må oppsettet kontrolleres på nytt før du ber om å fortsette.

Åpne en vanlig prosjektmappe i appen og legg egne kildefiler i undermappen `dokumenter`. Du trenger verken Git eller en eksempelkjøring. Beskriv oppgaven, for eksempel:

> Bruk Systematic Document Analysis. Jeg vil undersøke hvordan disse årsrapportene omtaler egen bruk av KI. Filene ligger i dokumenter-mappen.

Du trenger ikke ferdige kriterier eller tekniske innstillinger. Assistenten er instruert til å avklare hva du ønsker å finne ut, inspisere filene, foreslå spørsmål og svaralternativer og spørre om valg som faktisk påvirker analysen. Den skal skille dine krav fra egne forslag og si fra om manglende eller ustøttede kilder. Dere kan utvikle problemstillingen sammen og eventuelt prøve et lite, avtalt utvalg først.

Før lesemotoren starter, får du en kort plan med dokumentutvalg, kriterier, håndtering av usikkerhet, lesemotor/modell og plassering av resultatene. Detaljert plan og nøyaktig input er tilgjengelig for inspeksjon. Du godkjenner den konkrete planen og oppgir ansvarlig person. Assistenten foreslår normalt appens abonnementsbaserte lesemotor, samtalens språk, en ny analyseundermappe og Excel-resultater; du kan endre valgene. Kontroller planen: veiledning i samtalen reduserer unødige feil, men garanterer ikke at assistenten har forstått alt.

Dokumentene kjøres deretter ett om gangen. Du kan stoppe, gjenoppta og se enkeltforsøk, registrere faktisk menneskelig kontroll og eksportere. Endrede kriterier krever en ny planversjon og godkjenning.

Vert og lesemotor velges uavhengig: Claude Code eller Codex som samtaleapp; `claude_cli` (standard `sonnet`, high), `codex_cli` (standard `gpt-5.6-terra`, high) eller en API-motor med eksplisitt modell-ID som leser. CLI-motorene bruker abonnementsinnloggingen din; API-motorer faktureres av leverandøren. Ønsket modell og tenkenivå lagres; om leverandøren faktisk fulgte tenkenivået, vet vi bare når den rapporterer det.

Valgfrie API-nøkler legges i filen `installer.cmd settings` åpner, utenfor prosjektet. Del den ikke, og be ikke en assistent lese den. Analysedata lagres i `%LOCALAPPDATA%\systematic-document-analysis` og deles av begge appene; `SDA_DATA` velger en annen mappe.

## Dokumentasjon

- [Start her](../README.md)
- [Installasjon og oppdateringer](UPDATES.md)
- [Oppsett og deling](SETUP_AND_SHARING.md)
- [Filformater](SOURCE_FORMATS.md) og [OCR og store dokumenter](DOCUMENT_PROCESSING.md)
- [Fem eksempelmapper](https://github.com/emilmsh/systematic-document-analysis/tree/main/examples/README.md) med fiktive filer. Valgfritt; pluginen er laget for dine egne dokumenter.

Se også den [engelske veiledningen](USAGE.md). Utviklingsmateriale ligger i [repoen](https://github.com/emilmsh/systematic-document-analysis).

Skapt og utviklet av Emil Mathias Strøm Halseth, med utviklingshjelp fra OpenAI Codex og Anthropic Claude Code.
