import csv
import json
from pathlib import Path
import pytest
from kildeanalyse import tjeneste
from kildeanalyse.english_tools import register
from kildeanalyse.konfig import datamappe
from kildeanalyse.lager import Lager
from kildeanalyse.languages import public_result
from kildeanalyse.modell import Plan
from kildeanalyse.prompt import bygg_inputpakke
from kildeanalyse.task_contract import validate as valider

FIX = Path(__file__).parent/'fixtures/syntetisk'


def test_english_workflow_and_export_boundary(tmp_path):
    store = Lager(tmp_path/'data')
    functions = {}
    class Server:
        def tool(self, **kwargs):
            def decorator(fn):
                functions[fn.__name__] = fn
                return fn
            return decorator
    register(Server(), lambda:store)
    assert len(functions) == 21
    def call(tool_name, **kwargs):
        result = json.loads(functions[tool_name](**kwargs))
        assert 'error' not in result, result
        return result
    project = call('create_project', name='English æøå')
    call('import_documents', project_id=project['id'], paths=[str(FIX/'fjordblikk_2025.pdf')])
    result = call('create_analysis', project_id=project['id'], name='Policies', request='Read the report',
                  engine='openai_api', model='chosen-model', language='en',
                  engine_settings={'max_output_tokens':2048,'timeout_seconds':300})
    aid = result['analysis']['id']
    old = result['plan_version']['plan']
    assert old['language'] == 'en' and old['task_instructions'] == 'Read the report'
    call('approve_plan', analysis_id=aid, approved_by='Reader')
    runs = call('add_runs', analysis_id=aid)
    package = call('show_input_package', run_id=runs['new'][0]['id'])['package']
    assert 'in English' in package['system_instruction']
    assert 'result' in package['response_schema']['properties']
    assert package['api_request']['body']['max_output_tokens'] == 2048
    call('new_plan_version', analysis_id=aid, change_note='Norwegian commentary', language='nb')
    plan = call('show_plan', analysis_id=aid)
    assert [v['plan']['language'] for v in plan['versions']] == ['en','nb']
    exported = call('export_results', analysis_id=aid)
    assert Path(exported['workbook']).is_file()
    assert 'error' in json.loads(functions['create_analysis'](project['id'], 'x', 'x', engine='openai_api', model='x', language='fr'))


def test_translation_preserves_identifiers_wire_payloads_and_quotes():
    raw = {'result':{'navn':'ja','belegg':[{'side':1,'sitat':'Styret vedtok en policy.'}]},
           'svarskjema':{'properties':{'navn':{'type':'string'}}}, 'api_foresporsel':{'body':{'navn':'x'}}}
    result = public_result(raw)
    assert result['result'] == raw['result']
    assert result['response_schema'] == raw['svarskjema']
    assert result['api_request'] == raw['api_foresporsel']
    schema = {'properties': {'vurderinger': {'type': 'array'}, 'sider_lest': {'type': 'array'}},
              'required': ['vurderinger', 'sider_lest'], 'additionalProperties': False}
    manifest = {'motorinfo': {'svarskjema_sendt': schema}, 'hendelser': [
        {'type': 'item.completed', 'item': {'vurderinger': ['navn']}}]}
    nested = public_result({'forsok': [{'manifest': manifest}], 'svarskjema_sendt': schema})
    assert nested['attempts'][0]['manifest'] == manifest
    assert nested['svarskjema_sendt'] == schema
    assert public_result(nested) == nested








def test_data_directory_is_explicit_and_non_destructive(tmp_path, monkeypatch):
    # Not below LOCALAPPDATA: the Store desktop apps would each keep a hidden copy there.
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'appdata'))
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.delenv('SDA_DATA', raising=False)
    current = tmp_path/'.systematic-document-analysis'/'data'
    other = tmp_path/'another-store'
    assert datamappe() == current
    other.mkdir()
    (other/'kildeanalyse.sqlite').write_bytes(b'old database')
    assert datamappe() == current
    (current/'kildeanalyse.sqlite').write_bytes(b'new database')
    monkeypatch.setenv('SDA_DATA', str(other))
    assert datamappe() == other
    monkeypatch.setenv('SDA_DATA', str(current))
    assert datamappe() == current
    assert (other/'kildeanalyse.sqlite').read_bytes() == b'old database'


def test_explicit_api_key(monkeypatch):
    from kildeanalyse.api_oppsett import local_key
    monkeypatch.delenv('SDA_CUSTOM_API_KEY', raising=False)
    monkeypatch.setenv('SDA_CUSTOM_API_KEY','new-fake-key')
    assert local_key('kompatibel_api') == 'new-fake-key'
