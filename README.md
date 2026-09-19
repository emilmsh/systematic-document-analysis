# OE Kildeanalyse

**Systematisk dokumentanalyse i ChatGPT desktop/Codex og Claude Code, med kildebelegg og sporbar historikk.** Beskriv oppgaven i samtalen, avtal kriteriene, velg modell og tenkenivå, og la pluginen lese dokumentene etter samme plan. Inspiser sitater, rett vurderinger og eksporter til Excel eller videre rapportarbeid.

Passer for å kode årsrapporter, kartlegge tiltak i rapporter og gjøre strukturerte dokumentgjennomganger. Hvert dokument leses i en egen CLI-sesjon eller et separat API-kall. Arbeidet starter og fortsetter i vertsappens samtale. Egne dokumenter er normal arbeidsflyt, og eksempelfiler er valgfrie.

## To uavhengige valg

| Lag | Valg | Ansvar |
|---|---|---|
| Vertsapp / orkestrator | ChatGPT desktop med lokal Codex-plugin, eller Claude Code | Dialog, kriterier, planlegging, godkjenning og oppfølging |
| Arbeidsagent / lesemotor | Codex CLI, Claude Code CLI, OpenAI API, Anthropic API, OpenRouter eller kompatibelt API | Ett dokument og ett registrert forsøk om gangen |

Begge vertsappene tilbyr samme MCP-verktøy, arbeidsrutine og motorvalg. Modellvalget i vertsamtalen gjelder ikke automatisk arbeidsagentene. Lokal ChatGPT desktop/Codex-støtte innebærer ikke en egen integrasjon i vanlig ChatGPT-nettchat eller Claude Desktop.

CLI-motorene har leverandørens agentlag (harness) rundt modellen, selv om vi begrenser verktøy og kontekst. API-motorene bruker ett direkte kall uten verktøy eller agentløkke. Samme modellnavn og tenkenivå garanterer derfor ikke identisk atferd på tvers av motorene. Kriterier, dokumenttekst, validering og historikk er felles.

## Last ned og del

- **[Siste release](https://github.com/emilmsh/oe-kildeanalyse/releases/latest)** – versjonsnotater og filer.
- **[Last ned Windows-pakken](https://github.com/emilmsh/oe-kildeanalyse/releases/latest/download/oe-kildeanalyse-windows.zip)** – samme ZIP for Claude Code, Codex eller begge.
- [Alle releases](https://github.com/emilmsh/oe-kildeanalyse/releases).

Repoet er privat. Mottakeren må ha GitHub-tilgang for å laste ned derfra. Du kan også sende ZIP-filen direkte til kolleger, uten at de trenger repo-tilgang. Pakken inneholder ingen innlogging, API-nøkler eller analysedata. Foreløpig støttes Windows, ikke macOS/Linux.

## Installer

1. Installer **Python 3.12 eller nyere** og CLI-en til appen du vil bruke (Claude Code og/eller Codex). Logg inn med din egen abonnementskonto. Skrivebordsappen alene er ikke tilstrekkelig dersom CLI-en mangler på PATH.
2. Pakk ut ZIP-filen og dobbeltklikk **installer.cmd**. Velg Claude Code, Codex eller begge.
3. Start en ny lokal samtale i valgt app med OE Kildeanalyse aktivert.

Du kan også kjøre `installer.cmd claude`, `installer.cmd codex` eller `installer.cmd begge` fra PowerShell med `./` foran filnavnet. Første serveroppstart henter Python-avhengigheter fra PyPI. API-nøkkel er bare nødvendig hvis du velger en API-lesemotor; CLI-ene brukes fortsatt til pluginregistrering.

Installasjonen kopierer pluginen til `%LOCALAPPDATA%/oe-kildeanalyse/plugins/<app>/oe-kildeanalyse` og registrerer markedsplassen `oe-kildeanalyse-lokal` med appens CLI. Codex får lokale Python- og serverstier generert på mottakerens PC. Begge appene bruker samme analysekjerne. Etter vellykket installasjon kan den utpakkede nedlastingsmappen slettes; behold installasjonsmappen i LocalAppData.

**Oppdatering:** Last ned ny ZIP og kjør samme installer på nytt, og start deretter en ny samtale. Hvis en eldre utviklingsinstallasjon bruker samme markedsplassnavn fra en annen mappe, stopper Claude-installasjonen med forklaring uten å endre den registreringen. Oppdater den gamle kopien med `claude plugin marketplace update oe-kildeanalyse-lokal` og `claude plugin update oe-kildeanalyse@oe-kildeanalyse-lokal`, eller fjern den gamle markedsplassregistreringen før du installerer fra ZIP. Fjern/deaktiver en eldre Codex-installasjon fra `personal` dersom du bytter til ZIP-installasjonen, så samme MCP-server ikke lastes to ganger.

Se [START_HER.md](START_HER.md) for kort brukerveiledning.

## Start en analyse

En vanlig mappe med PDF-filer er nok. Det kreves ingen spesielle filnavn eller Git-repo. Mappeimport tar PDF-er direkte i mappen, ikke undermapper; oppgi flere mapper ved behov. Filene må finnes lokalt og ha tekstlag. En enkel arbeidsmappe kan se slik ut:

```text
Min analyse/
  dokumenter/
    rapport-a.pdf
    rapport-b.pdf
  kriterier.json
```

Du trenger bare PDF-ene før start. Assistenten kan lage kriteriefilen sammen med deg. Åpne arbeidsmappen i appen og gi den tilgang til dokumentene og mulighet til å skrive kriteriefilen. Pluginen trenger ikke ligge i arbeidsmappen.

> Bruk OE Kildeanalyse på PDF-ene i [full mappesti]. Jeg vil undersøke [problemstilling]. Hjelp meg å formulere kriterier og svaralternativer. Bruk claude_cli med sonnet og high. Vis planen og lesedekningen før vi starter. Etter min godkjenning: kjør dokumentene, vis svar med kildebelegg og eksporter resultatene.

I Codex kan du erstatte motorvalget med `codex_cli`, for eksempel modellen `gpt-5.6-terra` og nivået `high`. Motoren kan velges uavhengig av appen.

## Modell, kontroll og resultater

| Lesemotor | Modell når ingen annen er valgt | Tenkenivå for nye planer |
|---|---|---|
| Claude Code (`claude_cli`) | `sonnet` | `high` |
| Codex (`codex_cli`) | `gpt-5.6-terra` | `high` |
| OpenAI (`openai_api`) | Må velges eksplisitt | `standard` |
| Anthropic (`anthropic_api`) | Må velges eksplisitt | `standard` |
| OpenRouter (`openrouter_api`) | Må velges eksplisitt | `standard` |
| Annet kompatibelt API (`kompatibel_api`) | Må velges eksplisitt | `standard` |

Du kan velge et annet modellnavn eller full modell-ID. Et alias som `sonnet` er ikke en låst modellversjon. Tenkenivåene er `low`, `medium`, `high`, `xhigh` og `max`; Codex CLI har også `ultra`. API-valget `standard` utelater effort-parameteren og bruker leverandørens standard. OpenAI, OpenRouter og kompatible API-er kan også forespørres med `none` og `minimal` når modellen støtter dem. Tilgjengelighet avhenger av modell og konto. CLI-en og OpenRouter kan tilpasse nivåer; ønsket nivå registreres, mens faktisk nivå merkes ukjent når det ikke rapporteres.

Valgene gjelder lesekjøringene og arves ikke fra app-samtalens modellinnstilling. Planen godkjennes før start. Endringer gir ny planversjon og endrer ikke tidligere kjøringer. Standard tidsgrense er 600 sekunder per dokument, og kan endres i planen.

Hvert svar har kriterium, vurdering og belegg med fysisk PDF-side og sitat. Originale svar og senere rettelser bevares. KI-svar starter som «ikke kontrollert»; registrert menneskelig kontroll bygger på brukerens vurdering.

Pluginen bevarer dokumentkopier og lagrer prosjekter, planer, kjøringer og eksport i `%LOCALAPPDATA%/oe-kildeanalyse`. Begge appene bruker dette lageret på samme PC. `OE_KILDEANALYSE_DATA` kan velge en annen datamappe. Eksportverktøyet viser resultatstien; du kan be assistenten kopiere eksporten til arbeidsmappen. CSV har semikolon og UTF-8 med BOM; JSON og Markdown følger med. Endringer i original-PDF-ene endrer ikke allerede importerte kopier.

## Valgfrie API-nøkler

API-støtten i denne kildeutgaven er kontrollert lokalt med falsk HTTP-transport, ikke med betalte modellkall. Modelltilgang, leverandørens parametertolkning og faglig kvalitet må kontrolleres ved faktisk bruk.

| Motor | Lokal miljøvariabel | API-format |
|---|---|---|
| `openai_api` | `OPENAI_API_KEY` | OpenAI Responses |
| `anthropic_api` | `ANTHROPIC_API_KEY` | Anthropic Messages |
| `openrouter_api` | `OPENROUTER_API_KEY` | OpenRouter Chat Completions |
| `kompatibel_api` | `OE_KILDEANALYSE_CUSTOM_API_KEY` | OpenAI-kompatibelt Chat Completions |

Sett nøkkelen som en **brukermiljøvariabel i Windows** (søk etter «Rediger miljøvariablene for kontoen din»), og avslutt og start vertsappen helt på nytt. Ikke lim nøkkelen inn i samtalen, kriteriefilen eller motorinnstillingene. Miljøvariabler er lokal konfigurasjon, ikke et kryptert nøkkelhvelv. `vis_oppsett` viser bare om nøkkelen er tilgjengelig; det gjør ingen API-kall. Både vertsappene og deres lokale prosesser kjører under din bruker.

Nøkkelverdien brukes bare som autentisering ved kall; den tas ikke inn i input, plan eller eksport. Eventuelt ekko av kjente API-nøkler i råsvar maskeres. Ved CLI-kjøring fjernes API-nøklene fra underprosessmiljøet, og abonnementsinnlogging kontrolleres. API-nøkler aktivert på PC-en bytter altså ikke lesemotor automatisk.

Eksempel i **begge vertsappene**:

> Bruk OE Kildeanalyse på PDF-ene i [full mappesti]. Velg openai_api med gpt-6-astra og high som lesemotor. Jeg har konfigurert nøkkelen lokalt. Vis kriterier, mottaker, modell, tenkenivå og tokenbudsjett før godkjenning. Ikke start modellkall før planen er godkjent.

API krever leverandørens modell-ID, ikke CLI-aliaset `sonnet`. For OpenRouter brukes for eksempel `openai/gpt-6-astra`. Velg bare modeller som støtter strukturert JSON etter skjemaet. Hvis en modell ikke støtter de valgte parametrene, beholdes feilen; pluginen fjerner dem ikke automatisk.

API-motorinnstillinger kan være `{"maks_output_tokens": 16384, "tidsavbrudd_sek": 600}`. Grensen på output gjelder leverandørens tokenbudsjett, som kan omfatte tenking; den er ikke en kronergrense. Anthropic bruker adaptive thinking når et eksplisitt tenkenivå er valgt, og krever en modell som støtter dette.

OpenRouter kan i tillegg bruke `{"provider": "OpenAI"}` for å begrense leverandøren. Uten dette velger OpenRouter leverandør for den navngitte modellen; dette vises i planen. Vi sender `require_parameters: true` og `allow_fallbacks: false`. Automatisk modellruting og variant-suffikser støttes ikke. OpenRouter kan oversette tenkenivåer, så faktisk levert nivå er fortsatt ukjent.

For andre leverandører velges `kompatibel_api`, eksplisitt modell-ID og `{"base_url": "https://leverandor.example/v1"}`. Nøkkelen for denne motoren sendes til akkurat denne mottakeren. API-et må støtte `/chat/completions` og `response_format` med JSON-skjema; ved valgt tenkenivå må det også støtte `reasoning_effort`. «Kompatibel» betyr ikke at alle leverandører eller modeller er prøvd. Denne utgaven følger ikke HTTP-omdirigeringer og bruker ikke proxy-/sertifikatinnstillinger fra miljøvariabler.

API-planen og inputpakken viser mottaker, modell, nivå, tokenbudsjett og forespørselen uten autentiseringsheaders. Den samme forespørselen inngår i inputhash og eksport. Rapportert modell, request-ID og forbruk bevares når leverandøren oppgir det. Feil, kvotestopp, tidsavbrudd og avbrudd gir ingen automatisk retry eller bytte til en annen motor; leverandøren kan likevel ha behandlet og fakturert et avbrutt kall.

API-formatene følger [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [OpenAI reasoning](https://developers.openai.com/api/docs/guides/reasoning), [Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs), [Anthropic effort](https://platform.claude.com/docs/en/build-with-claude/effort) og [OpenRouter Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs).

## Fem årsrapporter som eksempel

[Startprompt og oppgave](eksempler/arsrapporter-2024/STARTPROMPT.md) undersøker egen bruk av KI i Datatilsynet, Språkrådet, Forbrukerrådet, Medietilsynet og Kulturtanken. Utvalget er illustrativt, ikke representativt. [Kildelisten](eksempler/arsrapporter-2024/kilder.json) peker til rapportutgivernes PDF-er.

Utviklingskopi: kjør `.venv/Scripts/python.exe bin/hent_arsrapporter.py`. Rapportene legges lokalt i `eksempler/arsrapporter-2024/dokumenter/`. PDF-ene legges ikke i Git eller plugin-releases. Scriptet kan også kjøres med vanlig Python; `pypdf` gir kontroll av tekstlag og sidetall.

## Begrensninger

PDF med tekstlag og ett dokument per lesekjøring støttes. OCR, DOCX og automatisk oppdeling av store dokumenter er ikke implementert. Lange rapporter kan overskride modellens kontekst; lange inputvisninger avkortes. CLI-flaggene begrenser kontekst og verktøy, men gir ikke full OS-isolasjon eller beskytter resultatlageret mot direkte filskriving fra samme bruker. Faktisk kvotebelastning og eventuell ekstraforbruksordning bestemmes av abonnementet, ikke CLI-ens listepris-estimat.

## Utvikling og releases

- `src/kildeanalyse/`: felles analyse-, lagrings- og eksportkode; `adaptere/` kobler til CLI-ene.
- `skills/kildeanalyse/SKILL.md`: arbeidsveiledningen som appen laster.
- `bin/installer.py`: felles installasjon; `bin/lag_release.py`: bygger én ren ZIP og SHA-256-fil.
- `tests/`: lokale kontroller og valgfrie syntetiske eksempler.
- `dist/v<versjon>/`: generert distribusjon; skal ikke redigeres eller legges i Git.
- [UTVIKLINGSSTRATEGI.md](UTVIKLINGSSTRATEGI.md): beslutninger og videre utvikling. [Testlogg](tests/TESTLOGG.md): gjennomførte kontroller.

```powershell
./oppsett.cmd
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe bin/lag_release.py
```

Ved en ny release oppdateres versjonen i `pyproject.toml`, `src/kildeanalyse/__init__.py` og plugin-/markedsplassmanifestene. Bygg ZIP, kontroller installasjon, commit og push, og opprett en GitHub Release med ZIP og `SHA256SUMS.txt`. Det stabile filnavnet gjør at nedlastingslenken øverst alltid peker til siste release.
