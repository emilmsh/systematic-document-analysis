"""Instruction-first tasks through the real queue, using fake CLI/API responses only."""
import copy
import json
import zipfile
from pathlib import Path

import pytest

from kildeanalyse import tjeneste, visning
from kildeanalyse.adaptere import ADAPTERE
from kildeanalyse.english_tools import register
from kildeanalyse.lager import Lager, FS_FULLFORT, KJ_FULLFORT
from kildeanalyse.languages import public_result
from kildeanalyse.modell import Plan, Motorsvar, Stotte
from kildeanalyse.prompt import bygg_inputpakke
from kildeanalyse.task_contract import validate, problem, instruction

QUOTE = 'We support a mandatory annual accessibility audit.'
SCHEMA = {'type': 'array', 'items': {'type': 'object', 'properties': {
    'navn': {'type': 'string'}, 'passage': {'type': 'string'}, 'unit': {'type': 'integer'}},
    'required': ['navn', 'passage', 'unit'], 'additionalProperties': False}}
CHECKS = [{'path': '', 'quote_field': 'passage', 'unit_field': 'unit'}]


def test_file_reader_instructions_match_cli_tools():
    plan = Plan('Read', task_instructions='Find relevant passages.', motorinnstillinger={'file_tools': True})
    plan.motor = 'claude_cli'
    claude = instruction(plan)
    plan.motor = 'codex_cli'
    codex = instruction(plan)
    assert claude == codex
    assert 'Use the available tools and a method suited to the task' in codex
    assert 'Do not inspect other runs' in codex
    assert 'Preserve requested quotations exactly' not in codex
    plan.quote_checks = CHECKS
    assert 'Preserve requested quotations exactly' in instruction(plan)


def fixture(tmp_path, monkeypatch, *, engine='claude_cli', structured=False, large=False, broken=False):
    store = Lager(tmp_path / 'data')
    project = tjeneste.opprett_prosjekt(store, 'Task test')
    for name in ['a.txt', 'b.txt']:
        source = tmp_path / name
        source.write_text(name + '\n' + ('Background. ' * 1400 if large else '') + QUOTE +
                          (' More background. ' * 800 if large else ''), encoding='utf-8')
        tjeneste.importer_dokumenter(store, project['id'], [str(source)])
    seen = []
    def read(self, package, *args):
        seen.append(package)
        assert package.dokument_navn in package.brukermelding
        assert ('b.txt' if package.dokument_navn == 'a.txt' else 'a.txt') not in package.brukermelding
        evidence = [{'side': s.nr, 'sitat': QUOTE} for s in package.sider if QUOTE in s.tekst]
        result = [{'navn': 'Audit', 'passage': e['sitat'], 'unit': e['side']} for e in evidence] if structured else '# Findings\n\n' + QUOTE
        response = {'result': result, 'source_units_read': [s.nr for s in package.sider], 'limitations': []}
        if broken and package.dokument_navn == 'a.txt':
            response['result'] = 42  # wrong task schema
        return Motorsvar(json.dumps(response), response, sesjon_id=package.forsok_id,
                         modell_rapportert='fake-model', motorinfo={'test_fixture': True})
    monkeypatch.setattr(ADAPTERE[engine], 'sjekk_stotte', lambda self: Stotte(True))
    monkeypatch.setattr(ADAPTERE[engine], 'kjor', read)
    settings = {'input_budget_bytes': 200000 if large else 60000}
    if engine == 'kompatibel_api':
        settings['base_url'] = 'https://example.org/v1'
    if engine == 'azure_foundry_api':
        settings.update(base_url='https://example.services.ai.azure.com', api_format='responses')
    created = tjeneste.opprett_analyse(store, project['id'], 'Extract passages', 'Extract passages about audits.',
        motor=engine, modell='test-model', sprak='en', motorinnstillinger=settings,
        output_schema=copy.deepcopy(SCHEMA) if structured else None, quote_checks=CHECKS if structured else None)
    aid = created['analyse']['id']
    runs = tjeneste.legg_til_kjoringer(store, aid)['nye']
    return store, aid, runs, seen


@pytest.mark.parametrize('engine', ['claude_cli', 'codex_cli', 'openai_api', 'anthropic_api',
                                   'openrouter_api', 'kompatibel_api', 'azure_foundry_api'])
@pytest.mark.parametrize('large', [False, True])
def test_task_execution_all_readers(tmp_path, monkeypatch, engine, large):
    store, aid, runs, seen = fixture(tmp_path, monkeypatch, engine=engine, structured=True, large=large)
    preview = tjeneste.vis_inputpakke(store, runs[0]['id'])['pakke']
    assert preview['processing']['calls'] == 1
    tjeneste.godkjenn_plan(store, aid, 'Fixture reviewer')
    report = tjeneste.start(store, aid)
    assert not report['run_issues'], report
    for run in runs:
        detail = tjeneste.vis_kjoring(store, run['id'])
        attempt = detail['forsok'][0]
        assert attempt['forsok']['status'] == FS_FULLFORT
        assert attempt['result'][0]['passage'] == QUOTE
        assert attempt['review_status'] == 'ikke kontrollert'
        assert attempt['validering']['checks']['exact_quotes_checked'] >= 1
        assert attempt['validering']['checks']['semantic_accuracy'] == 'not_checked'
        assert public_result(detail)['attempts'][0]['result'][0]['navn'] == 'Audit'
        assert attempt['forsok']['input_hash'] != ''
    assert len({p.dokument_id for p in seen}) == 2
    assert len({p.systeminstruks for p in seen if 'STAGE:' not in p.systeminstruks}) <= 1
    output = tjeneste.eksporter(store, aid)
    folder = Path(output['mappe'])
    assert Path(output['workbook']).is_file()
    assert len(list(folder.iterdir())) == 3
    with zipfile.ZipFile(output['documentation_archive']) as archive:
        for run in runs:
            assert QUOTE in archive.read(f'results/{run["id"]}.md').decode('utf-8')
            assert f'audit/attempts/{run["id"]}.f1/input.json' in archive.namelist()
        assert 'Plan.md' in archive.namelist()
        assert len([n for n in archive.namelist() if n.startswith('sources/')]) == 2


def test_whitespace_repair_reaches_workbook_without_changing_raw_reply(tmp_path, monkeypatch):
    from openpyxl import load_workbook
    store, aid, runs, _ = fixture(tmp_path, monkeypatch, structured=True)
    altered = QUOTE.replace('We support', 'We  support')
    def reply(self, package, *args):
        response = {'result': [{'navn': 'Audit', 'passage': altered, 'unit': 2}],
                    'source_units_read': [1, 2], 'limitations': []}
        return Motorsvar(json.dumps(response), response, sesjon_id=package.forsok_id,
                         modell_rapportert='fake-model', motorinfo={'test_fixture': True})
    monkeypatch.setattr(ADAPTERE['claude_cli'], 'kjor', reply)
    tjeneste.godkjenn_plan(store, aid, 'Fixture reviewer')
    assert not tjeneste.start(store, aid)['run_issues']
    attempt = store.forsok_for_kjoring(runs[0]['id'])[0]
    assert altered in attempt['raasvar']
    assert tjeneste.vis_kjoring(store, runs[0]['id'])['forsok'][0]['result'][0]['passage'] == QUOTE
    workbook = load_workbook(tjeneste.eksporter(store, aid, med_kilder=False)['workbook'], read_only=True)
    try:
        assert any(QUOTE in str(value) for sheet in workbook for row in sheet.values for value in row if value)
        assert not any(altered in str(value) for sheet in workbook for row in sheet.values for value in row if value)
    finally:
        workbook.close()


@pytest.mark.parametrize('large', [False, True])
def test_failure_is_local_and_intermediate_work_is_preserved(tmp_path, monkeypatch, large):
    store, aid, runs, seen = fixture(tmp_path, monkeypatch, large=large, broken=True)
    tjeneste.godkjenn_plan(store, aid, 'Fixture reviewer')
    report = tjeneste.start(store, aid)
    assert len(report['run_issues']) == 1
    assert not report['workflow_block']
    assert store.kjoring(runs[1]['id'])['status'] == KJ_FULLFORT
    first = tjeneste.vis_kjoring(store, runs[0]['id'])['forsok'][0]
    assert first['forsok']['status'] == 'valideringsfeil'
    with pytest.raises(tjeneste.TjenesteFeil, match='invalid'):
        tjeneste.registrer_kontroll(store, first['forsok']['id'], 'Reviewer', 'godkjent', 'Inspected')
    output = tjeneste.eksporter(store, aid, med_kilder=False)
    with zipfile.ZipFile(output['documentation_archive']) as archive:
        assert f'audit/attempts/{first["forsok"]["id"]}/raasvar.txt' in archive.namelist()


def test_default_result_review_correction_retry_and_snapshot(tmp_path, monkeypatch):
    store, aid, runs, seen = fixture(tmp_path, monkeypatch)
    plan = tjeneste.vis_plan(store, aid)
    assert 'task_path' in plan and 'criteria_path' not in plan
    tjeneste.godkjenn_plan(store, aid, 'Fixture reviewer')
    tjeneste.start(store, aid)
    attempt = store.forsok_for_kjoring(runs[0]['id'])[0]
    old = attempt['raasvar']
    correction = {'result': '# Corrected\n\nActual corrected deliverable.', 'source_units_read': [1, 2], 'limitations': []}
    review = tjeneste.registrer_kontroll(store, attempt['id'], 'Reviewer', 'rettet', 'Checked against original',
                                        replacement_response=correction)
    assert review['result'] == correction['result']
    assert store.forsok(attempt['id'])['raasvar'] == old
    out = tjeneste.eksporter(store, aid)
    with zipfile.ZipFile(out['documentation_archive']) as archive:
        assert 'Actual corrected' in archive.read(f'results/{runs[0]["id"]}.md').decode('utf-8')
    assert 'Extract passages' in visning.md_plan(tjeneste.vis_plan(store, aid))
    assert 'Actual corrected' in visning.md_kjoring(tjeneste.vis_kjoring(store, runs[0]['id']))
    assert out['entrypoint'] in visning.md_eksport(out)
    tjeneste.nytt_forsok(store, runs[0]['id'], 'Explicit test retry')
    tjeneste.start(store, aid)
    latest = tjeneste.vis_kjoring(store, runs[0]['id'])['forsok'][-1]
    assert latest['review_status'] == 'ikke kontrollert'
    assert len(store.forsok_for_kjoring(runs[0]['id'])) == 2
    out2 = tjeneste.eksporter(store, aid)
    assert out['mappe'] != out2['mappe']
    with zipfile.ZipFile(out2['documentation_archive']) as archive:
        assert len({p.split('/')[2] for p in archive.namelist() if p.startswith('audit/attempts/')}) == 3


def test_versioning_and_mcp_preserve_custom_contract(tmp_path, monkeypatch):
    store, aid, runs, _ = fixture(tmp_path, monkeypatch, structured=True)
    old = store.gjeldende_planversjon(aid)
    tjeneste.ny_planversjon(store, aid, 'Readable result', reset_output_schema=True, quote_checks=[],
                            task_instructions='Write a readable account of the audit position.')
    assert store.planversjon(old['id'])['plan'].output_schema == SCHEMA
    assert store.gjeldende_planversjon(aid)['plan'].output_schema is None
    functions = {}
    class Server:
        def tool(self, **kwargs):
            def decorate(fn):
                functions[fn.__name__] = fn
                return fn
            return decorate
    register(Server(), lambda: store)
    project = store.analyse(aid)['prosjekt_id']
    response = json.loads(functions['create_analysis'](project_id=project, name='Free task', request='Summarize.', engine='claude_cli'))
    assert 'error' not in response, response
    assert response['plan_version']['plan']['task_instructions'] == 'Summarize.'
    result = public_result({'result': {'navn': 'unchanged', 'svar': {'side': 2}}, 'output_schema': SCHEMA})
    assert result['result']['svar']['side'] == 2
    assert result['output_schema'] == SCHEMA


@pytest.mark.parametrize('quote,unit', [('we support a mandatory annual accessibility audit.', 1),
    ('invented', 1), (QUOTE, 2), ('', 1)])
def test_quote_validation_rejects_non_whitespace_changes(quote, unit):
    plan = Plan('Extract', task_instructions='Extract', output_schema=SCHEMA, quote_checks=CHECKS)
    doc = {'sider': [{'nr': 1, 'tekst': QUOTE, 'tegn': len(QUOTE)}]}
    response = {'result': [{'navn': 'Audit', 'passage': quote, 'unit': unit}], 'source_units_read': [1], 'limitations': []}
    assert not validate(plan, doc, response, [1])['gyldig']


def test_contract_rejects_silent_rewrites_and_references():
    plan = Plan('Test', task_instructions='Test', output_schema={'type': 'object', 'properties': {'x': {'type': 'string'}}})
    assert 'all properties required' in problem(plan)
    plan.output_schema = {'$ref': 'https://example.org/schema'}
    assert 'references' in problem(plan)
    plan.output_schema = {'type': ['string', 'null']}
    assert problem(plan) is None
    plan.output_schema = {'type': 'object', 'properties': {'$ref': {'type': 'string'}},
                          'required': ['$ref'], 'additionalProperties': False}
    assert problem(plan) is None  # user-defined property name is not a schema reference
    plan.output_schema = None
    assert problem(plan) is None


def test_generic_plan_approval_and_contract_revision_are_enforced(tmp_path, monkeypatch):
    store, aid, runs, seen = fixture(tmp_path, monkeypatch)
    with pytest.raises(tjeneste.TjenesteFeil):
        tjeneste.start(store, aid)
    assert not seen
    tjeneste.godkjenn_plan(store, aid, 'Fixture reviewer')
    first = tjeneste.vis_inputpakke(store, runs[0]['id'])['pakke']['input_hash']
    tjeneste.ny_planversjon(store, aid, 'Different task', task_instructions='Describe disagreements.')
    with pytest.raises(tjeneste.TjenesteFeil):
        tjeneste.start(store, aid)
    assert not seen
    preview = tjeneste.vis_plan(store, aid)
    assert preview['latest']['status'] == 'utkast'
    assert 'Describe disagreements.' in Path(preview['plan_path']).read_text(encoding='utf-8')
    new = tjeneste.legg_til_kjoringer(store, aid)['nye'][0]
    assert tjeneste.vis_inputpakke(store, new['id'])['pakke']['input_hash'] != first
