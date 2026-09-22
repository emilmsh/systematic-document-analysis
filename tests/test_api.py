"""API-kontrakter og feilgrenser med falsk HTTP-transport. Aldri leverandørkontakt."""
import asyncio
import json
import time

import httpx
import pytest

from kildeanalyse.adaptere import lag_adapter
from kildeanalyse.adaptere.api import les_svar
from kildeanalyse.api_oppsett import API_MOTORER, AZURE_FORMATS, wire_engine
from kildeanalyse.modell import Plan, Kriterium
from kildeanalyse.parametre import normaliser
from kildeanalyse.prompt import bygg_inputpakke

ANSWER = {'vurderinger':[{'kriterium_id':'k1','svar':'ja','belegg':[], 'kommentar':''}],
          'sider_lest':[1], 'merknader':[]}
API_CASES = [(engine, None) for engine in API_MOTORER if engine != 'azure_foundry_api'] + [
    ('azure_foundry_api', fmt) for fmt in AZURE_FORMATS]


def package(engine, level='high', **settings):
    if engine == 'kompatibel_api':
        settings.setdefault('base_url', 'https://example.org/v1')
    if settings.get('api_format') is None:
        settings.pop('api_format', None)
    if engine == 'azure_foundry_api':
        settings.setdefault('base_url', 'https://test-resource.services.ai.azure.com')
        settings.setdefault('api_format', 'responses')
    model, settings = normaliser(engine, 'chosen-model', settings, level)
    plan = Plan('formål', [Kriterium('k1','navn','spørsmål',['ja'])], motor=engine,
                modell=model, motorinnstillinger=settings)
    doc = {'id':'d1','navn':'dokument','sha256':'sha','antall_sider':1,
           'sider':[{'nr':1,'tekst':'Dokument med æøå.','tegn':17}]}
    return bygg_inputpakke(plan, doc, forsok_id='f1', kjoring_id='k1'), settings


def response(engine, answer=ANSWER, api_format=None):
    engine = wire_engine(engine, {'api_format': api_format or 'responses'})
    data = {'id':'req-1','model':'reported-model','usage':{'input_tokens':100,'output_tokens':20}}
    text = json.dumps(answer)
    if engine == 'openai_api':
        data.update(status='completed', output=[{'type':'message','role':'assistant','content':[{'type':'output_text','text':text}]}])
    elif engine == 'anthropic_api':
        data.update(stop_reason='end_turn', content=[{'type':'thinking','thinking':'local'}, {'type':'text','text':text}])
    else:
        data.update(choices=[{'finish_reason':'stop','message':{'role':'assistant','content':text}}])
    return data


@pytest.fixture
def transport(monkeypatch):
    original = httpx.AsyncClient
    def install(handler):
        monkeypatch.setattr(httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    for _, env, _ in API_MOTORER.values():
        monkeypatch.setenv(env, 'fake-secret-for-offline-tests')
    return install


@pytest.mark.parametrize('engine,api_format', API_CASES)
def test_exact_request_and_success(engine, api_format, transport, tmp_path):
    pakke, settings = package(engine, api_format=api_format)
    observed = []
    def handler(req):
        observed.append(req)
        assert str(req.url) == pakke.api_foresporsel['url']
        assert json.loads(req.content) == pakke.api_foresporsel['body']
        return httpx.Response(200, json=response(engine, api_format=api_format), headers={'x-request-id':'trace-1'})
    transport(handler)
    result = lag_adapter(engine, settings).kjor(pakke, 'chosen-model', lambda:False, str(tmp_path))
    assert result.svar == ANSWER and not result.feil
    assert len(observed) == 1 and result.modell_rapportert == 'reported-model'
    assert result.motorinfo['request_id'] == 'trace-1'
    assert 'fake-secret' not in json.dumps(pakke.til_dict())
    body = pakke.api_foresporsel['body']
    wire = wire_engine(engine, settings)
    if engine == 'azure_foundry_api':
        header = 'x-api-key' if api_format == 'anthropic_messages' else 'api-key'
        assert observed[0].headers[header] == 'fake-secret-for-offline-tests'
        assert 'authorization' not in observed[0].headers
        assert result.motorinfo['api_format'] == api_format
        assert 'tools' not in body
    if wire == 'openai_api':
        assert body['reasoning'] == {'effort':'high'} and body['store'] is False
        assert body['text']['format']['schema'] == pakke.svarskjema
    elif wire == 'anthropic_api':
        assert body['output_config']['effort'] == 'high' and body['thinking'] == {'type':'adaptive'}
        assert observed[0].headers['anthropic-version'] == '2023-06-01'
    elif engine == 'openrouter_api':
        assert body['reasoning']['effort'] == 'high'
        assert body['provider'] == {'require_parameters':True, 'allow_fallbacks':False}
    else:
        assert body['reasoning_effort'] == 'high'


@pytest.mark.parametrize('engine,api_format', API_CASES)
def test_standard_omits_effort_and_hash_tracks_options(engine, api_format):
    default, settings = package(engine, 'standard', api_format=api_format)
    high, _ = package(engine, 'high', api_format=api_format)
    larger, _ = package(engine, 'standard', maks_output_tokens=20000, api_format=api_format)
    assert len({default.hash(), high.hash(), larger.hash()}) == 3
    body = default.api_foresporsel['body']
    assert 'reasoning' not in body and 'reasoning_effort' not in body
    assert 'effort' not in body.get('output_config', {})
    if engine == 'openrouter_api':
        pinned, _ = package(engine, provider='OpenAI')
        assert pinned.api_foresporsel['body']['provider']['only'] == ['OpenAI']
        assert pinned.hash() != high.hash()


@pytest.mark.parametrize('status', [302,400,401,402,403,429,500,503])
def test_http_errors_stop_without_retry_and_redact_secrets(status, transport, tmp_path):
    pakke, settings = package('openai_api')
    calls=[]
    def handler(req):
        calls.append(req)
        return httpx.Response(status, json={'error':'fake-secret-for-offline-tests'}, headers={'location':'https://other.example/'})
    transport(handler)
    result = lag_adapter('openai_api', settings).kjor(pakke, 'chosen-model', lambda:False, str(tmp_path))
    assert result.feil and result.motorinfo['stopp_ko'] and len(calls) == 1
    assert 'fake-secret' not in json.dumps(result.__dict__)


@pytest.mark.parametrize('engine,api_format', API_CASES)
def test_truncation_refusal_and_bad_schema(engine, api_format, transport, tmp_path):
    pakke, settings = package(engine, api_format=api_format)
    data = response(engine, {'unexpected':'object'}, api_format=api_format)
    transport(lambda req:httpx.Response(200, json=data))
    result = lag_adapter(engine, settings).kjor(pakke, 'chosen-model', lambda:False, str(tmp_path))
    assert result.svar is None and result.feil and result.raasvar
    truncated = response(engine, api_format=api_format)
    wire = wire_engine(engine, settings)
    if wire == 'openai_api':
        truncated['status'] = 'incomplete'
    elif wire == 'anthropic_api':
        truncated['stop_reason'] = 'max_tokens'
    else:
        truncated['choices'][0]['finish_reason'] = 'length'
    with pytest.raises(ValueError):
        les_svar(engine, truncated, settings)


@pytest.mark.parametrize('stop_mode', ['before','during','timeout','network'])
def test_stop_timeout_network_no_retry(stop_mode, transport, tmp_path):
    pakke, settings = package('openai_api', tidsavbrudd_sek=0.05 if stop_mode == 'timeout' else 600)
    calls=[]
    cleaned=[]
    async def handler(req):
        calls.append(req)
        if stop_mode == 'network':
            raise httpx.ConnectError('secret must not enter log', request=req)
        try:
            await asyncio.sleep(10)
        finally:
            cleaned.append(True)
        return httpx.Response(200, json=response('openai_api'))
    transport(handler)
    started=time.monotonic()
    stop=lambda:stop_mode == 'before' or (stop_mode == 'during' and time.monotonic()-started > .05)
    result=lag_adapter('openai_api', settings).kjor(pakke, 'chosen-model', stop, str(tmp_path))
    assert result.feil and result.svar is None and result.motorinfo['stopp_ko']
    assert len(calls) == (0 if stop_mode == 'before' else 1)
    assert result.avbrutt == (stop_mode in ('before','during'))
    if stop_mode in ('during','timeout'):
        assert cleaned


@pytest.mark.parametrize('settings', [{'api_key':'secret'}, {'headers':{}}, {'base_url':'https://evil.example'},
                                    {'maks_output_tokens':True}, {'maks_output_tokens':0}, {'provider':'wrong'}])
def test_bad_settings_rejected_before_persistence(settings):
    with pytest.raises(ValueError):
        normaliser('openai_api', 'model', settings)


@pytest.mark.parametrize('url', ['', 'http://example.org/v1','https://user:secret@example.org/v1',
                                 'https://example.org/v1?key=secret','https://example.org/v1#secret'])
def test_custom_url_is_explicit_https(url):
    with pytest.raises(ValueError):
        normaliser('kompatibel_api', 'model', {'base_url':url})


@pytest.mark.parametrize('fmt,base,path', [
    ('responses', 'https://demo.openai.azure.com/', '/openai/v1/responses'),
    ('chat_completions', 'https://demo.services.ai.azure.com/openai/v1/', '/openai/v1/chat/completions'),
    ('anthropic_messages', 'https://demo.services.ai.azure.com/anthropic', '/anthropic/v1/messages'),
    ('anthropic_messages', 'https://demo.services.ai.azure.com/anthropic/v1/', '/anthropic/v1/messages'),
])
def test_azure_endpoint_and_protocol_are_explicit(fmt, base, path):
    from urllib.parse import urlsplit
    pakke, _ = package('azure_foundry_api', api_format=fmt, base_url=base)
    assert pakke.api_foresporsel['url'] == 'https://' + urlsplit(base).hostname + path
    changed, _ = package('azure_foundry_api', api_format=fmt, base_url='https://other.services.ai.azure.com')
    assert changed.hash() != pakke.hash()


@pytest.mark.parametrize('base,fmt', [
    ('https://demo.services.ai.azure.com', None),
    ('https://demo.services.ai.azure.com', 'automatic'),
    ('https://demo.services.ai.azure.com', []),
    ('https://demo.services.ai.azure.com/api/projects/example', 'responses'),
    ('https://demo.services.ai.azure.com/anthropic', 'responses'),
    ('https://demo.openai.azure.com', 'anthropic_messages'),
    ('https://demo.services.ai.azure.com/openai/v1', 'anthropic_messages'),
    ('https://demo.services.ai.azure.com.evil.example', 'responses'),
    ('http://demo.services.ai.azure.com', 'chat_completions'),
    ('https://demo.services.ai.azure.com?key=secret', 'responses'),
    ('https://user:secret@demo.services.ai.azure.com', 'responses'),
])
def test_azure_invalid_destination_or_format_is_rejected(base, fmt):
    with pytest.raises(ValueError):
        normaliser('azure_foundry_api', 'deployment', {'base_url': base, 'api_format': fmt})


def test_azure_protocol_and_deployment_changes_require_new_input():
    packages = [package('azure_foundry_api', api_format=fmt)[0] for fmt in AZURE_FORMATS]
    assert len({p.hash() for p in packages}) == 3
    with pytest.raises(ValueError):
        package('azure_foundry_api', 'none', api_format='anthropic_messages')
    with pytest.raises(ValueError):
        normaliser('openai_api', 'model', {'api_format': 'chat_completions'})


@pytest.mark.parametrize('fmt', AZURE_FORMATS)
def test_azure_rejection_never_changes_protocol_or_exposes_key(fmt, transport, tmp_path):
    pakke, settings = package('azure_foundry_api', api_format=fmt)
    calls = []
    def handler(req):
        calls.append(req)
        return httpx.Response(400, json={'error': 'unsupported schema fake-secret-for-offline-tests'})
    transport(handler)
    result = lag_adapter('azure_foundry_api', settings).kjor(pakke, 'chosen-model', lambda: False, str(tmp_path))
    assert result.feil and result.svar is None and len(calls) == 1
    assert str(calls[0].url) == pakke.api_foresporsel['url']
    assert 'fake-secret' not in json.dumps(result.__dict__)


def test_model_required_and_missing_key_is_local(monkeypatch):
    for engine, (_, env, _) in API_MOTORER.items():
        monkeypatch.delenv(env, raising=False)
        assert not lag_adapter(engine).sjekk_stotte().ok
        with pytest.raises(ValueError):
            normaliser(engine, '')


def test_request_change_blocks_send(transport, tmp_path):
    from kildeanalyse.adaptere.base import AdapterFeil
    pakke, settings = package('openai_api')
    pakke.api_foresporsel['body']['model']='altered'
    transport(lambda req:pytest.fail('Must not send changed request'))
    with pytest.raises(AdapterFeil):
        lag_adapter('openai_api', settings).kjor(pakke, 'chosen-model', lambda:False, str(tmp_path))


def test_file_key_authentication_and_response_redaction(transport, tmp_path, monkeypatch):
    from dataclasses import asdict
    from kildeanalyse.credentials import prepare_file
    from kildeanalyse.api_oppsett import local_key
    for _, name, _ in API_MOTORER.values():
        monkeypatch.delenv(name,raising=False)
    path=prepare_file(); path.write_text('OPENAI_API_KEY=private-file-secret\n',encoding='utf-8')
    pakke, settings = package('openai_api')
    def handler(req):
        assert req.headers['Authorization'] == 'Bearer private-file-secret'
        assert b'private-file-secret' not in req.content
        return httpx.Response(429,json={'error':'private-file-secret'})
    transport(handler)
    result=lag_adapter('openai_api',settings).kjor(pakke,'chosen-model',lambda:False,str(tmp_path))
    assert result.feil and 'private-file-secret' not in json.dumps(asdict(result))
    assert local_key('openai_api') == 'private-file-secret'


@pytest.mark.parametrize('engine,api_format', API_CASES)
def test_full_workflow_and_export_with_http_mock(engine, api_format, transport, tmp_path):
    from pathlib import Path
    from kildeanalyse import tjeneste, visning
    from kildeanalyse.lager import Lager, KJ_FULLFORT
    lager = Lager(tmp_path)
    pr = tjeneste.opprett_prosjekt(lager, 'API arbeidsflyt')
    fix = Path(__file__).parent/'fixtures/syntetisk/fjordblikk_2025.pdf'
    imported = tjeneste.importer_dokumenter(lager, pr['id'], [str(fix)])
    doc = imported['resultater'][0]['dokument']
    _, settings = package(engine, api_format=api_format)
    criteria = {'kriterier':[{'id':'k1','spørsmål':'Lokal kontroll','tillatte_svar':['ja']}]}
    created = tjeneste.opprett_analyse(lager, pr['id'], 'API', 'Bestilling', criteria,
        motor=engine, modell='chosen-model', motorinnstillinger=settings, sprak='en')
    aid = created['analyse']['id']
    text = visning.md_plan(tjeneste.vis_plan(lager, aid))
    assert 'separat betaling' in text and '16384' in text
    if engine == 'azure_foundry_api':
        assert api_format in text
    kid = tjeneste.legg_til_kjoringer(lager, aid)['nye'][0]['id']
    preview = tjeneste.vis_inputpakke(lager, kid)['pakke']
    answer = dict(ANSWER, sider_lest=list(range(1, doc['antall_sider']+1)))
    quote = doc['sider'][0]['tekst'].strip()[:80]
    answer['vurderinger'] = [dict(ANSWER['vurderinger'][0], belegg=[{'side':1,'sitat':quote}])]
    requests=[]
    def handler(req):
        requests.append(req)
        assert json.loads(req.content) == preview['api_foresporsel']['body']
        return httpx.Response(200, json=response(engine, answer, api_format=api_format))
    transport(handler)
    # Ingen forespørsler før godkjenning og start.
    assert not requests
    tjeneste.godkjenn_plan(lager, aid, 'Automatisk lokal kontroll')
    tjeneste.start(lager, aid)
    assert lager.kjoring(kid)['status'] == KJ_FULLFORT and len(requests) == 1
    attempt = lager.forsok_for_kjoring(kid)[0]
    export = Path(tjeneste.eksporter(lager, aid, legacy_format=True)['mappe'])
    saved = json.loads((export/'forsok'/attempt['id']/'input.json').read_text(encoding='utf-8'))
    assert saved['input_hash'] == preview['input_hash'] and saved['api_foresporsel'] == preview['api_foresporsel']
    manifest = json.loads((export/'forsok'/attempt['id']/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['modell_rapportert'] == 'reported-model'
    assert manifest['kjoreparametre']['language'] == 'en'
    assert 'in English' in saved['systeminstruks']
    assert manifest['motorinfo']['harness'].startswith('direct API')
    if engine == 'azure_foundry_api':
        assert manifest['motorinfo']['api_format'] == api_format
        assert manifest['kjoreparametre']['api']['api_format'] == api_format
    import csv
    with (export/'evidence.csv').open(encoding='utf-8-sig', newline='') as source:
        evidence = list(csv.DictReader(source, delimiter=';'))
    assert evidence[0]['quote'] == quote and evidence[0]['answer'] == 'ja'
    original = Path(attempt['input_sti'])
    for name in ('input.json','manifest.json','raasvar.txt','systeminstruks.txt'):
        if (original/name).is_file():
            assert (export/'forsok'/attempt['id']/name).read_bytes() == (original/name).read_bytes()
    for file in export.rglob('*'):
        if file.is_file():
            assert b'fake-secret-for-offline-tests' not in file.read_bytes()


def test_api_quota_is_reported_per_run_and_redacted_from_export(transport, tmp_path):
    from pathlib import Path
    from kildeanalyse import tjeneste
    from kildeanalyse.lager import Lager
    lager = Lager(tmp_path)
    pr = tjeneste.opprett_prosjekt(lager, 'Kvotestopp')
    fix = Path(__file__).parent/'fixtures/syntetisk'
    tjeneste.importer_dokumenter(lager, pr['id'], [str(fix/'fjordblikk_2025.pdf'), str(fix/'nordlys_2025.pdf')])
    aid = tjeneste.opprett_analyse(lager, pr['id'], 'API', 'Bestilling', str(fix/'eksempelkriterier.json'),
                                  motor='openai_api', modell='chosen-model')['analyse']['id']
    tjeneste.godkjenn_plan(lager, aid, 'Lokal kontroll')
    jobs = tjeneste.legg_til_kjoringer(lager, aid)['nye']
    calls=[]
    def handler(req):
        calls.append(req)
        return httpx.Response(429, json={'error':{'message':'fake-secret-for-offline-tests'}})
    transport(handler)
    report = tjeneste.start(lager, aid)
    assert len(calls) == 2 and report['startet'] == [job['id'] for job in jobs]
    assert all(lager.kjoring(job['id'])['status'] == 'feilet' for job in jobs)
    assert report['workflow_block'] is None and len(report['run_issues']) == 2
    export = Path(tjeneste.eksporter(lager, aid, legacy_format=True)['mappe'])
    for file in export.rglob('*'):
        if file.is_file():
            assert b'fake-secret-for-offline-tests' not in file.read_bytes()
