import csv
import json
from pathlib import Path
import pytest
from kildeanalyse import tjeneste
from kildeanalyse.english_tools import register
from kildeanalyse.konfig import datamappe
from kildeanalyse.lager import Lager
from kildeanalyse.languages import normalize_criteria, public_result
from kildeanalyse.modell import Plan, Kriterium
from kildeanalyse.prompt import bygg_inputpakke
from kildeanalyse.validering import valider

CRITERIA = {'name':'Policy', 'criteria':[{'id':'navn', 'name':'Policy', 'question':'Is a policy reported?',
    'allowed_answers':['yes','not_mentioned'], 'evidence_required_for':['yes'], 'rule':'Quote the report.'}]}
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
    assert len(functions) == 18
    def call(tool_name, **kwargs):
        result = json.loads(functions[tool_name](**kwargs))
        assert 'error' not in result, result
        return result
    project = call('create_project', name='English æøå')
    call('import_documents', project_id=project['id'], paths=[str(FIX/'fjordblikk_2025.pdf')])
    criteria = tmp_path/'criteria.json'
    criteria.write_text(json.dumps(CRITERIA), encoding='utf-8')
    result = call('create_analysis', project_id=project['id'], name='Policies', request='Read the report',
                  criteria_file=str(criteria), engine='openai_api', model='chosen-model', language='en',
                  engine_settings={'max_output_tokens':2048,'timeout_seconds':300})
    aid = result['analysis']['id']
    old = result['plan_version']['plan']
    assert old['language'] == 'en' and old['criteria'][0]['id'] == 'navn'
    call('approve_plan', analysis_id=aid, approved_by='Reader')
    runs = call('add_runs', analysis_id=aid)
    package = call('show_input_package', run_id=runs['new'][0]['id'])['package']
    assert 'in English' in package['system_instruction']
    assert 'vurderinger' in package['response_schema']['properties']
    assert package['api_request']['body']['max_output_tokens'] == 2048
    call('new_plan_version', analysis_id=aid, change_note='Norwegian commentary', language='nb')
    plan = call('show_plan', analysis_id=aid)
    assert [v['plan']['language'] for v in plan['versions']] == ['en','nb']
    out = Path(call('export_results', analysis_id=aid)['directory'])
    with (out/'results.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f, delimiter=';'))
    assert rows[0]['language'] == 'en' and 'navn_answer' in rows[0]
    assert (out/'README.md').is_file() and 'chosen-model' in (out/'plan-summary.md').read_text(encoding='utf-8')
    assert 'error' in json.loads(functions['create_analysis'](project['id'], 'x', 'x', str(criteria), 'openai_api', model='x', language='fr'))


def test_translation_preserves_identifiers_wire_payloads_and_quotes():
    raw = {'vurderinger':{'navn':{'svar':'ja','belegg':[{'side':1,'sitat':'Styret vedtok en policy.'}]}},
           'svarskjema':{'properties':{'navn':{'type':'string'}}}, 'api_foresporsel':{'body':{'navn':'x'}}}
    result = public_result(raw)
    assert result['assessments']['navn']['answer'] == 'ja'
    assert result['assessments']['navn']['evidence'][0]['quote'] == 'Styret vedtok en policy.'
    assert result['response_schema'] == raw['svarskjema']
    assert result['api_request'] == raw['api_foresporsel']
    with pytest.raises(ValueError):
        normalize_criteria({'criteria':[], 'kriterier':[]})


@pytest.mark.parametrize('label', ['not_mentioned','not_reported'])
def test_english_absence_requires_full_coverage(label):
    plan = Plan('Read', [Kriterium('k','k','question',[label])], sprak='en')
    document = {'sider':[{'nr':1,'tekst':'Readable first page with sufficient text.', 'tegn':35},
                         {'nr':2,'tekst':'Readable second page with sufficient text.', 'tegn':35}]}
    answer = {'vurderinger':[{'kriterium_id':'k','svar':label,'belegg':[]}], 'sider_lest':[1], 'merknader':[]}
    assert not valider(plan, document, answer, [1,2])['gyldig']
    answer['sider_lest'] = [1,2]
    assert valider(plan, document, answer, [1,2])['gyldig']


def test_old_plan_language_default_without_rewriting():
    old = {'formaal':'Read', 'kriterier':[]}
    assert Plan.fra_dict(old).sprak == 'nb'
    assert 'sprak' not in old


def test_data_directory_is_explicit_and_non_destructive(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.delenv('SDA_DATA', raising=False)
    current = tmp_path/'systematic-document-analysis'
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
