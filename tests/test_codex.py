import json
import pytest
from kildeanalyse.adaptere.codex_cli import les_hendelser, strengt_skjema, CodexCliAdapter

def stream(extra=None):
    events=[{'type':'thread.started','thread_id':'new-session'}, {'type':'item.completed','item':{'type':'agent_message','text':'{"vurderinger": []}'}}]
    if extra: events.append(extra)
    events.append({'type':'turn.completed','usage':{'input_tokens':50}})
    return '\n'.join(json.dumps(e) for e in events)

def test_codex_jsonl_success():
    result=les_hendelser(stream(),0)
    assert result.svar=={'vurderinger':[]} and result.sesjon_id=='new-session'
    assert result.forbruk['usage']['input_tokens']==50

@pytest.mark.parametrize('extra,code', [({'type':'turn.failed','error':{'message':'usage limit reached'}},0), ({'type':'error','message':'rate limit'},0), ({'type':'item.completed','item':{'type':'command_execution'}},0), (None,1)])
def test_codex_fail_closed(extra,code):
    result=les_hendelser(stream(extra),code)
    assert result.svar is None and result.feil and result.raasvar

@pytest.mark.parametrize('raw',['not json','{}','{"type":"turn.completed"}'])
def test_codex_invalid_response(raw):
    assert les_hendelser(raw,0).feil

def test_strict_schema_preserves_original():
    original={'type':'object','properties':{'vurderinger':{'type':'array','items':{'type':'object','properties':{'svar':{'type':'string'}}}}}}
    result=strengt_skjema(original)
    assert 'additionalProperties' not in original
    assert result['required']==['vurderinger']
    assert result['properties']['vurderinger']['items']['additionalProperties'] is False

def test_no_api_fallback(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','not-a-real-key')
    monkeypatch.setattr(CodexCliAdapter,'_bin',lambda self:'codex')
    assert not CodexCliAdapter().sjekk_stotte().ok

def test_codex_input_schema_is_the_sent_schema():
    from kildeanalyse.modell import Plan
    from kildeanalyse.prompt import bygg_inputpakke
    from pathlib import Path
    raw=json.loads((Path(__file__).parent/'fixtures/syntetisk/eksempelkriterier.json').read_text(encoding='utf-8'))
    plan=Plan.fra_kriteriefil(raw,formaal='Test',motor='codex_cli',modell='')
    doc={'id':'d','navn':'test','sha256':'test','antall_sider':1,'sider':[{'nr':1,'tegn':20,'tekst':'syntetisk dokument'}]}
    pakke=bygg_inputpakke(plan,doc,forsok_id='f',kjoring_id='k')
    assert pakke.svarskjema==strengt_skjema(pakke.svarskjema)
    assert pakke.til_dict()['svarskjema']==pakke.svarskjema

def test_quota_stops_queue_without_retry(tmp_path, monkeypatch):
    from pathlib import Path
    from kildeanalyse import tjeneste
    from kildeanalyse.lager import Lager
    from kildeanalyse.modell import Motorsvar
    from kildeanalyse.adaptere.simulert import SimulertAdapter
    fix=Path(__file__).parent/'fixtures/syntetisk'
    lager=Lager(tmp_path)
    pr=tjeneste.opprett_prosjekt(lager,'Test')
    tjeneste.importer_dokumenter(lager,pr['id'],[str(fix/'fjordblikk_2025.pdf'),str(fix/'nordlys_2025.pdf')])
    an=tjeneste.opprett_analyse(lager,pr['id'],'Test','Test',str(fix/'eksempelkriterier.json'))
    aid=an['analyse']['id']
    tjeneste.godkjenn_plan(lager,aid,'Test')
    kj=tjeneste.legg_til_kjoringer(lager,aid)['nye']
    monkeypatch.setattr(SimulertAdapter,'kjor',lambda *a: Motorsvar(raasvar='usage limit reached',svar=None,feil='usage limit reached',motorinfo={'stopp_ko':True}))
    report=tjeneste.start(lager,aid)
    assert report['startet']==[kj[0]['id']]
    assert lager.kjoring(kj[1]['id'])['status']=='planlagt'
    assert len(lager.forsok_for_kjoring(kj[0]['id']))==1
