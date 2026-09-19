import csv
import json
import sqlite3
from pathlib import Path
import pytest
from docx import Document
from openpyxl import Workbook
from kildeanalyse import tjeneste, visning
from kildeanalyse.dokument import importer_dokument, sider_uten_tekst, DokumentFeil, sha256_fil
from kildeanalyse.lager import Lager, SKJEMA, KJ_FULLFORT
from kildeanalyse.modell import Motorsvar, Stotte
from kildeanalyse.adaptere.claude_cli import ClaudeCliAdapter
from kildeanalyse.source_formats import extract, location
from kildeanalyse.validering import valider

QUOTE = 'The board adopted a policy.'


def source_file(tmp_path, extension):
    path = tmp_path/f'example.{extension}'
    if extension == 'docx':
        doc = Document(); doc.add_heading('Policy', 1); doc.add_paragraph(QUOTE)
        table = doc.add_table(rows=1, cols=1); table.cell(0,0).text = 'Follow-up'
        doc.save(path)
    elif extension == 'xlsx':
        book = Workbook(); sheet = book.active; sheet.title = 'Governance'
        sheet['A1'] = 'Policy'; sheet['B2'] = QUOTE
        book.save(path); book.close()
    elif extension in ('csv','tsv'):
        with path.open('w',encoding='utf-8-sig',newline='') as f:
            writer = csv.writer(f,delimiter=';' if extension == 'csv' else '\t')
            writer.writerows([['Name','Statement'], ['Example',QUOTE]])
    else:
        path.write_text('Policy\n\n'+QUOTE,encoding='utf-8')
    return path


@pytest.mark.parametrize('extension,locator', [('txt','Line 3'),('md','Line 3'),('csv','Record 2'),
                                               ('tsv','Record 2'),('docx','Body/block 2'),('xlsx','Governance!B2:B2')])
def test_complete_format_workflow_without_models(tmp_path, monkeypatch, extension, locator):
    file = source_file(tmp_path, extension); original_hash = sha256_fil(file)
    store = Lager(tmp_path/'data'); project = tjeneste.opprett_prosjekt(store, 'Comparable files')
    document, new = importer_dokument(store, project['id'], file)
    assert new and not sider_uten_tekst(document)
    assert importer_dokument(store, project['id'], file)[1] is False
    assert Path(document['lagret_kopi']).suffix == '.'+extension
    criterion = {'criteria':[{'id':'policy', 'allowed_answers':['yes','not_mentioned'], 'evidence_required_for':['yes']}]}
    analysis = tjeneste.opprett_analyse(store, project['id'], 'Policy', 'Compare each file', criterion, motor='claude_cli', sprak='en')
    aid = analysis['analyse']['id']; plan = analysis['planversjon']['plan']
    assert tjeneste.vis_plan(store,aid)['source_profiles'][0]['format'] == extension
    run = tjeneste.legg_til_kjoringer(store,aid)['nye'][0]['id']
    preview = tjeneste.vis_inputpakke(store,run)['pakke']
    assert locator in preview['brukermelding'] and '[Source unit' in preview['brukermelding']
    assert 'fysiske sider' not in preview['brukermelding']
    monkeypatch.setattr(ClaudeCliAdapter, 'sjekk_stotte', lambda self:Stotte(True))
    def reader(self, package, *args):
        unit = next(s for s in package.sider if QUOTE in s.tekst)
        return Motorsvar(raasvar='offline fixture', svar={'vurderinger':[{'kriterium_id':'policy','svar':'yes',
            'belegg':[{'side':unit.nr,'sitat':QUOTE}], 'kommentar':'Explicit statement.'}],
            'sider_lest':[s.nr for s in package.sider], 'merknader':[]})
    monkeypatch.setattr(ClaudeCliAdapter, 'kjor', reader)
    tjeneste.godkjenn_plan(store,aid,'Offline check'); tjeneste.start(store,aid)
    assert store.kjoring(run)['status'] == KJ_FULLFORT
    details = tjeneste.vis_kjoring(store,run)
    assert details['forsok'][0]['vurderinger']['policy']['belegg'][0]['source']['location'] == locator
    assert locator in visning.md_kjoring(details)
    output = Path(tjeneste.eksporter(store,aid,True)['mappe'])
    with (output/'evidence.csv').open(encoding='utf-8-sig',newline='') as f:
        row = next(csv.DictReader(f,delimiter=';'))
    assert row['source_location'] == locator and row['physical_page'] == '' and row['quote'] == QUOTE
    assert any(p.suffix == '.'+extension for p in (output/'kilder').iterdir())
    assert sha256_fil(file) == original_hash
    assert json.loads((output/'resultater.json').read_text(encoding='utf-8'))['kjoringer'][0]['source_metadata']['format'] == extension


def test_workbook_formulas_hidden_sheet_and_short_values(tmp_path):
    file = tmp_path/'formulas.xlsx'; book = Workbook(); sheet = book.active
    sheet.title = 'Data'; sheet['B1'] = 17; sheet['C1'] = '=B1*2'
    hidden = book.create_sheet('Hidden'); hidden.sheet_state='hidden'; hidden['A3']='yes'
    book.save(file); book.close()
    units, profile, _ = extract(file)
    assert profile['missing_formula_values'] == ['Data!C1']
    assert 'UNAVAILABLE' in units[0]['tekst'] and '=B1*2' in units[0]['tekst']
    assert units[1]['source']['sheet_state'] == 'hidden' and units[1]['source']['row'] == 3
    from kildeanalyse.modell import Plan, Kriterium
    plan = Plan('Read', [Kriterium('k','k','question',['yes'],['yes'])])
    def validate_quote(quote):
        return valider(plan, {'sider':units}, {'vurderinger':[{'kriterium_id':'k','svar':'yes',
            'belegg':[{'side':1,'sitat':quote}]}], 'sider_lest':[1,2]}, [1,2])['gyldig']
    assert validate_quote('17')
    assert not validate_quote('1')  # must not match the coordinate B1
    assert not validate_quote('34')  # no recalculation or invented cached value


def test_csv_record_ids_handle_multiline_quotes_and_single_columns(tmp_path):
    file=tmp_path/'table.csv'; file.write_text('name;statement\nX;"first\nsecond"\n',encoding='utf-8')
    units, _, _ = extract(file)
    assert len(units) == 2 and units[1]['source']['record'] == 2 and 'first\nsecond' in units[1]['tekst']
    file.write_text('header\nvalue\n',encoding='utf-8')
    assert len(extract(file)[0]) == 2


def test_old_database_migration_preserves_documents(tmp_path):
    schema = SKJEMA.replace(",\n  metadata_json TEXT NOT NULL DEFAULT '{}'", '')
    with sqlite3.connect(tmp_path/'kildeanalyse.sqlite') as con:
        con.executescript(schema)
        con.execute("INSERT INTO prosjekt VALUES ('pr1','Existing','yesterday')")
    store = Lager(tmp_path)
    assert store.prosjekt('pr1')['navn'] == 'Existing'
    with sqlite3.connect(store.db) as con:
        assert 'metadata_json' in [row[1] for row in con.execute('PRAGMA table_info(dokument)')]
    assert Lager(tmp_path).prosjekt('pr1')['navn'] == 'Existing'


def test_explicit_unsupported_and_empty_files_fail_visibly(tmp_path):
    store=Lager(tmp_path/'data'); project=store.opprett_prosjekt('Files')
    for extension, data in [('doc',b'unsupported'),('txt',b''),('txt',b'\xffbad encoding')]:
        file=tmp_path/f'bad.{extension}'; file.write_bytes(data)
        with pytest.raises(DokumentFeil): importer_dokument(store,project['id'],file)
    assert store.dokumenter(project['id']) == []


def test_identical_bytes_with_different_formats_keep_distinct_interpretations(tmp_path):
    store=Lager(tmp_path/'data'); project=store.opprett_prosjekt('Files')
    files = [tmp_path/'data.txt', tmp_path/'data.csv']
    for file in files: file.write_text('field,value\npolicy,yes\n', encoding='utf-8')
    docs = [importer_dokument(store,project['id'],file)[0] for file in files]
    assert docs[0]['sha256'] == docs[1]['sha256'] and docs[0]['id'] != docs[1]['id']
    assert docs[0]['source_metadata']['format'] == 'txt' and docs[1]['source_metadata']['format'] == 'csv'
    assert importer_dokument(store,project['id'],files[1])[0]['id'] == docs[1]['id']
