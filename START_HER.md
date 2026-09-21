# Start her

Systematic Document Analysis bruker avtalte kriterier likt på egne dokumenter, og bevarer sitater, modellvalg, råsvar og menneskelig kontroll.

Skapt og utviklet av **Emil Mathias Strøm Halseth**, med utviklingshjelp fra **OpenAI Codex** og **Anthropic Claude Code**.

1. Pakk ut Windows-pakken. Dobbeltklikk **installer.cmd** og velg Claude Code, Codex eller begge. Mangler egnet Python, lastes det automatisk ned et eget lokalt miljø. Førstegangsoppsett krever internett. Du kan også lime inn en av oppsettspromptene i [README](README.no.md#la-assistenten-gjøre-det) i Claude Code eller ChatGPT-appen og la assistenten laste ned og verifisere utgaven. Ikke kjør installer.cmd fra en terminal inne i Codex-appen; filene ville blitt omdirigert til feil sted, og installasjonsprogrammet nekter.
2. **Fortsett i samme installasjonsvindu.** Velg lesemotor: **1 = Codex / ChatGPT, 2 = Claude Code eller 3 = hopp over (API eller senere)**. Installeringen sjekker eksisterende abonnementsinnlogging og starter innlogging ved behov; du fullfører den i nettleseren. Vent på bekreftelsen i installasjonsvinduet. Du trenger bare **installer.cmd** til vanlig førstegangsoppsett. Hvis du hopper over eller avbryter innloggingen, kan du fullføre senere med **reader_setup.cmd**. For å bytte konto: `./reader_setup.cmd codex --login` eller `./reader_setup.cmd claude --login`. Valgfri API: dobbeltklikk **settings.cmd**, lim inn nøkkelen på riktig leverandørlinje i Notisblokk, lagre og lukk. Ikke lim nøkkelen inn i chatten.
3. **OCR klargjøres automatisk i installasjonen**, med norsk og engelsk språkstøtte. Du trenger ikke ordne PATH eller installere parsere selv. Hvis OCR-oppsettet avbrytes eller feiler, kan du reparere det med **ocr_setup.cmd**.
4. Start en ny lokal samtale med pluginen aktivert. Åpne en vanlig arbeidsmappe, for eksempel `Dokumenter/Min analyse`, med kildefilene i undermappen `dokumenter`. Du trenger ikke Git eller en teknisk prosjektstruktur.

Arbeidsmappen er mappen du velger for denne analysen. Pluginen installeres et annet sted. Assistenten kan lage kriteriefilen sammen med deg. Importer bare mappen med kilder; undermapper tas ikke automatisk med. Begge appene deler det lokale analyselageret. `show_setup` viser den faktiske datamappen.

> Bruk Systematic Document Analysis. Jeg vil undersøke hvordan disse årsrapportene omtaler egen bruk av KI. Filene ligger i dokumenter-mappen.

Beskriv din egen oppgave med vanlige ord. Du trenger ikke ha kriteriene klare: assistenten skal foreslå et opplegg og stille nødvendige oppfølgingsspørsmål, med utgangspunkt i filene dine. Den foreslår også lesemotor, modell og en ny analyseundermappe med Excel-resultater. Før lesemotoren starter, får du en kort plan å kontrollere og godkjenne, med lenker til detaljene. Et lite pilotutvalg er valgfritt. Oppgi hvem som er ansvarlig for godkjenningen; assistenten skal ikke registrere menneskelig kontroll på dine vegne.

Fem valgfrie [eksempelmapper](examples/README.md) viser ulike bruksområder. Normal bruk krever ingen simulering eller eksempelkjøring. Se [oppsett og deling](docs/SETUP_AND_SHARING.md) for detaljer. Den utfylte nøkkelfilen er privat klartekst utenfor delingspakken og skal aldri deles.
