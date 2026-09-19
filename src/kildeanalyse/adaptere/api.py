"""Valgfrie API-motorer. Ingen verktøy, automatisk retry eller CLI/API-fallback."""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time

import httpx
from jsonschema import Draft202012Validator

from .base import Adapter, AdapterFeil
from ..api_oppsett import API_MOTORER, API_ENV, api_metadata
from ..modell import Motorsvar, Stotte


def bygg_request(motor, pakke, modell, valg):
    """Ren funksjon; samme payload forhåndsvises, hashes, lagres og sendes."""
    effort = valg.get('tenkenivaa', 'standard')
    maximum = valg.get('maks_output_tokens', 16384)
    schema = pakke.svarskjema
    messages = [{'role': 'system', 'content': pakke.systeminstruks},
                {'role': 'user', 'content': pakke.brukermelding}]
    body = {'model': modell}
    if motor == 'openai_api':
        body.update(input=messages, store=False, max_output_tokens=maximum,
                    text={'format': {'type': 'json_schema', 'name': 'kildeanalyse', 'strict': True, 'schema': schema}})
        if effort != 'standard':
            body['reasoning'] = {'effort': effort}
    elif motor == 'anthropic_api':
        body.update(system=pakke.systeminstruks, messages=messages[1:], max_tokens=maximum,
                    output_config={'format': {'type': 'json_schema', 'schema': schema}})
        if effort != 'standard':
            body['thinking'] = {'type': 'adaptive'}
            body['output_config']['effort'] = effort
    else:
        body.update(messages=messages, max_tokens=maximum,
                    response_format={'type': 'json_schema', 'json_schema': {
                        'name': 'kildeanalyse', 'strict': True, 'schema': schema}})
        if motor == 'openrouter_api':
            body['provider'] = {'require_parameters': True, 'allow_fallbacks': False}
            if valg.get('provider'):
                body['provider']['only'] = [valg['provider']]
            if effort != 'standard':
                body['reasoning'] = {'effort': effort}
        elif effort != 'standard':
            body['reasoning_effort'] = effort
    return {'url': api_metadata(motor, valg)['endpoint'], 'body': body}


def les_svar(motor, data):
    """Avvis ufullstendige svar, refusals og verktøykall før JSON-validering."""
    if not isinstance(data, dict) or data.get('error'):
        raise ValueError('API-et returnerte en feil eller ukjent svarformat.')
    if motor == 'openai_api':
        if data.get('status') != 'completed':
            raise ValueError('API-svaret er ikke fullført (mulig tokengrense eller avvisning).')
        texts = []
        for item in data.get('output', []):
            if item.get('type') == 'reasoning':
                continue
            if item.get('type') != 'message' or item.get('role') != 'assistant':
                raise ValueError('Uventet verktøy eller hendelse i API-svaret.')
            for part in item.get('content', []):
                if part.get('type') != 'output_text':
                    raise ValueError('API-svaret inneholder avvisning eller uventet innhold.')
                texts.append(part['text'])
        text = ''.join(texts)
    elif motor == 'anthropic_api':
        if data.get('stop_reason') != 'end_turn':
            raise ValueError('Claude-svaret er ikke fullført (tokengrense, avvisning eller verktøy).')
        texts = []
        for part in data.get('content', []):
            if part.get('type') in ('thinking', 'redacted_thinking'):
                continue
            if part.get('type') != 'text':
                raise ValueError('Uventet innhold i Claude-svaret.')
            texts.append(part['text'])
        text = ''.join(texts)
    else:
        choices = data.get('choices', [])
        if len(choices) != 1 or choices[0].get('finish_reason') != 'stop':
            raise ValueError('API-svaret er ikke ett fullført svar (mulig tokengrense).')
        message = choices[0]['message']
        if message.get('refusal') or message.get('tool_calls') or message.get('function_call'):
            raise ValueError('API-svaret inneholder avvisning eller verktøykall.')
        text = message.get('content')
    answer = json.loads(text)
    if not isinstance(answer, dict):
        raise ValueError('Sluttsvaret er ikke et JSON-objekt.')
    return answer


class ApiAdapter(Adapter):
    simulert = False

    def __init__(self, innstillinger=None):
        super().__init__(innstillinger)
        self._avbryt = False

    def sjekk_stotte(self):
        metadata = api_metadata(self.navn, self.innstillinger)
        ready = bool(os.environ.get(metadata['nokkelvariabel'], '').strip())
        messages = ['Separat API-forbruk. Nøkkelen er bare kontrollert lokalt; konto, modell og saldo er ikke verifisert.']
        if not ready:
            messages.append(f"Sett {metadata['nokkelvariabel']} lokalt og start vertsappen på nytt. Ikke lim nøkkelen inn i samtalen.")
        if self.navn == 'kompatibel_api' and not self.innstillinger.get('base_url'):
            ready = False
            messages.append('Velg base_url og modell eksplisitt i planen.')
        return Stotte(ready, messages, metadata)

    def avbryt(self):
        self._avbryt = True

    async def _post(self, request, headers, stopp, timeout):
        if stopp() or self._avbryt:
            raise asyncio.CancelledError()
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            task = asyncio.create_task(client.post(request['url'], json=request['body'], headers=headers))
            start = time.monotonic()
            try:
                while True:
                    if stopp() or self._avbryt:
                        raise asyncio.CancelledError()
                    if time.monotonic() - start >= timeout:
                        raise TimeoutError()
                    done, _ = await asyncio.wait({task}, timeout=min(0.1, timeout))
                    if done:
                        return task.result()
            finally:
                if not task.done():
                    task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task

    def kjor(self, pakke, modell, stopp, arbeidsmappe):
        self._avbryt = False
        support = self.sjekk_stotte()
        if not support.ok:
            raise AdapterFeil('; '.join(support.meldinger))
        key = os.environ[API_MOTORER[self.navn][1]].strip()
        request = bygg_request(self.navn, pakke, modell, self.innstillinger)
        if pakke.api_foresporsel != request:
            raise AdapterFeil('API-forespørselen avviker fra inputpakken. Lag en ny plan og inputpakke.')
        # Ingen headers eller nøkkelverdier lagres. Masker eventuelt ekko fra leverandøren.
        secrets = [os.environ[n].strip() for n in API_ENV if os.environ.get(n, '').strip()]
        def redact(text):
            for secret in secrets:
                text = text.replace(secret, '[API-NØKKEL SKJULT]')
                text = text.replace(json.dumps(secret)[1:-1], '[API-NØKKEL SKJULT]')
            return text
        headers = {'Content-Type': 'application/json'}
        if self.navn == 'anthropic_api':
            headers.update({'x-api-key': key, 'anthropic-version': '2023-06-01'})
        else:
            headers['Authorization'] = 'Bearer ' + key
        info = {**support.egenskaper, 'modell_onsket': modell,
                'tenkenivaa_onsket': self.innstillinger.get('tenkenivaa', 'standard'),
                'tenkenivaa_rapportert': 'ukjent', 'stopp_ko': False}
        result = Motorsvar(raasvar='', svar=None, motorinfo=info)
        start = time.monotonic()
        try:
            response = asyncio.run(self._post(request, headers, stopp, float(self.innstillinger.get('tidsavbrudd_sek', 600))))
            result.raasvar = redact(response.text)
            info['http_status'] = response.status_code
            info['request_id'] = redact(response.headers.get('x-request-id') or response.headers.get('request-id') or '')
            if not 200 <= response.status_code < 300:
                info['stopp_ko'] = True
                result.feil = f'API HTTP {response.status_code}. Køen er stoppet; se bevart råsvar. Ingen automatisk nytt forsøk.'
                return result
            data = json.loads(result.raasvar)
            result.sesjon_id = data.get('id') if isinstance(data, dict) else None
            result.modell_rapportert = data.get('model') if isinstance(data, dict) else None
            result.forbruk = {'usage': data.get('usage'), 'merknad': 'API-forbruk rapportert av leverandøren; ikke en kontrollert faktura.'} if isinstance(data, dict) else None
            if isinstance(data, dict):
                info['provider_rapportert'] = data.get('provider') or 'ukjent'
            answer = les_svar(self.navn, data)
            if next(Draft202012Validator(pakke.svarskjema).iter_errors(answer), None):
                raise ValueError('API-svaret følger ikke det registrerte JSON-skjemaet.')
            result.svar = answer
        except asyncio.CancelledError:
            result.avbrutt = True
            result.feil = 'Avbrutt av bruker. Leverandørens behandling og fakturering kan ha fortsatt.'
            info['stopp_ko'] = True
        except (httpx.TimeoutException, TimeoutError):
            result.feil = 'API-tidsavbrudd. Leverandørens behandling og fakturering kan ha fortsatt.'
            info['stopp_ko'] = True
        except httpx.HTTPError:
            result.feil = 'Nettverksfeil under API-kallet. Utfallet hos leverandøren er ukjent; ingen automatisk retry.'
            info['stopp_ko'] = True
        except (ValueError, TypeError, KeyError, AttributeError):
            result.feil = 'Ugyldig, avvist eller ufullstendig API-svar. Se bevart råsvar. Ingen automatisk nytt forsøk.'
            info['stopp_ko'] = True
        except Exception:
            result.feil = 'API-klientfeil. Detaljer som kan inneholde autentisering er utelatt. Ingen automatisk retry.'
            info['stopp_ko'] = True
        finally:
            info['varighet_sek'] = round(time.monotonic() - start, 2)
        return result


class OpenAiApiAdapter(ApiAdapter):
    navn = 'openai_api'
    beskrivelse = 'OpenAI Responses API, egen API-nøkkel og separat betaling.'


class AnthropicApiAdapter(ApiAdapter):
    navn = 'anthropic_api'
    beskrivelse = 'Anthropic Messages API, egen API-nøkkel og separat betaling.'


class OpenRouterApiAdapter(ApiAdapter):
    navn = 'openrouter_api'
    beskrivelse = 'OpenRouter Chat Completions, eksplisitt modell og valgfri leverandør, separat betaling.'


class KompatibelApiAdapter(ApiAdapter):
    navn = 'kompatibel_api'
    beskrivelse = 'OpenAI-kompatibelt Chat Completions API over HTTPS; må støtte valgt JSON-skjema og parametre.'
