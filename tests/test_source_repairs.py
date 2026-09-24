"""Source-only safeguards for quotation whitespace and visually checked blank pages."""
import json

import pytest

from kildeanalyse import tjeneste
from kildeanalyse.adaptere import ADAPTERE
from kildeanalyse.dokument import sider_uten_tekst
from kildeanalyse.lager import Lager
from kildeanalyse.modell import Plan, Motorsvar, Stotte
from kildeanalyse.task_contract import validate
from kildeanalyse.task_results import current


SCHEMA = {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
          'properties': {'quote': {'type': 'string'}, 'page': {'type': 'integer'}},
          'required': ['quote', 'page']}}
CHECKS = [{'path': '', 'quote_field': 'quote', 'unit_field': 'page'}]


def test_unique_whitespace_repair_keeps_raw_reply_and_not_human_review():
    plan = Plan('Quote', task_instructions='Extract a quote.', output_schema=SCHEMA, quote_checks=CHECKS)
    source = 'Start. A\u202fB\nC. End.'
    document = {'sider': [{'nr': 1, 'tekst': source, 'tegn': 12}], 'source_metadata': {}}
    response = {'result': [{'quote': 'A B C', 'page': 1}], 'source_units_read': [1], 'limitations': []}
    checked = validate(plan, document, response, [1])
    assert checked['gyldig']
    assert checked['checks']['source_whitespace_repairs'] == 1
    assert checked['quote_repairs'][0]['after'] == 'A\u202fB\nC'
    assert response['result'][0]['quote'] == 'A B C'

    class Store:
        def kontroller(self, _): return []
    attempt = {'id': 'f1', 'svar_json': json.dumps(response), 'validering_json': json.dumps(checked)}
    view = current(Store(), attempt)
    assert view['result'][0]['quote'] == 'A\u202fB\nC'
    assert view['result_origin'] == 'source_whitespace_repair'
    assert view['review_status'] == 'ikke kontrollert'


@pytest.mark.parametrize('source,quote', [('A\u202fB and A\nB', 'A B'), ('A-B', 'A B'), ('AB', 'A B')])
def test_ambiguous_or_non_whitespace_changes_stay_invalid(source, quote):
    plan = Plan('Quote', task_instructions='Extract a quote.', output_schema=SCHEMA, quote_checks=CHECKS)
    document = {'sider': [{'nr': 1, 'tekst': source, 'tegn': 50}], 'source_metadata': {}}
    response = {'result': [{'quote': quote, 'page': 1}], 'source_units_read': [1], 'limitations': []}
    checked = validate(plan, document, response, [1])
    assert not checked['gyldig']
    assert checked['quote_repairs'] == []


def test_image_pdf_page_blocks_until_real_visual_blank_check(tmp_path):
    fitz = pytest.importorskip('fitz')
    path = tmp_path / 'pages.pdf'
    pdf = fitz.open()
    pdf.new_page().insert_text((40, 40), 'Readable document text. ' * 4)
    pdf.new_page().draw_rect(fitz.Rect(40, 40, 400, 400), color=(0, 0, 0), fill=(0, 0, 0))
    pdf.save(path)
    pdf.close()
    store = Lager(tmp_path / 'data')
    project = tjeneste.opprett_prosjekt(store, 'Blank page check')
    document = tjeneste.importer_dokumenter(store, project['id'], [str(path)], ocr_mode='off')['resultater'][0]['dokument']
    assert sider_uten_tekst(document) == [2]
    with pytest.raises(tjeneste.TjenesteFeil, match='visually checked'):
        tjeneste.verify_blank_pdf_page(store, document['id'], 2, '', '')
    # A graphical page is not auto-approved as blank. An explicit visual claim is
    # required; this test does not make that claim about this nonblank page.
    assert store.dokument(document['id'])['source_metadata'].get('verified_blank_pages') is None


def test_verified_blank_page_retains_source_identity_and_coverage(tmp_path):
    fitz = pytest.importorskip('fitz')
    path = tmp_path / 'blank.pdf'
    pdf = fitz.open()
    pdf.new_page().insert_text((40, 40), 'Readable document text. ' * 4)
    pdf.new_page()
    pdf.save(path)
    pdf.close()
    store = Lager(tmp_path / 'data')
    project = tjeneste.opprett_prosjekt(store, 'Blank page check')
    document = tjeneste.importer_dokumenter(store, project['id'], [str(path)], ocr_mode='off')['resultater'][0]['dokument']
    recorded = tjeneste.verify_blank_pdf_page(store, document['id'], 2, 'Fixture viewer', 'Rendered page has no marks or substantive text.')
    assert recorded['remaining_unreadable_pages'] == []
    updated = store.dokument(document['id'])
    assert updated['sha256'] == document['sha256']
    assert updated['source_metadata']['blank_page_checks'][0]['source_sha256'] == document['sha256']
    plan = Plan('Summarize', task_instructions='Summarize the file.')
    response = {'result': 'Readable summary', 'source_units_read': [1], 'limitations': []}
    assert validate(plan, updated, response, [1, 2])['lesedekning']['fullstendig']


def test_export_destination_is_checkable_before_reader_execution(tmp_path):
    store = Lager(tmp_path / 'data')
    project = tjeneste.opprett_prosjekt(store, 'Preflight', str(tmp_path / 'project'))
    analysis = tjeneste.opprett_analyse(store, project['id'], 'Task', 'Summarize',
                                         task_instructions='Summarize each file.')['analyse']
    short = tjeneste.preview_export_destination(store, analysis['id'])
    assert short['ready']
    long_parent = tmp_path / ('long-' * 35)
    long = tjeneste.preview_export_destination(store, analysis['id'], str(long_parent))
    assert not long['ready']
    assert long['path_characters'] > long['windows_excel_budget']


def test_explicit_cli_file_inspection_can_run_on_image_only_pdf(tmp_path, monkeypatch):
    fitz = pytest.importorskip('fitz')
    path = tmp_path / 'visual.pdf'
    pdf = fitz.open()
    page = pdf.new_page()
    page.draw_rect(fitz.Rect(40, 40, 400, 400), fill=(0, 0, 0))
    pdf.save(path)
    pdf.close()
    store = Lager(tmp_path / 'data')
    project = tjeneste.opprett_prosjekt(store, 'Visual task')
    document = tjeneste.importer_dokumenter(store, project['id'], [str(path)], ocr_mode='off')['resultater'][0]['dokument']
    assert document['lesbarhet'] == 'uleselig'
    created = tjeneste.opprett_analyse(store, project['id'], 'Visual inspection', 'Describe the image.',
        task_instructions='Describe the image in this file.', motor='claude_cli',
        tillat_sider_uten_tekst=True)
    aid = created['analyse']['id']
    run = tjeneste.legg_til_kjoringer(store, aid)['nye'][0]
    def reply(self, package, *args):
        response = {'result': 'A black rectangle.', 'source_units_read': [],
                    'limitations': ['No text was extracted; the original page needs visual inspection.']}
        return Motorsvar(json.dumps(response), response, sesjon_id=package.forsok_id,
                         modell_rapportert='fake-model', motorinfo={'test_fixture': True})
    monkeypatch.setattr(ADAPTERE['claude_cli'], 'sjekk_stotte', lambda self: Stotte(True))
    monkeypatch.setattr(ADAPTERE['claude_cli'], 'kjor', reply)
    tjeneste.godkjenn_plan(store, aid, 'Fixture reviewer')
    assert not tjeneste.start(store, aid)['run_issues']
    shown = tjeneste.vis_kjoring(store, run['id'])['forsok'][0]
    assert shown['result'] == 'A black rectangle.'
    assert not shown['validering']['lesedekning']['fullstendig']


def test_unparsed_file_is_available_to_cli_but_api_stops_before_dispatch(tmp_path, monkeypatch):
    source = tmp_path / 'item.custom'
    source.write_text('A task-relevant custom file.', encoding='utf-8')
    store = Lager(tmp_path / 'data')
    project = tjeneste.opprett_prosjekt(store, 'Custom file')
    document = tjeneste.importer_dokumenter(store, project['id'], [str(source)])['resultater'][0]['dokument']
    assert document['source_metadata']['format'] == 'opaque'
    assert document['sha256']
    seen = []
    def reply(self, package, *args):
        seen.append(package)
        response = {'result': 'Task completed on the assigned original.', 'source_units_read': [],
                    'limitations': ['No automatic extraction was available.']}
        return Motorsvar(json.dumps(response), response, sesjon_id=package.forsok_id,
                         modell_rapportert='fake-model', motorinfo={'test_fixture': True})
    monkeypatch.setattr(ADAPTERE['claude_cli'], 'sjekk_stotte', lambda self: Stotte(True))
    monkeypatch.setattr(ADAPTERE['claude_cli'], 'kjor', reply)
    cli = tjeneste.opprett_analyse(store, project['id'], 'Task', 'Work on this file.', motor='claude_cli')
    cli_id = cli['analyse']['id']
    run = tjeneste.legg_til_kjoringer(store, cli_id)['nye'][0]
    tjeneste.godkjenn_plan(store, cli_id, 'Fixture reviewer')
    assert not tjeneste.start(store, cli_id)['run_issues']
    assert seen[0].local_source_path == document['lagret_kopi']
    assert tjeneste.vis_kjoring(store, run['id'])['forsok'][0]['result'] == 'Task completed on the assigned original.'

    called = []
    monkeypatch.setattr(ADAPTERE['openai_api'], 'sjekk_stotte', lambda self: Stotte(True))
    monkeypatch.setattr(ADAPTERE['openai_api'], 'kjor', lambda *args: called.append(True))
    api = tjeneste.opprett_analyse(store, project['id'], 'API task', 'Work on this file.',
                                    motor='openai_api', modell='test-model')
    api_id = api['analyse']['id']
    api_run = tjeneste.legg_til_kjoringer(store, api_id)['nye'][0]
    tjeneste.godkjenn_plan(store, api_id, 'Fixture reviewer')
    assert tjeneste.start(store, api_id)['run_issues']
    assert not called
    assert 'no automatically extracted content' in store.kjoring(api_run['id'])['merknad']
