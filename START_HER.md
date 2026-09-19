# Start med OE Kildeanalyse

**Samme Windows-pakke fungerer i Claude Code og Codex.**

1. Du trenger Python 3.12+ og CLI-en til appen du bruker, innlogget med din egen abonnementskonto. CLI-en må finnes på PATH.
2. Pakk ut ZIP-filen. Dobbeltklikk `installer.cmd` og velg 1 (Claude Code), 2 (Codex) eller 3 (begge). Menyen registrerer pluginen, uten modellkall eller endring av innlogging.
3. Start en ny lokal samtale i appen med OE Kildeanalyse aktivert. Første serverstart installerer Python-avhengigheter og kan ta litt tid.

## Dine dokumenter

En vanlig mappe med PDF-er er nok. Oppgi hele stien. Mappeimport leser filene direkte i mappen; undermapper oppgis separat. PDF må ha tekstlag og ligge lokalt, også ved bruk av OneDrive. Kriterier kan assistenten hjelpe deg å formulere og lagre i en fil i arbeidsmappen.

> Bruk OE Kildeanalyse på PDF-ene i [full mappesti]. Jeg vil undersøke [problemstilling]. Hjelp meg å formulere kriterier og svaralternativer. Bruk motoren til appen jeg arbeider i, med tenkenivå high. Vis modell, plan og lesedekning før vi starter. Etter min godkjenning: kjør materialet, vis svar med sitater og PDF-sidetall og eksporter tabellen. Ikke registrer menneskelig kontroll på mine vegne.

Du kan velge modell selv: for eksempel `claude_cli / sonnet / high` eller `codex_cli / gpt-5.6-terra / high`. Lesemotorens modellvalg er uavhengig av samtalens modell. Endringer får ny planversjon. Simulering og eksempler er valgfrie.

## Hvor havner ting?

- Installasjon: `%LOCALAPPDATA%/oe-kildeanalyse/plugins/<app>/oe-kildeanalyse`. Behold denne mappen.
- Prosjektdata og eksport: `%LOCALAPPDATA%/oe-kildeanalyse`, eller valgt `OE_KILDEANALYSE_DATA`. Eksportverktøyet viser filstien.
- Etter vellykket installasjon kan du slette den utpakkede nedlastingsmappen. Innlogging og analyser følger ikke med ZIP-filen.

Oppdater ved å laste ned [siste release](https://github.com/emilmsh/oe-kildeanalyse/releases/latest), kjøre installer på nytt og åpne en ny samtale. Det private repoet krever GitHub-tilgang, men ZIP-filen kan deles direkte.

En gammel utviklingsinstallasjon kan bruke samme markedsplassnavn fra en annen mappe. Da gir installer en forklaring og bevarer den eksisterende registreringen. Se README for oppdatering eller flytting. Hvis en gammel Codex-plugin fra `personal` er aktivert, deaktiver den når du går over til ZIP-installasjonen.

Verktøyet støtter foreløpig Windows og PDF med tekstlag. Full OS-isolasjon og automatisk oppdeling av store dokumenter er ikke implementert. Se README for arbeidsflyt og begrensninger. Ved feil: ta med feilmeldingen til utvikleren; API-nøkler er ikke nødvendig.
