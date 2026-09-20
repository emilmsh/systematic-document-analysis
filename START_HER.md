# Start her

Systematic Document Analysis bruker avtalte kriterier likt på egne dokumenter, og bevarer sitater, modellvalg, råsvar og menneskelig kontroll.

1. Pakk ut Windows-pakken. Dobbeltklikk **installer.cmd** og velg Claude Code, Codex eller begge. Mangler egnet Python, lastes det automatisk ned et eget lokalt miljø. Førstegangsoppsett krever internett.
2. Velg lesemotor. Med abonnement: dobbeltklikk **reader_setup.cmd**, velg Codex eller Claude Code og følg innloggingsvinduet. Terminalalternativ: `./reader_setup.cmd codex --login` eller `./reader_setup.cmd claude --login`. Hjelperen installerer CLI ved behov; du fullfører leverandørens innlogging. Valgfri API: dobbeltklikk **settings.cmd**, lim inn nøkkelen på riktig leverandørlinje i Notisblokk, lagre og lukk. Ikke lim nøkkelen inn i chatten.
3. For skannede PDF-er: dobbeltklikk **ocr_setup.cmd**. Det installerer lokal Tesseract OCR med norsk og engelsk språkstøtte ved behov.
4. Start en ny lokal samtale med pluginen aktivert. Åpne en vanlig arbeidsmappe, for eksempel `Dokumenter/Min analyse`, med kildefilene i undermappen `dokumenter`. Du trenger ikke Git eller en teknisk prosjektstruktur.

Arbeidsmappen er mappen du velger for denne analysen. Pluginen installeres et annet sted. Assistenten kan lage kriteriefilen sammen med deg. Importer bare mappen med kilder; undermapper tas ikke automatisk med. Begge appene deler det lokale analyselageret. `show_setup` viser den faktiske datamappen.

> Bruk Systematic Document Analysis på [absolutt sti til dokumentmappen]. Undersøk [problemstilling] likt på tvers av filene. Hjelp meg med kriteriene. Undersøk uttrekket og diskuter utfordringer med skanning, tabeller, formler, store filer og hvilke deler vi bør prioritere. Bruk [lesemotor/modell/tenkenivå], og rapporter på norsk. Vis planen og nøyaktig input før start. Behold full dekning med mindre vi uttrykkelig avtaler noe annet. Eksporter resultatene med sitater og kildeplassering. Registrer ikke menneskelig kontroll på mine vegne.

Hvis du er usikker på lesemotor og modell, be assistenten forklare valgene før planen lages. Assistenten kan hjelpe med lokal installasjon når appen tillater det; innlogging og innliming av nøkler gjør du selv.

Fem valgfrie [eksempelmapper](examples/README.md) viser ulike bruksområder. Normal bruk krever ingen simulering eller eksempelkjøring. Se [oppsett og deling](docs/SETUP_AND_SHARING.md) for detaljer. Den utfylte nøkkelfilen er privat klartekst utenfor delingspakken og skal aldri deles.
