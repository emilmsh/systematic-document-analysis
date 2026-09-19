"""English reading copies alongside unchanged audit files and source quotations."""
import csv
import json
from .languages import FIELD_NAMES, public_result
from .parametre import fra_plan
from .prompt import bygg_systeminstruks


HEADERS = dict(FIELD_NAMES, antall_forsok='attempt_count', modell_onsket='requested_model',
               modell_rapportert='reported_model', tenkenivaa_onsket='requested_reasoning_effort',
               api_provider_valg='requested_provider', maks_output_tokens='max_output_tokens',
               sesjon_id='session_id', merknad='note', fysisk_side='physical_page',
               kriterium='criterion_id', sitat_funnet_paa_side='quote_found_on_page', nr='number',
               startet='started', avsluttet='finished', tid='time', opprinnelig='original', nytt='new')


def write_english_export(directory, analysis, versions, criterion_ids):
    """Translate headers, never values or user-controlled criterion IDs."""
    headers = dict(HEADERS)
    for criterion in criterion_ids:
        for old, new in [('svar','answer'), ('kontroll','review'), ('validering','validation')]:
            headers[f'{criterion}_{old}'] = f'{criterion}_{new}'
    for old, new in [('resultater','results'), ('forsok','attempts'), ('belegg','evidence'), ('kontroll','reviews')]:
        with (directory/f'{old}.csv').open(encoding='utf-8-sig', newline='') as source:
            rows = list(csv.reader(source, delimiter=';'))
        rows[0] = [headers.get(field, field) for field in rows[0]]
        with (directory/f'{new}.csv').open('w', encoding='utf-8-sig', newline='') as target:
            csv.writer(target, delimiter=';').writerows(rows)
    lines = [f"# Analysis plan: {analysis['navn']}", '',
             'Instructions below use the current template. The exact historical input is preserved in each attempt directory.', '']
    for version in versions:
        plan = version['plan']
        lines += [f"## Version {version['versjon']} ({version['status']})", '',
                  f"Approved by: {version.get('godkjent_av') or 'not approved'}", '',
                  f"Change note: {version.get('endringsnotat') or ''}", '',
                  '### Request', '', version['oppgavetekst'], '', '### Reader settings', '',
                  '```json', json.dumps(public_result(fra_plan(plan)), ensure_ascii=False, indent=2), '```', '',
                  '### Criteria (labels and wording preserved)', '', '```json',
                  json.dumps(public_result(plan)['criteria'], ensure_ascii=False, indent=2), '```', '',
                  '### Reader instruction', '', '```text', bygg_systeminstruks(plan), '```', '']
    (directory/'plan-summary.md').write_text('\n'.join(lines), encoding='utf-8')
    (directory/'README.md').write_text('''# Systematic Document Analysis — export

Start with **results.csv**, **evidence.csv**, **attempts.csv**, **reviews.csv** and **plan-summary.md**.
CSV files use semicolons and UTF-8 with BOM. Language is recorded per plan/run; quotations and
answer labels are preserved exactly. A mixture of plan versions, languages or engines may affect comparability.
Evidence includes source_format, source_unit and source_location. Only PDFs have physical_page values.
Other locators identify Word blocks, text lines, CSV records or workbook sheets and cell ranges.
The legacy fields side/sider_lest are source-unit IDs, not page numbers for non-PDF files.
Source profiles in resultater.json record extraction scope, structure and missing formula caches.
Full reading coverage refers to extracted units only; omitted objects are not evidence of absence.

The English CSV files are reading copies with translated headers. Recorded values remain unchanged:
`ja`/`JA` = yes, `nei`/`NEI` = no; `simulert` = simulated (no model call).
Run states include `fullført` (completed), `planlagt` (planned), `kjører` (running),
`stoppet` (stopped), `stoppet_uleselig` (unreadable), `feilet` (failed),
`uavklart` (uncertain), `valideringsfeil` (validation failed).
Review states include `ikke_kontrollert` (not reviewed), `godkjent` (approved),
`rettet` (corrected), `avvist` (rejected). Automatic validation is not human review.
Reading coverage reports `sider` (pages) and `ufullstendig` (incomplete).

For the audit trail, **resultater.json** contains the recorded data and all plan versions.
**forsok/<attempt-id>/** contains input.json, manifest.json, systeminstruks.txt and raasvar.txt
when available: the exact input, execution metadata, instruction and raw answer.
The Norwegian CSV/Markdown files are retained for existing workflows. Technical field names,
status codes and the internal response schema remain stable across languages.
Optional source copies are in **kilder/**. Physical PDF pages count from 1.

Failed or unreadable runs are not evidence of absence. Inspect validation failures and source
quotations before relying on results. Only an explicitly recorded human review counts as reviewed.
Edits to an export are not imported back into the authoritative local database.
''', encoding='utf-8')
