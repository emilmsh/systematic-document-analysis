import copy
import json
from pathlib import Path
from urllib.parse import unquote

import pytest
from openpyxl import load_workbook

from kildeanalyse import tjeneste
from kildeanalyse.call_evidence import call_records, call_warnings
from kildeanalyse.english_tools import register
from kildeanalyse.lager import Lager
from kildeanalyse.adaptere.simulert import SimulertAdapter

FIX = Path(__file__).parent/'fixtures/syntetisk'
CACHE = 'ERROR failed to load models cache: missing field supports_parallel_tool_calls'


def test_historical_chunks_have_separate_proof_without_double_counting_or_inferred_telemetry():
    chunks = [{'stage': stage, 'sesjon_id': f'session-{i}', 'modell_rapportert': None,
               'forbruk': {'usage': {'input_tokens': 10*i, 'output_tokens': i}},
               'motorinfo': {'returkode': 0, 'varighet_sek': i, 'stderr': CACHE}}
              for i, stage in enumerate(['extract','extract','synthesis'], 1)]
    manifest = {'startet': 'parent-start', 'avsluttet': 'parent-end',
                'kjoreparametre': {'modell': 'requested', 'tenkenivaa': 'high'},
                'motorinfo': {**chunks[-1]['motorinfo'], 'calls': chunks}}
    attempt = {'id':'kj1.f1','kjoring_id':'kj1','motor':'codex_cli','simulert':False,
               'input_sti':'attempts/kj1.f1','manifest_json':json.dumps(manifest)}
    original = copy.deepcopy(attempt)
    records = call_records(attempt, 'source.pdf')
    assert len(records) == 3
    assert sum(r['input_tokens'] for r in records) == 60
    assert [r['session_id'] for r in records] == ['session-1','session-2','session-3']
    assert all(r['started_at'] is None and r['reported_model'] is None for r in records)
    assert all(r['reported_effort'] is None and r['requested_effort'] == 'high' for r in records)
    assert all(r['exit_code'] == 0 and not r['simulated'] for r in records)
    assert len(call_warnings(records)) == 3  # no duplicated synthesis diagnostic from parent
    assert all(w['code'] == 'CLI_MODEL_CACHE' for w in call_warnings(records))
    assert records[-1]['artifact_subdirectory'] == 'calls/0003-synthesis'
    assert attempt == original


@pytest.mark.parametrize('usage', [
    {'input_tokens':0, 'output_tokens':5, 'cache_read_input_tokens':0},
    {'prompt_tokens':0, 'completion_tokens':5, 'prompt_tokens_details':{'cached_tokens':0}},
])
def test_missing_and_zero_usage_are_distinct_and_pre_dispatch_failure_is_not_success(usage):
    manifest = {'motorinfo': {'calls': [
        {'stage':'extract','dispatched':False,'feil':'Stopped before dispatch','motorinfo':{}},
        {'stage':'extract','forbruk':{'usage':usage},'modell_rapportert':'actual-model',
         'motorinfo':{'http_status':200,'stderr':'diagnostic '+('x'*1000)}},
    ]}}
    records = call_records({'id':'f1','manifest_json':json.dumps(manifest)})
    assert records[0]['status'] == 'not_dispatched'
    assert records[0]['input_tokens'] is None and records[0]['exit_code'] is None
    assert records[1]['input_tokens'] == 0 and records[1]['cached_input_tokens'] == 0
    assert records[1]['output_tokens'] == 5 and records[1]['reported_model'] == 'actual-model'
    assert records[1]['warnings'][0]['truncated']
    assert len(records[1]['warnings'][0]['message']) == 800
    assert call_records({'id':'not-started'}) == []


@pytest.mark.parametrize('language', ['nb','en'])
def test_warnings_do_not_block_queue_and_call_export_preserves_all_attempts(tmp_path, monkeypatch, language):
    store = Lager(tmp_path/'data')
    project = tjeneste.opprett_prosjekt(store,'Evidence',str(tmp_path/'visible'))
    tjeneste.importer_dokumenter(store, project['id'], [str(FIX/'fjordblikk_2025.pdf'),str(FIX/'steinbukk_2025.pdf')])
    result = tjeneste.opprett_analyse(store,project['id'],'Evidence','Read',str(FIX/'eksempelkriterier.json'),
                                     motor='simulert',sprak=language)
    aid = result['analyse']['id']
    runs = tjeneste.legg_til_kjoringer(store,aid)['nye']
    tjeneste.godkjenn_plan(store,aid,'Test person')
    original = SimulertAdapter.kjor
    def read(self, *args, **kwargs):
        reply = original(self, *args, **kwargs)
        reply.motorinfo = {'returkode':0,'stderr':CACHE,'cli_versjon':'test-double',
                           'tenkenivaa_onsket':'high','tenkenivaa_rapportert':'ukjent'}
        reply.modell_rapportert = None
        reply.forbruk = {'usage':{'input_tokens':100,'output_tokens':10}}
        return reply
    monkeypatch.setattr(SimulertAdapter,'kjor',read)
    tjeneste.start(store,aid)
    status = tjeneste.vis_status(store,aid,details=False)
    assert status['teller'] == {'fullført':2}
    assert status['workflow_block'] is None and status['run_issues'] == []
    assert len(status['run_warnings']) == 2
    assert all('sider' not in row['dokument'] for row in status['rader'])
    assert all('manifest_json' not in row['siste_forsok'] for row in status['rader'])
    functions = {}
    class Server:
        def tool(self, **kwargs):
            def register_fn(fn):
                functions[fn.__name__] = fn
                return fn
            return register_fn
    register(Server(),lambda:store)
    compact = json.loads(functions['show_status'](aid))
    full = json.loads(functions['show_status'](aid,details=True))
    assert compact['detail_level'] == 'compact' and full['detail_level'] == 'full'
    assert compact['teller'] == full['teller']
    assert len(json.dumps(compact)) < len(json.dumps(full))/2
    assert 'sider' in full['rader'][0]['document']
    # A new attempt keeps historical evidence and exposes each warning exactly once.
    tjeneste.nytt_forsok(store,runs[0]['id'],'Explicit retry in local test')
    tjeneste.start(store,aid)
    export = tjeneste.eksporter(store,aid)
    root = Path(export['mappe'])
    book = load_workbook(export['workbook'])
    sheet = book['Modellkall' if language == 'nb' else 'Model calls']
    assert sheet.max_row == 4
    assert {sheet.cell(i,2).value for i in range(2,5)} == {runs[0]['id']+'.f1',runs[0]['id']+'.f2',runs[1]['id']+'.f1'}
    assert all(sheet.cell(i,7).value is True for i in range(2,5))  # never present doubles as real calls
    assert all(sheet.cell(i,11).value == ('Ikke rapportert' if language == 'nb' else 'Not reported') for i in range(2,5))
    assert all(sheet.cell(i,17).value == 0 for i in range(2,5))
    assert all(CACHE in sheet.cell(i,24).value for i in range(2,5))
    for row in range(2,5):
        for column in (26,27,28):
            link = sheet.cell(row,column).hyperlink.target
            assert not Path(unquote(link)).is_absolute()
            assert (root/unquote(link)).is_file()
    assert CACHE in book['Resultater' if language == 'nb' else 'Results']['J2'].value
    book.close()
    audit = json.loads((root/('Dokumentasjon' if language == 'nb' else 'Documentation')/'analyse.json').read_text(encoding='utf-8'))
    assert len(audit['model_calls']) == 3 and len(audit['run_warnings']) == 3
    for run in runs:
        for attempt in store.forsok_for_kjoring(run['id']):
            exported = root/('Dokumentasjon' if language == 'nb' else 'Documentation')/'modellkall'/attempt['id']
            assert (exported/'manifest.json').read_bytes() == (Path(attempt['input_sti'])/'manifest.json').read_bytes()
