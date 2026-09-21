import json
import shutil
import sqlite3
from pathlib import Path
from urllib.parse import unquote

import pytest
from openpyxl import load_workbook

from kildeanalyse import tjeneste
from kildeanalyse.lager import Lager
from kildeanalyse.project_files import root_for

FIX = Path(__file__).parent/'fixtures'/'syntetisk'


def setup(store, tmp_path, language='nb', settings=None):
    project = tjeneste.opprett_prosjekt(store, 'Policy #1 æøå', str(tmp_path/'Arbeidsmappe æøå'))
    tjeneste.importer_dokumenter(store, project['id'], [str(FIX/'fjordblikk_2025.pdf')])
    created = tjeneste.opprett_analyse(store, project['id'], 'Eksempel', 'Les rapporten',
        str(FIX/'eksempelkriterier.json'), motor='simulert', sprak=language, motorinnstillinger=settings)
    aid = created['analyse']['id']
    tjeneste.godkjenn_plan(store, aid, 'Testperson')
    run = tjeneste.legg_til_kjoringer(store, aid)['nye'][0]
    return project, aid, run


@pytest.mark.parametrize('language', ['nb','en'])
def test_visible_workflow_workbook_and_portable_snapshot(tmp_path, language):
    store = Lager(tmp_path/'data')
    project, aid, run = setup(store, tmp_path, language)
    root = Path(project['directory'])
    assert (root/'START_HERE.md').is_file()
    assert (root/'plans'/f'{aid}.v1-utkast'/'Plan.md').is_file()
    plan = tjeneste.vis_plan(store, aid)
    assert 'Testperson' in Path(plan['plan_path']).read_text(encoding='utf-8')
    package = tjeneste.vis_inputpakke(store, run['id'])
    assert json.loads(Path(package['input_path']).read_text(encoding='utf-8')) == package['pakke']
    assert Path(package['input_path']).is_relative_to(root)
    tjeneste.start(store, aid)
    out = tjeneste.eksporter(store, aid)
    directory = Path(out['mappe'])
    assert directory.parent == root/'exports'
    assert len(list(directory.iterdir())) == 5  # entry, workbook, plan, sources, documentation
    assert not list(directory.rglob('*.csv'))
    docdir = directory/('Dokumentasjon' if language == 'nb' else 'Documentation')
    assert (docdir/'analyse.json').is_file()
    assert (docdir/'modellkall'/f'{run["id"]}.f1'/'input.json').is_file()
    book = load_workbook(out['workbook'])
    assert book.sheetnames == (['Oversikt','Resultater','Belegg','Kontroll','Kjøringer'] if language == 'nb' else
                               ['Overview','Results','Evidence','Review','Runs'])
    results = book.worksheets[1]
    assert results.max_row == 4 and results.freeze_panes == 'A2'
    assert all(results.cell(row, 7).value == 'ikke kontrollert' for row in range(2,5))
    assert any(cell.value == 'SIMULERT' or cell.value == 'SIMULATED' for row in book.worksheets[0] for cell in row)
    evidence = book.worksheets[2]
    link = evidence['A2'].hyperlink.target
    assert not Path(link).is_absolute()
    assert (directory/unquote(link)).is_file()
    book.close()
    relocated = tmp_path/'Flyttet pakke'
    shutil.copytree(directory, relocated)
    assert (relocated/unquote(link)).is_file()
    assert Path(out['entrypoint'].replace(str(directory), str(relocated))).is_file()
    original = Path(out['workbook']).read_bytes()
    Path(out['workbook']).write_bytes(b'user edits to be preserved')
    out2 = tjeneste.eksporter(store, aid, include_csv=True)
    assert out2['mappe'] != out['mappe']
    assert Path(out['workbook']).read_bytes() == b'user edits to be preserved'
    assert original != b'user edits to be preserved'
    csvs = {p.name for p in (Path(out2['mappe'])/'CSV').iterdir()}
    assert csvs == ({'resultater.csv','belegg.csv','forsok.csv','kontroll.csv'} if language == 'nb' else
                    {'results.csv','evidence.csv','attempts.csv','reviews.csv'})


def test_project_path_guards_and_old_database_migration(tmp_path, monkeypatch):
    data = tmp_path/'data'
    data.mkdir()
    with sqlite3.connect(data/'kildeanalyse.sqlite') as con:
        con.execute('CREATE TABLE prosjekt (id TEXT PRIMARY KEY, navn TEXT NOT NULL, opprettet TEXT NOT NULL)')
        con.execute("INSERT INTO prosjekt VALUES ('old','Old','2026-01-01')")
    store = Lager(data)
    assert store.prosjekt('old')['directory'] is None
    chosen = tmp_path/'Chosen'
    result = tjeneste.set_project_directory(store, 'old', str(chosen))
    assert result['directory'] == str(chosen)
    assert Lager(data).prosjekt('old')['directory'] == str(chosen)
    other = store.opprett_prosjekt('Other')
    with pytest.raises(ValueError, match='another project'):
        tjeneste.set_project_directory(store, other['id'], str(chosen))
    with pytest.raises(ValueError, match='absolute'):
        tjeneste.set_project_directory(store, other['id'], 'relative')
    with pytest.raises(ValueError, match='AppData'):
        tjeneste.set_project_directory(store, other['id'], str(data/'bad'))
    existing = tmp_path/'not-empty'
    existing.mkdir(); (existing/'keep.txt').write_text('user work')
    with pytest.raises(ValueError, match='empty'):
        tjeneste.set_project_directory(store, other['id'], str(existing))
    assert (existing/'keep.txt').read_text() == 'user work'
    changed = tjeneste.set_project_directory(store, 'old', str(tmp_path/'New'))
    assert chosen.exists() and Path(changed['directory']).exists()


def test_failed_run_is_visible_and_failed_export_does_not_publish(tmp_path, monkeypatch):
    store = Lager(tmp_path/'data')
    project, aid, run = setup(store, tmp_path, settings={'scenarier':{'fjordblikk_2025.pdf':'krasj'}})
    tjeneste.start(store, aid)
    out = tjeneste.eksporter(store, aid, med_kilder=False)
    book = load_workbook(out['workbook'])
    assert book['Resultater']['E2'].value == 'feilet'
    assert book['Resultater']['C2'].value is None
    assert book['Resultater']['J2'].value
    book.close()
    root = Path(project['directory'])/'exports'
    before = {p.name for p in root.iterdir()}
    def fail(*args, **kwargs):
        raise OSError('disk full')
    monkeypatch.setattr('kildeanalyse.workbook_export.write_workbook', fail)
    with pytest.raises(OSError, match='disk full'):
        tjeneste.eksporter(store, aid)
    assert {p.name for p in root.iterdir()} == before


def test_workbook_text_never_becomes_formula_and_overflow_is_preserved(tmp_path):
    from kildeanalyse.workbook_export import write_workbook
    store = Lager(tmp_path/'data')
    _, aid, run = setup(store, tmp_path)
    tjeneste.start(store, aid)
    out = tjeneste.eksporter(store, aid)
    directory = Path(out['mappe'])
    data = json.loads((directory/'Dokumentasjon'/'analyse.json').read_text(encoding='utf-8'))
    first = data['kjoringer'][0]
    values = first['vurderinger']
    criterion = next(iter(values))
    values[criterion]['svar'] = '=HYPERLINK("https://example.org")'
    long_quote = 'Langt sitat ' * 4000
    values[criterion]['belegg'][0]['sitat'] = long_quote
    name, notices = write_workbook(directory, store.analyse(aid), store.planversjoner(aid), data['kjoringer'], [], [], 'nb', True, 'Dokumentasjon')
    book = load_workbook(directory/name)
    assert book['Resultater']['C2'].data_type == 's'
    assert book['Resultater']['C2'].value.startswith('=HYPERLINK')
    text_link = book['Belegg']['D2'].hyperlink.target
    assert (directory/unquote(text_link)).read_text(encoding='utf-8') == long_quote
    assert notices
    book.close()


def test_actual_human_review_is_exported_without_losing_raw_answer(tmp_path):
    store = Lager(tmp_path/'data')
    _, aid, run = setup(store, tmp_path)
    tjeneste.start(store, aid)
    attempt = store.forsok_for_kjoring(run['id'])[0]
    raw = attempt['raasvar']
    tjeneste.registrer_kontroll(store, attempt['id'], 'Testperson', 'godkjent', 'Kontrollert mot kilden')
    out = tjeneste.eksporter(store, aid)
    book = load_workbook(out['workbook'])
    assert book['Kontroll']['B2'].value == 'Testperson'
    assert book['Resultater']['G2'].value == 'godkjent'
    book.close()
    path = Path(out['mappe'])/'Dokumentasjon'/'modellkall'/attempt['id']/'raasvar.txt'
    assert path.read_text(encoding='utf-8') == raw
