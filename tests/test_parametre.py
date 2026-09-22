"""Parametertransport og planhistorikk uten leverandørkall."""
import io
import csv
import json
from pathlib import Path

import pytest

from kildeanalyse import tjeneste, visning
from kildeanalyse.lager import Lager
from kildeanalyse.prompt import bygg_inputpakke
from kildeanalyse.parametre import normaliser
from kildeanalyse.adaptere.codex_cli import CodexCliAdapter
from kildeanalyse.adaptere.claude_cli import ClaudeCliAdapter
from kildeanalyse.adaptere.api import OpenAiApiAdapter, AnthropicApiAdapter, OpenRouterApiAdapter, KompatibelApiAdapter

FIX = Path(__file__).parent / "fixtures/syntetisk"


def test_planvalg_lagres_og_endring_bevarer_historikk(tmp_path):
    lager = Lager(tmp_path)
    pr = tjeneste.opprett_prosjekt(lager, "Analyse")
    an = tjeneste.opprett_analyse(lager, pr['id'], 'Analyse', 'Bestilling', str(FIX/'eksempelkriterier.json'),
                                motor='codex_cli', modell='gpt-5.6-terra', tenkenivaa='medium')
    aid = an['analyse']['id']
    old = lager.gjeldende_planversjon(aid)['plan']
    tjeneste.ny_planversjon(lager, aid, 'Mer tenking', tenkenivaa='high')
    new = lager.gjeldende_planversjon(aid)['plan']
    assert old.motorinnstillinger['tenkenivaa'] == 'medium'
    assert new.motorinnstillinger['tenkenivaa'] == 'high'
    doc = {'id':'d', 'navn':'d', 'sha256':'sha', 'antall_sider':1, 'sider':[{'nr':1,'tekst':'tekst','tegn':5}]}
    a = bygg_inputpakke(old, doc, forsok_id='f', kjoring_id='k')
    b = bygg_inputpakke(new, doc, forsok_id='f', kjoring_id='k')
    assert a.hash() != b.hash()
    assert 'high' in visning.md_plan(tjeneste.vis_plan(lager, aid))
    tjeneste.ny_planversjon(lager, aid, 'Mer tid', motorinnstillinger={'tidsavbrudd_sek':1200})
    assert lager.gjeldende_planversjon(aid)['plan'].motorinnstillinger == {
        'tenkenivaa':'high','tidsavbrudd_sek':1200,
        'document_processing':'auto','input_budget_bytes':60000,'max_chunks':100,'file_tools':True}
    tjeneste.ny_planversjon(lager, aid, 'Claude', motor='claude_cli')
    assert lager.gjeldende_planversjon(aid)['plan'].modell == 'sonnet'


@pytest.mark.parametrize('engine,level', [('claude_cli','ultra'),('codex_cli','auto'),('simulert','high')])
def test_ugyldige_valg_avvises(engine, level):
    with pytest.raises(ValueError):
        normaliser(engine, '', tenkenivaa=level)


@pytest.mark.parametrize('adapter', [ClaudeCliAdapter, CodexCliAdapter])
def test_parametre_sendes_til_prosess(adapter, tmp_path, monkeypatch):
    calls = []
    raw = (json.dumps({'structured_output':{'vurderinger':[]}}) if adapter is ClaudeCliAdapter else
           '\n'.join(json.dumps(e) for e in [
               {'type':'item.completed','item':{'type':'agent_message','text':'{"vurderinger":[]}'}},
               {'type':'turn.completed'}]))
    class Process:
        pid = 34567
        returncode = 0
        def __init__(self, args, **kwargs):
            calls.append((args, kwargs))
            self.stdin, self.stdout, self.stderr = io.BytesIO(), io.BytesIO(raw.encode()), io.BytesIO()
        def communicate(self, **kwargs): return raw.encode(), b''
        def poll(self): return 0
        def wait(self): return 0
    monkeypatch.setattr('subprocess.Popen', Process)
    monkeypatch.setenv('CLAUDE_CODE_EFFORT_LEVEL', 'low')
    monkeypatch.setenv('MAX_THINKING_TOKENS', '0')
    for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'OPENROUTER_API_KEY', 'SDA_CUSTOM_API_KEY'):
        monkeypatch.setenv(key, 'local-fake-key')
    motor = adapter({'tenkenivaa':'high'})
    monkeypatch.setattr(motor, '_bin', lambda:'cli')
    from kildeanalyse.modell import Inputpakke, Stotte
    monkeypatch.setattr(motor, 'sjekk_stotte', lambda:Stotte(True))
    pakke = Inputpakke('f','k','d','dok','sha',[],'instruks','tekst',{'type':'object','properties':{}})
    result = motor.kjor(pakke, 'chosen-model', lambda:False, str(tmp_path))
    args, env = calls[0][0], calls[0][1].get('env', {})
    assert env and not any(k.endswith('_API_KEY') for k in env)
    assert args[args.index('--model')+1] == 'chosen-model'
    if adapter is ClaudeCliAdapter:
        assert args[args.index('--effort')+1] == 'high'
        assert 'CLAUDE_CODE_EFFORT_LEVEL' not in env and 'MAX_THINKING_TOKENS' not in env
    else:
        assert 'model_reasoning_effort="high"' in args
    assert result.motorinfo['tenkenivaa_onsket'] == 'high'


@pytest.mark.parametrize('engine,adapter', [('claude_cli',ClaudeCliAdapter),('codex_cli',CodexCliAdapter),
    ('openai_api',OpenAiApiAdapter),('anthropic_api',AnthropicApiAdapter),
    ('openrouter_api',OpenRouterApiAdapter),('kompatibel_api',KompatibelApiAdapter)])
def test_parametre_i_input_historikk_og_eksport(engine, adapter, tmp_path, monkeypatch):
    from kildeanalyse.modell import Stotte, Motorsvar
    observed = []
    monkeypatch.setattr(adapter, 'sjekk_stotte', lambda self:Stotte(True))
    def local_run(self, pakke, modell, *args):
        observed.append((modell, self.innstillinger['tenkenivaa'], pakke.kjoreparametre['language']))
        if pakke.kjoreparametre['language'] == 'en':
            assert 'Write commentary (kommentar) and notes (merknader) in English' in pakke.systeminstruks
        # Ingen leverandørkontakt. Prøver lagring også for et mislykket forsøk.
        return Motorsvar(raasvar='lokal kontroll', svar=None, feil='lokal kontroll uten modellkall')
    monkeypatch.setattr(adapter, 'kjor', local_run)
    lager = Lager(tmp_path)
    pr = tjeneste.opprett_prosjekt(lager, 'Parametre')
    tjeneste.importer_dokumenter(lager, pr['id'], [str(FIX/'fjordblikk_2025.pdf')])
    an = tjeneste.opprett_analyse(lager, pr['id'], 'Analyse', 'Bestilling', str(FIX/'eksempelkriterier.json'),
                                motor=engine, modell='valgt-modell', tenkenivaa='medium',
                                motorinnstillinger={'base_url':'https://example.org/v1'} if engine == 'kompatibel_api' else None)
    aid = an['analyse']['id']
    for level in ('medium', 'high'):
        if level == 'high':
            tjeneste.ny_planversjon(lager, aid, 'Mer tenking, English', tenkenivaa=level, sprak='en')
        tjeneste.godkjenn_plan(lager, aid, 'Lokal kontroll')
        kid = tjeneste.legg_til_kjoringer(lager, aid)['nye'][0]['id']
        preview = tjeneste.vis_inputpakke(lager, kid)['pakke']
        assert level in visning.md_plan(tjeneste.vis_plan(lager, aid))
        tjeneste.start(lager, aid)
        attempt = lager.forsok_for_kjoring(kid)[0]
        saved = Path(attempt['input_sti'])
        assert json.loads((saved/'input.json').read_text(encoding='utf-8'))['input_hash'] == preview['input_hash']
        assert json.loads((saved/'manifest.json').read_text(encoding='utf-8'))['kjoreparametre']['tenkenivaa'] == level
    assert observed == [('valgt-modell','medium','nb'),('valgt-modell','high','en')]
    out = Path(tjeneste.eksporter(lager, aid, legacy_format=True)['mappe'])
    exported = json.loads((out/'resultater.json').read_text(encoding='utf-8'))
    assert [v['plan']['motorinnstillinger']['tenkenivaa'] for v in exported['planversjoner']] == ['medium','high']
    assert [v['plan']['sprak'] for v in exported['planversjoner']] == ['nb','en']
    plantext = (out/'plan.md').read_text(encoding='utf-8')
    assert 'medium' in plantext and 'high' in plantext and 'valgt-modell' in plantext
    for file in ('resultater.csv','forsok.csv'):
        with (out/file).open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f, delimiter=';'))
        assert [r['tenkenivaa_onsket'] for r in rows] == ['medium','high']
        assert [r['language'] for r in rows] == ['nb','en']
        if engine.endswith('_api'):
            assert all(r['api_endpoint'].startswith('https://') and r['maks_output_tokens'] == '16384' for r in rows)
    for kid in lager.kjoringer(aid):
        fid = lager.forsok_for_kjoring(kid['id'])[0]['id']
        assert (out/'forsok'/fid/'input.json').is_file()
