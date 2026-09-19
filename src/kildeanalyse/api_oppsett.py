"""Offentlige API-valg. Nøkler leses først ved kjøring, aldri inn i planen."""
from urllib.parse import urlsplit
import os

API_MOTORER = {
    'openai_api': ('https://api.openai.com/v1', 'OPENAI_API_KEY', 'responses'),
    'anthropic_api': ('https://api.anthropic.com/v1', 'ANTHROPIC_API_KEY', 'messages'),
    'openrouter_api': ('https://openrouter.ai/api/v1', 'OPENROUTER_API_KEY', 'chat/completions'),
    'kompatibel_api': ('', 'SDA_CUSTOM_API_KEY', 'chat/completions'),
}
API_ENV = tuple(item[1] for item in API_MOTORER.values()) + ('OE_KILDEANALYSE_CUSTOM_API_KEY',)
API_FELT = {'tenkenivaa', 'tidsavbrudd_sek', 'maks_output_tokens', 'base_url', 'provider'}


def local_key(motor):
    key = os.environ.get(API_MOTORER[motor][1], '').strip()
    if not key and motor == 'kompatibel_api':
        key = os.environ.get('OE_KILDEANALYSE_CUSTOM_API_KEY', '').strip()
    return key


def api_valg(motor, valg):
    """Normaliser bare tillatte, ikke-hemmelige parametre før lagring."""
    if set(valg) - API_FELT:
        raise ValueError('Ukjent API-innstilling. Nøkler, headers og vilkårlige request-felt skal ikke inn i planen.')
    base, key_env, path = API_MOTORER[motor]
    if motor == 'kompatibel_api':
        base = valg.get('base_url', '')
        if not isinstance(base, str):
            raise ValueError('base_url må være en HTTPS-adresse.')
        parts = urlsplit(base)
        if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
                or parts.query or parts.fragment or any(c.isspace() for c in base)):
            raise ValueError('Kompatibel API krever eksplisitt HTTPS base_url uten innlogging, query eller fragment.')
    elif 'base_url' in valg and valg['base_url'] != base:
        raise ValueError('Fast leverandøradresse kan ikke overstyres. Bruk kompatibel_api for en annen leverandør.')
    maximum = valg.get('maks_output_tokens', 16384)
    if type(maximum) is not int or not 1 <= maximum <= 1000000:
        raise ValueError('maks_output_tokens må være et heltall mellom 1 og 1000000.')
    provider = valg.get('provider', '')
    if not isinstance(provider, str) or (provider and (motor != 'openrouter_api' or len(provider) > 100)):
        raise ValueError('provider kan bare brukes som et leverandørnavn for OpenRouter.')
    result = dict(valg, base_url=base.rstrip('/'), maks_output_tokens=maximum)
    if provider:
        result['provider'] = provider
    return result


def api_metadata(motor, valg):
    base, key_env, path = API_MOTORER[motor]
    return {'endpoint': valg.get('base_url', base).rstrip('/') + '/' + path,
            'nokkelvariabel': key_env, 'maks_output_tokens': valg.get('maks_output_tokens', 16384),
            'provider': valg.get('provider') or ('automatisk valg hos OpenRouter' if motor == 'openrouter_api' else motor),
            'betaling': 'separat API-forbruk', 'harness': 'direkte API, ett kall, ingen verktøy eller automatisk nytt forsøk'}
