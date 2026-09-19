# Eksempel: intern bruk av kunstig intelligens i fem virksomheter

Fem offentlig tilgjengelige årsrapporter for 2024 er vilkårlig valgt fra norske virksomheter: Datatilsynet, Språkrådet, Forbrukerrådet, Medietilsynet og Kulturtanken. Dette er et illustrativt utvalg, ikke et statistisk tilfeldig eller representativt utvalg. Originalene og kildelenkene står i [kilder.json](kilder.json).

Last ned med `python bin/hent_arsrapporter.py` fra prosjektmappen. PDF-ene legges i `dokumenter/`; de publiseres ikke i kode-repoet eller plugin-ZIP-en. Filen `lesbarhet.json` viser lokal nedlastingskontroll, SHA-256, sidetall og eventuelle sider uten tekst når pypdf er tilgjengelig.

Kontroll 19. september 2026: Rapportene har henholdsvis 76, 85, 46, 111 og 77 sider og tekstlag. Kulturtankens fysiske side 77 gir ikke tekst ved uttrekk; visuell kontroll viser en grafisk bakside med logo og organisasjonsnavn. Pluginen vil varsle om den siden. Godkjenn eventuelt videre arbeid med merket lesedekning. Originalfilene er bevart uendret.

## Lim inn i en ny samtale med Systematic Document Analysis aktivert

> Bruk Systematic Document Analysis på de fem årsrapportene i [full sti til dokumenter-mappen]. Undersøk hvordan virksomhetene rapporterer om egen bruk av kunstig intelligens i 2024. Skill klart mellom KI som tema i samfunnsoppdraget og KI brukt internt i organisasjonen.
>
> Lag en kriteriefil sammen med meg med disse fire spørsmålene: (1) Er konkret intern bruk av KI omtalt? (2) Er intern opplæring i KI omtalt? (3) Er interne regler eller retningslinjer for KI omtalt? (4) Er oppnådde, målte virkninger av intern KI-bruk omtalt? Foreslå presise definisjoner før vi starter. Bruk svaralternativene «ja», «eksplisitt_nei», «uklart» og «ikke_omtalt». Planer, ambisjoner og forventede effekter teller ikke som gjennomførte tiltak eller målte virkninger. Manglende omtale betyr ikke at tiltaket ikke finnes.
>
> Foreslå lesemotoren som passer appen jeg bruker, med tenkenivå high. Vis modell, tenkenivå, lesedekning og samlet plan før du ber meg godkjenne kjøringen. Hvis noen sider ikke har tekst, vis hvilke og la meg velge om vi skal fortsette med tydelig merket lesedekning.
>
> Etter godkjenning: analyser de fem rapportene med ett dokument per kjøring. Oppgi fysisk PDF-side og korte, ordrette sitater for positive og eksplisitt negative svar. Eksporter tabell og belegg. Lag deretter en kort oppsummering i samtalen av mønstre og usikkerhet, basert på de lagrede resultatene. Ikke registrer menneskelig kontroll på mine vegne, og ikke generaliser fra disse fem til alle norske virksomheter.

Vil du styre modellen selv, legg til «Bruk claude_cli med sonnet og high» eller «Bruk codex_cli med gpt-5.6-terra og high», eller oppgi en annen tilgjengelig modell-ID.
