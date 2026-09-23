"""Human-readable datasets for arbitrary task results, using the plugin's XLSX runtime."""
from __future__ import annotations

import csv
import json
import math
import re
from collections import OrderedDict

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .task_dataset import add_result, describe, pointer, source_locations


def write_workbook(directory, analysis, versions, records, archive_name, *, include_csv=False, csv_directory=None, list_layout='sheets', compact=False):
    if list_layout not in ('sheets', 'inline'):
        raise ValueError('list_layout must be sheets or inline.')
    nb = versions[-1]['plan'].sprak == 'nb'
    tr = lambda no, en: no if nb else en
    book = Workbook()
    book.remove(book.active)
    used_names, overflow, notices = set(), [], []
    dictionary, datasets, run_rows = [], OrderedDict(), []

    def name_for(name):
        base = re.sub(r'[\\/*?:\[\]\x00-\x1f]', '_', name).strip(" '")[:31] or 'Data'
        candidate, index = base, 2
        while candidate.casefold() in used_names:
            suffix = f' {index}'
            candidate = base[:31-len(suffix)] + suffix
            index += 1
        used_names.add(candidate.casefold())
        return candidate

    overview_name = name_for(tr('Oversikt', 'Overview'))
    runs_name = name_for(tr('Kjøringer', 'Runs'))
    dictionary_name = name_for(tr('Variabler', 'Variables'))
    texts_name = name_for(tr('Lange tekster', 'Long texts'))
    results_name = name_for(tr('Resultater', 'Results'))

    def write_cell(cell, value):
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        if isinstance(value, int) and not isinstance(value, bool) and len(str(abs(value))) > 15:
            value = str(value)  # Excel's numeric precision must not change identifiers or exact integers.
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('Non-finite numbers cannot be exported as dataset values.')
        if isinstance(value, str):
            if ILLEGAL_CHARACTERS_RE.search(value):
                notices.append(tr('Kontrolltegn vises med synlige escape-sekvenser; originalen ligger i arkivet.',
                                  'Control characters use visible escape sequences; originals are in the archive.'))
                value = ILLEGAL_CHARACTERS_RE.sub(lambda m: f'\\u{ord(m[0]):04x}', value)
            # Keep long text inside the same workbook, with no truncation or loose attachments.
            if len(value) > 30000 or (len(value) > 2200 and cell.parent.title != texts_name):
                parts = [value[i:i+2000] for i in range(0, len(value), 2000)]
                first = len(overflow) + 2
                ref = f'{cell.parent.title}!{cell.coordinate}'
                overflow.extend([[ref, n, text] for n, text in enumerate(parts, 1)])
                value = tr('Hele teksten: ', 'Full text: ') + f'{texts_name} ({len(parts)} ' + tr('deler)', 'parts)')
                cell.hyperlink = f"#'{texts_name.replace(chr(39), chr(39)*2)}'!C{first}"
            cell.value = value
            cell.data_type = 's'  # Source text must never become an Excel formula.
        else:
            cell.value = value
            if isinstance(value, (int, float)):
                cell.number_format = '0' if isinstance(value, int) else '0.##########'

    def sheet(name, headers, rows, widths=None):
        if len(rows) > 1048575 or len(headers) > 16384:
            raise ValueError(f'{name}: dataset exceeds Excel limits; narrow the output contract or selected files.')
        ws = book.create_sheet(name)
        ws.sheet_view.showGridLines = False
        ws.freeze_panes = 'B2' if len(headers) > 5 else 'A2'
        for r, values in enumerate([headers, *rows], 1):
            for c, value in enumerate(values, 1):
                cell = ws.cell(r, c)
                write_cell(cell, value)
                cell.font = Font(name='Arial', size=11, color='243444')
                cell.alignment = Alignment(vertical='top', wrap_text=True)
                if r == 1:
                    cell.fill = PatternFill('solid', fgColor='233F5B')
                    cell.font = Font(name='Arial', size=11, bold=True, color='FFFFFF')
                    cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                elif r % 2 == 0:
                    cell.fill = PatternFill('solid', fgColor='F0F4F7')
        for c in range(1, len(headers)+1):
            ws.column_dimensions[get_column_letter(c)].width = (widths or {}).get(c, 24)
        header_lines = max((math.ceil(len(str(c.value or '')) / max(8, ws.column_dimensions[c.column_letter].width-2)) for c in ws[1]), default=1)
        ws.row_dimensions[1].height = max(30, min(100, header_lines*15+6))
        for row in ws.iter_rows(min_row=2):
            lines = max((sum(max(1, math.ceil(len(p) / max(8, ws.column_dimensions[c.column_letter].width-2)))
                             for p in str(c.value if c.value is not None else '').split('\n')) for c in row), default=1)
            ws.row_dimensions[row[0].row].height = min(409, max(22, lines*15+4))
        ws.auto_filter.ref = ws.dimensions
        return ws

    schema_groups = {}
    for record in records:
        run, doc, plan, chosen, view = (record[k] for k in ('run', 'document', 'plan', 'chosen', 'view'))
        aid = chosen['id'] if chosen else ''
        result = view['result'] if view else None
        validation = (view or {}).get('result_validation') or {}
        review = (view or {}).get('review_status', 'ikke kontrollert')
        accepted = bool(view and validation.get('gyldig') and review != 'avvist' and
                        (chosen['status'] == 'fullført' or view.get('result_origin') == 'human_correction'))
        if not view:
            state = tr('Ingen resultatleveranse', 'No result')
        elif review == 'avvist':
            state = tr('Avvist; ikke med i datasettet', 'Rejected; excluded from dataset')
        elif not accepted:
            state = tr('Ugyldig/uavklart; ikke med i datasettet', 'Invalid/uncertain; excluded from dataset')
        elif result == [] or result == {}:
            state = tr('Tomt resultat', 'Empty result')
        elif result is None:
            state = tr('Resultatet er null', 'Result is null')
        else:
            state = tr('Med i datasettet', 'Included in dataset')
        pid = run['planversjon_id']
        key = json.dumps(plan.output_schema, sort_keys=True, ensure_ascii=False)
        group = schema_groups.setdefault(key, pid) if compact else pid
        record['dataset_key'] = group
        tables = datasets.setdefault(group, describe(plan.output_schema))
        context = {'document': doc['navn'], 'document_id': doc['id'], 'run_id': run['id'], 'attempt_id': aid,
                   'plan_id': pid, 'source_sha256': doc['sha256'], 'review': review,
                   'simulated': bool(chosen and chosen['simulert']), 'origin': (view or {}).get('result_origin', ''),
                   'source': doc, 'plan': plan}
        if accepted:
            add_result(tables, result, context)
        record['dataset_included'] = accepted
        record['dataset_state'] = state
        validation_state = tr('Bestått', 'Passed') if validation.get('gyldig') else tr('Ikke bestått', 'Not passed') if validation else tr('Ikke kontrollert', 'Not checked')
        read = validation.get('lesedekning', {})
        coverage = f"{len(read.get('sider_lest_oppgitt', []))}/{len(doc['sider'])}" if validation else ''
        errors = chosen.get('feil') if chosen else run.get('merknad')
        if not errors:
            errors = '\n'.join(e.get('melding', str(e)) for e in validation.get('feil', []))
        limitations = ((view or {}).get('response') or {}).get('limitations', [])
        # The validator also records limitations as a Python-list string. Their
        # readable source values already have a dedicated column and issue row.
        warnings = '\n'.join(x.get('melding', '') for x in validation.get('advarsler', [])
                             if x.get('type') != 'validation_scope' and
                             not (x.get('type') == 'limitations' and limitations))
        run_rows.append([doc['navn'], run['status'], state, validation_state, review,
                         '\n'.join(limitations), errors or '', coverage, aid, run['id'], pid, doc['id'],
                         bool(chosen and chosen['simulert']), (chosen or {}).get('modell_onsket', ''),
                         (chosen or {}).get('modell_rapportert') or tr('Ikke rapportert', 'Not reported'),
                         plan.motorinnstillinger.get('tenkenivaa', ''), (chosen or {}).get('sesjon_id') or '',
                         doc['sha256'], warnings])

    overview = sheet(overview_name, [tr('Felt', 'Field'), tr('Verdi', 'Value')], [
        [tr('Analyse', 'Analysis'), analysis['navn']],
        [tr('Åpne først', 'Start here'), tr('Resultater har én rad per kjøring og variabler i kolonnene. Gjentatte poster ligger i koblede detaljfaner.',
                                         'Results has one row per run and variables in columns. Repeated records have linked detail sheets.')],
        [tr('Dokumentkjøringer', 'Document runs'), len(records)],
        [tr('Resultater med i datasettet', 'Results included in dataset'), sum(r['dataset_included'] for r in records)],
        [tr('Variabler', 'Variables'), tr('Se Variabler for feltnavn, definisjoner, datatyper og hva én rad betyr.',
                                        'See Variables for field names, definitions, data types and row units.')],
        [tr('Menneskelig kontroll', 'Human review'), tr('Automatisk validering er ikke menneskelig kontroll. Ugyldige og avviste kjøringer beholder sin rad, med tomme resultatvariabler.',
                                                     'Automatic validation is not human review. Invalid and rejected runs retain their row, with blank result variables.')],
        [tr('Tomme verdier', 'Missing values'), tr('Null og fraværende felt vises som tomme celler og listes i egne sporbarhetskolonner. Tom liste har null rader, ikke et negativt funn.',
                                                'Null and absent fields display as blank cells and are listed in provenance columns. An empty list has zero detail rows, not a negative finding.')],
        [tr('Dokumentasjon', 'Documentation'), archive_name],
        [tr('Redigering', 'Editing'), tr('Et eksportert øyeblikksbilde. Excel-endringer oppdaterer ikke kilder, råsvar eller kontrollhistorikk.',
                                       'An exported snapshot. Excel edits do not update sources, raw responses or review history.')],
    ], {1:32, 2:110})
    overview.freeze_panes = None
    overview.auto_filter.ref = None
    overview.cell(9, 2).hyperlink = archive_name

    def headers_for(table):
        names = set()
        headers = []
        for column in table.columns.values():
            label = column.schema.get('title') or '.'.join(column.path) or tr('Resultat', 'Result')
            if column.role == 'count':
                label += tr(' (antall)', ' (count)')
            base, i = str(label), 2
            while label.casefold() in names:
                label = f'{base} ({i})'
                i += 1
            names.add(label.casefold())
            headers.append(label)
        return headers

    meta = [('source_location', tr('Kildeplassering', 'Source location')),
            ('record_id', tr('Rad-ID', 'Record ID')), ('parent_id', tr('Overordnet rad-ID', 'Parent record ID')),
            ('ordinal', tr('Rekkefølge', 'Ordinal')), ('run_id', tr('Kjøring', 'Run')),
            ('attempt_id', tr('Forsøk', 'Attempt')), ('plan_id', tr('Planversjon', 'Plan version')),
            ('review', tr('Menneskelig kontroll', 'Human review')), ('simulated', tr('Simulert', 'Simulated')),
            ('origin', tr('Svargrunnlag', 'Result origin')), ('result_path', tr('Resultatsti', 'Result path')),
            ('null_fields', tr('Nullfelt', 'Null fields')), ('missing_fields', tr('Fraværende felt', 'Absent fields'))]

    if compact:
        meta = [m for m in meta if m[0] in ('source_location', 'record_id', 'parent_id', 'review')]

    # The primary dataset has exactly one row per selected run, including failed/unstarted runs.
    # Repeated values default to detail sheets; inline lists are an explicit option.
    primary_columns = []
    primary_headers = ([tr('Dokument', 'Document'), tr('Status', 'Status'), tr('Menneskelig kontroll', 'Human review'), tr('Kjøring', 'Run')]
                       if compact else [tr('Kjøring', 'Run'), tr('Dokument', 'Document')])
    for pid, tables in datasets.items():
        for table in tables.values():
            if table.repeated and list_layout == 'sheets':
                if not table.path:
                    header = (f'{pid}: ' if len(datasets) > 1 else '') + tr('Resultatposter (antall)', 'Result items (count)')
                    primary_headers.append(header)
                    primary_columns.append((pid, table, None))
                    dictionary.append([results_name, header, '/', tr('Antall poster i detaljfanen.', 'Number of detail records.'),
                                       'integer', pid, '/', tr('Én dokumentrad' if compact else 'Én kjøring', 'One document row' if compact else 'One run')])
                continue
            for label, col in zip(headers_for(table), table.columns.values()):
                prefix = '.'.join(p for p in table.path if p != '*')
                header = f'{prefix}.{label}' if prefix else label
                if len(datasets) > 1:
                    header = f'{pid}: {header}'
                while header.casefold() in {h.casefold() for h in primary_headers}:
                    header += tr(' (variabel)', ' (variable)')
                primary_headers.append(header)
                primary_columns.append((pid, table, col))
                kind = col.schema.get('type', tr('Ikke deklarert', 'Not declared'))
                kind = ', '.join(kind) if isinstance(kind, list) else kind
                if col.role == 'count':
                    kind = 'integer'
                if table.repeated:
                    kind = tr('Liste av ', 'List of ') + str(kind)
                dictionary.append([results_name, header, pointer(col.path) or '/',
                    col.schema.get('description') or (tr('Antall elementer i listen.', 'Number of list items.') if col.role == 'count' else tr('Ikke beskrevet i planen.', 'Not described in the plan.')),
                    kind, pid, pointer(table.path) or '/', tr('Én dokumentrad' if compact else 'Én kjøring', 'One document row' if compact else 'One run')])
    primary_rows = []
    for record in records:
        run, chosen, view = record['run'], record['chosen'], record['view']
        values, nulls, missing, locations = [], [], [], []
        for pid, table, col in primary_columns:
            selected = [r for r in table.rows if r['run_id'] == run['id']]
            if pid != record['dataset_key'] or not record['dataset_included']:
                values.append(None)
                continue
            if col is None:
                values.append(None if view['result'] is None else len(selected))
                continue
            present = [r['values'].get(col.key) for r in selected]
            path = pointer(table.path + col.path) or '/'
            if any(col.key not in r['present'] for r in selected):
                missing.append(path)
            if any(col.key in r['present'] and r['values'].get(col.key) is None for r in selected):
                nulls.append(path)
            if table.repeated:
                # Number list items so multi-line passages cannot be confused with separate findings.
                values.append('\n\n'.join(f'{i}. ' + (tr('(mangler)', '(missing)') if col.key not in r['present'] else
                    '(null)' if v is None else str(v).lower() if isinstance(v, bool) else str(v))
                    for i, (r, v) in enumerate(zip(selected, present), 1)) if selected else None)
            else:
                values.append(present[0] if present else None)
            for row in selected:
                location = source_locations(table, row, row['plan'], row['source'])
                if location:
                    locations.append(location)
        prefix = ([record['document']['navn'], run['status'] + ': ' + record['dataset_state'],
                   (view or {}).get('review_status', 'ikke kontrollert'), run['id']] if compact else
                  [run['id'], record['document']['navn']])
        primary_rows.append([*prefix, *values])
        record['null_fields'] = '\n'.join(dict.fromkeys(nulls))
        record['missing_fields'] = '\n'.join(dict.fromkeys(missing))
        record['source_locations'] = '\n'.join(dict.fromkeys(locations))
    widths = {1:32, 2:40, 3:22, 4:14} if compact else {1:16, 2:30}
    for i, (_, table, col) in enumerate(primary_columns, len(primary_headers)-len(primary_columns)+1):
        if col is None:
            widths[i] = 22
            continue
        sizes = [len(str(row[i-1] or '')) for row in primary_rows]
        widths[i] = min(90, max(22, max(sizes, default=0)*0.65)) if table.repeated or col.schema.get('type') not in ('integer','number','boolean') else 16
    primary = sheet(results_name, primary_headers, primary_rows, widths)
    book.move_sheet(primary, offset=-book.index(primary))
    if include_csv and csv_directory:
        csv_directory.mkdir(parents=True, exist_ok=True)
        with (csv_directory / f'{results_name}.csv').open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(primary_headers)
            writer.writerows(primary_rows)
    summaries = []
    for pid, tables in datasets.items():
        for table in tables.values():
            if not table.repeated or (compact and not table.rows):
                continue  # Already represented in the one-row-per-run primary dataset.
            label = table.schema.get('title') or (tr('Funn', 'Findings') if not table.path else '.'.join(table.path).replace('.*', ''))
            name = name_for(str(label))
            headers = headers_for(table)
            # Reserved metadata columns are visibly distinct even when a user variable has the same name.
            all_headers = [tr('Kildedokument', 'Source document')] + headers
            for _, title in meta:
                candidate = title
                while candidate.casefold() in {h.casefold() for h in all_headers}:
                    candidate += ' [SDA]'
                all_headers.append(candidate)
            if all_headers[0].casefold() in {h.casefold() for h in headers}:
                all_headers[0] += ' [SDA]'
            rows = []
            for row in table.rows:
                row['source_location'] = source_locations(table, row, row['plan'], row['source'])
                row['null_fields'] = '\n'.join(row['nulls'])
                row['missing_fields'] = '\n'.join(pointer(c.path) or '/' for c in table.columns.values() if c.key not in row['present'])
                rows.append([row['document']] + [row['values'].get(k) for k in table.columns] + [row[k] for k, _ in meta])
            widths = {1:30}
            for i, column in enumerate(table.columns.values(), 2):
                kind = column.schema.get('type')
                lengths = [len(str(r['values'].get(column.key, ''))) for r in table.rows]
                widths[i] = 14 if column.role == 'count' or kind in ('integer', 'number', 'boolean') else min(90, max(24, max(lengths, default=0)*0.7))
            ws = sheet(name, all_headers, rows, widths)
            summaries.append((name, pid, len(rows), table.schema.get('description') or
                              tr('Én resultatpost per dokument' if table.repeated else 'Ett resultat per dokument',
                                 'One result item per document' if table.repeated else 'One result per document')))
            for label, c in zip(headers, table.columns.values()):
                spec = c.schema
                kind = 'integer' if c.role == 'count' else spec.get('type', tr('Ikke deklarert', 'Not declared'))
                definition = tr('Antall elementer i listen. Ingen kombinasjon med andre lister.', 'Number of list items. No cross-product with other lists.') if c.role == 'count' else spec.get('description', tr('Ikke beskrevet i planen.', 'Not described in the plan.'))
                dictionary.append([name, label, pointer(c.path) or '/', definition, ', '.join(kind) if isinstance(kind, list) else kind,
                                   pid, pointer(table.path) or '/', summaries[-1][3]])
            if include_csv and csv_directory:
                csv_directory.mkdir(parents=True, exist_ok=True)
                with (csv_directory / f'{name}.csv').open('w', encoding='utf-8-sig', newline='') as handle:
                    writer = csv.writer(handle)
                    # CSV is analysis data, not an Excel UI; values stay exact, including formula-like source text.
                    writer.writerow(all_headers)
                    writer.writerows(rows)
    for name, pid, count, unit in summaries:
        overview.append([name, f'{pid}: {count} ' + tr('rader. ', 'rows. ') + unit])
        cell = overview.cell(overview.max_row, 1)
        cell.hyperlink = f"#'{name.replace(chr(39), chr(39)*2)}'!A1"
        cell.font = Font(name='Arial', size=11, color='0563C1', underline='single')
        overview.cell(overview.max_row, 2).alignment = Alignment(wrap_text=True, vertical='top')
        overview.row_dimensions[overview.max_row].height = 44

    for row, record in zip(run_rows, records):
        row += [record['source_locations'], record['null_fields'], record['missing_fields']]
    if not compact:
        sheet(runs_name, [tr(a, b) for a, b in [
            ('Dokument','Document'), ('Kjøringsstatus','Run status'), ('Datasett','Dataset'), ('Validering','Validation'),
            ('Menneskelig kontroll','Human review'), ('Begrensninger','Limitations'), ('Feil','Error'),
            ('Dekning oppgitt','Reported coverage'), ('Forsøk','Attempt'), ('Kjøring','Run'), ('Planversjon','Plan version'),
            ('Dokument-ID','Document ID'), ('Simulert','Simulated'), ('Bestilt modell','Requested model'),
            ('Rapportert modell','Reported model'), ('Bestilt tenkenivå','Requested effort'), ('Sesjons-ID','Session ID'),
            ('Kilde SHA-256','Source SHA-256'), ('Valideringsmerknader','Validation notes'),
            ('Kildeplasseringer','Source locations'), ('Nullfelt','Null fields'), ('Fraværende felt','Absent fields')]], run_rows,
            {1:30, 3:40, 6:85, 7:65, 18:68, 19:85})
    issues = []
    for r in run_rows:
        for kind, text in [(tr('Feil','Error'), r[6]), (tr('Begrensning','Limitation'), r[5]),
                           (tr('Validering','Validation'), r[18])]:
            if text:
                issues.append([r[0], r[9], r[8], kind, text])
    if issues:
        sheet(name_for(tr('Feil og merknader','Errors and notes')),
              [tr('Dokument','Document'), tr('Kjøring','Run'), tr('Forsøk','Attempt'), tr('Type','Type'), tr('Melding','Message')],
              issues, {1:30, 2:16, 3:16, 4:24, 5:110})
    if compact:
        if csv_directory is not None:
            csv_directory.mkdir(parents=True, exist_ok=True)
            (csv_directory / 'variables.json').write_text(json.dumps(dictionary, ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        sheet(dictionary_name, [tr('Dataark','Data sheet'), tr('Kolonne','Column'), tr('Variabelsti','Variable path'),
                               tr('Forklaring','Definition'), tr('Datatype','Data type'), tr('Planversjon','Plan version'),
                               tr('Tabellsti','Table path'), tr('Én rad betyr','Row unit')], dictionary,
              {1:28, 2:30, 3:35, 4:90, 5:25, 6:20, 7:35, 8:75})
    if overflow:
        sheet(texts_name, [tr('Celle','Cell'), tr('Del','Part'), tr('Tekst','Text')], overflow, {1:35, 2:10, 3:120})
    for notice in dict.fromkeys(notices):
        overview.append([tr('Merknad','Note'), notice])
    if compact:
        book.remove(overview)
    filename = tr('Resultater.xlsx', 'Results.xlsx')
    book.save(directory / filename)
    book.close()
    return filename, [{'sheet': results_name, 'rows': len(records), 'row_unit': 'One document' if compact else 'One run'}] + [
        {'sheet': n, 'plan_version_id': p, 'rows': c, 'row_unit': u} for n,p,c,u in summaries]
