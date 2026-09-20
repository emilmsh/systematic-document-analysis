"""Local extraction and orchestration checks. No provider/model calls."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from kildeanalyse import tjeneste, ocr
from kildeanalyse.chunking import prepare, preview, execute, size, settings
from kildeanalyse.dokument import importer_dokument, DokumentFeil
from kildeanalyse.lager import Lager, KJ_FULLFORT, KJ_FEILET
from kildeanalyse.modell import Plan, Kriterium, Motorsvar, Stotte
from kildeanalyse.parametre import normaliser
from kildeanalyse.prompt import bygg_inputpakke
from kildeanalyse.adaptere import ADAPTERE

QUOTE = 'The board adopted a documented policy.'


def context(engine='claude_cli', *, text=None, budget=8000):
    model, values = normaliser(engine, 'chosen-model', {'input_budget_bytes':budget,
        **({'base_url':'https://example.org/v1'} if engine == 'kompatibel_api' else {})})
    plan = Plan(formaal='Look for the policy', kriterier=[Kriterium('policy','Policy','Is there a policy?',
        ['yes','not_mentioned'],['yes'])], motor=engine, modell=model, motorinnstillinger=values, sprak='en')
    text = text or ('Ordinary source content. '*800 + QUOTE + ' End of text. '*800)
    document = {'id':'d1','navn':'source.pdf','sha256':'abc','antall_sider':1,
        'sider':[{'nr':1,'tekst':text,'tegn':len(text)}]}
    package = bygg_inputpakke(plan, document, forsok_id='f1', kjoring_id='k1')
    return plan, document, package


def fake_reader(package, *args):
    if 'findings' in package.svarskjema['properties']:
        evidence = [{'side':s.nr,'sitat':QUOTE} for s in package.sider if QUOTE in s.tekst]
        payload = {'findings':[{'kriterium_id':'policy','belegg':evidence,'kommentar':'Found.' if evidence else 'No evidence in fragment.'}],
            'sider_lest':[s.nr for s in package.sider],'merknader':[]}
    else:
        data = json.loads(package.brukermelding)
        evidence = next(f['belegg'] for c in data['chunks'] for f in c['findings'] if f['belegg'])
        payload = {'vurderinger':[{'kriterium_id':'policy','svar':'yes','belegg':evidence,'kommentar':'Explicit.'}],
            'sider_lest':[],'merknader':[]}
    return Motorsvar(json.dumps(payload), payload, forbruk={'tokens':10}, modell_rapportert='mock-model')


def test_priorities_change_order_without_losing_source_coverage():
    plan, doc, package = context()
    original, baseline = prepare(plan,doc,package)
    plan.motorinnstillinger['priority_terms'] = ['documented policy']
    ordered, summary = prepare(plan,doc,package)
    assert QUOTE in ordered[0].sider[0].tekst
    assert sorted(json.dumps(x) for x in summary['ranges']) == sorted(json.dumps(x) for x in baseline['ranges'])
    assert len(original) == len(ordered)
    with pytest.raises(ValueError):
        settings({'priority_terms':'not a list'})


@pytest.mark.parametrize('engine', ['claude_cli','codex_cli','openai_api','anthropic_api','openrouter_api','kompatibel_api'])
def test_complete_chunk_workflow_all_engines(tmp_path, monkeypatch, engine):
    plan, document, package = context(engine)
    chunks, summary = prepare(plan, document, package)
    assert len(chunks) > 1 and all(size(p) <= 8000 for p in chunks)
    intervals = summary['ranges']
    previous = 0
    for interval in intervals:
        interval = interval[0]
        assert interval['start'] <= previous
        previous = interval['end']
    assert previous == len(document['sider'][0]['tekst'])
    # Request identity excludes provisional attempt names.
    a = preview(plan, document, package)
    package.forsok_id = 'f1 (planned)'
    assert preview(plan, document, package)['input_hash'] == a['input_hash']
    observed = []
    adapter_class = ADAPTERE[engine]
    monkeypatch.setattr(adapter_class, 'sjekk_stotte', lambda self:Stotte(True))
    def read(self, package, *args):
        observed.append(package)
        assert package.kjoreparametre['modell'] == 'chosen-model'
        assert package.kjoreparametre['tenkenivaa'] == plan.motorinnstillinger['tenkenivaa']
        if package.api_foresporsel:
            assert json.dumps(package.systeminstruks) in json.dumps(package.api_foresporsel['body'])
        return fake_reader(package, *args)
    monkeypatch.setattr(adapter_class, 'kjor', read)
    store = Lager(tmp_path/'data'); project = tjeneste.opprett_prosjekt(store,'Chunks')
    file = tmp_path/'source.txt'; file.write_text(document['sider'][0]['tekst'],encoding='utf-8')
    importer_dokument(store, project['id'], file)
    created = tjeneste.opprett_analyse(store,project['id'],'Policy','Find policy',
        {'kriterier':[k.til_dict() for k in plan.kriterier]}, motor=engine, modell=plan.modell,
        motorinnstillinger=plan.motorinnstillinger, sprak='en')
    aid = created['analyse']['id']; run = tjeneste.legg_til_kjoringer(store,aid)['nye'][0]['id']
    planned = tjeneste.vis_inputpakke(store,run)['pakke']
    assert planned['processing']['calls'] > 2
    tjeneste.godkjenn_plan(store,aid,'Local fixture'); tjeneste.start(store,aid)
    assert store.kjoring(run)['status'] == KJ_FULLFORT
    attempt = store.forsok_for_kjoring(run)[0]
    assert attempt['input_hash'] == planned['input_hash']
    exported = Path(tjeneste.eksporter(store,aid)['mappe'])/'forsok'/attempt['id']
    calls = list((exported/'calls').glob('*/input.json'))
    assert len(calls) == len(observed) == planned['processing']['calls']
    assert json.loads((exported/'input.json').read_text(encoding='utf-8'))['processing']['mode'] == 'chunked'
    final_raw = json.loads((exported/'raasvar.txt').read_text(encoding='utf-8'))
    assert final_raw['sider_lest'] == []  # raw output never rewritten
    assert json.loads(store.forsok(attempt['id'])['svar_json'])['sider_lest'] == [1]


@pytest.mark.parametrize('failure', ['coverage','quote','synthesis_evidence','absence','stop','oversize'])
def test_partial_work_never_becomes_completed_analysis(tmp_path, failure):
    plan, doc, package = context()
    observed = []
    def run(p, *args):
        observed.append(p)
        reply = fake_reader(p, *args)
        if 'findings' in p.svarskjema['properties']:
            if failure == 'coverage': reply.svar['sider_lest'] = []
            if failure == 'quote': reply.svar['findings'][0]['belegg'] = [{'side':1,'sitat':'fabricated words'}]
            if failure == 'oversize': reply.svar['findings'][0]['kommentar'] = 'x'*8000
        else:
            if failure == 'synthesis_evidence': reply.svar['vurderinger'][0]['belegg'][0]['sitat'] = 'Ordinary source content.'
            if failure == 'absence': reply.svar['vurderinger'][0]['svar'] = 'not_mentioned'
        return reply
    reply = execute(plan,doc,package,SimpleNamespace(kjor=run),lambda:failure == 'stop',tmp_path)
    assert reply.svar is None or reply.avbrutt
    assert reply.motorinfo['stopp_ko']
    if failure in ('coverage','quote','stop'): assert len(observed) <= 1
    if failure == 'oversize': assert all('findings' in p.svarskjema['properties'] for p in observed)


def test_legacy_plan_single_and_explicit_limits():
    plan, doc, p = context()
    plan.motorinnstillinger = {}
    assert prepare(plan,doc,p)[1]['mode'] == 'legacy_single'
    plan.motorinnstillinger = settings({'document_processing':'single','input_budget_bytes':8000})
    with pytest.raises(ValueError,match='exceeds'): prepare(plan,doc,p)
    plan.motorinnstillinger = settings({'max_chunks':2,'input_budget_bytes':8000})
    with pytest.raises(ValueError,match='max_chunks'): prepare(plan,doc,p)
    plan.formaal = 'long instructions '*10000
    p = bygg_inputpakke(plan,doc,forsok_id='f',kjoring_id='k')
    with pytest.raises(ValueError,match='Instructions'): prepare(plan,doc,p)


def test_ocr_missing_dependency_and_languages(monkeypatch, tmp_path):
    pages = [{'nr':1,'tekst':'','tegn':0}]
    monkeypatch.setattr(ocr,'setup',lambda:{'available':False,'installation':'Install Tesseract.'})
    with pytest.raises(ValueError,match='unavailable'): ocr.apply_pdf(tmp_path/'x.pdf',pages)
    monkeypatch.setattr(ocr,'setup',lambda:{'available':True,'languages':['eng']})
    with pytest.raises(ValueError,match='nor'): ocr.apply_pdf(tmp_path/'x.pdf',pages)
    assert ocr.apply_pdf(tmp_path/'x.pdf',pages,mode='off')[0] == pages


def test_ocr_render_selection_and_immutable_import(tmp_path, monkeypatch):
    import fitz
    path = tmp_path/'mixed.pdf'
    with fitz.open() as pdf:
        pdf.new_page().insert_text((50,50), QUOTE)
        pdf.new_page()
        pdf.save(path)
    original = path.read_bytes()
    monkeypatch.setattr(ocr,'setup',lambda:{'available':True,'executable':'tesseract','version':'local mock','languages':['eng','nor']})
    rendered = []
    def recognition(command, **kwargs):
        assert Path(command[1]).is_file()
        rendered.append(command)
        return SimpleNamespace(stdout=QUOTE)
    monkeypatch.setattr(ocr.subprocess,'run',recognition)
    store = Lager(tmp_path/'data'); pr = tjeneste.opprett_prosjekt(store,'OCR')
    before,_ = importer_dokument(store,pr['id'],path)
    after,_ = importer_dokument(store,pr['id'],path,ocr_mode='auto')
    assert len(rendered) == 1 and after['source_metadata']['ocr']['pages'] == [2]
    assert before['id'] != after['id'] and before['sha256'] == after['sha256']
    assert store.dokument(before['id'])['lesbarhet'] == 'delvis' and after['lesbarhet'] == 'lesbar'
    assert importer_dokument(store,pr['id'],path,ocr_mode='auto')[1] is False
    forced,_ = importer_dokument(store,pr['id'],path,ocr_mode='force')
    assert forced['source_metadata']['ocr']['pages'] == [1,2] and len(rendered) == 3
    assert path.read_bytes() == original
