"""Offentlige API-valg. Nøkler leses først ved kjøring, aldri inn i planen."""
from urllib.parse import urlsplit
import os

API_MOTORER = {
    'openai_api': ('https://api.openai.com/v1', 'OPENAI_API_KEY', 'responses'),
    'azure_foundry_api': ('', 'AZURE_AI_API_KEY', 'responses'),
    'anthropic_api': ('https://api.anthropic.com/v1', 'ANTHROPIC_API_KEY', 'messages'),
    'openrouter_api': ('https://openrouter.ai/api/v1', 'OPENROUTER_API_KEY', 'chat/completions'),
    'kompatibel_api': ('', 'SDA_CUSTOM_API_KEY', 'chat/completions'),
}
API_ENV = tuple(item[1] for item in API_MOTORER.values())
API_FELT = {'tenkenivaa', 'tidsavbrudd_sek', 'maks_output_tokens', 'base_url', 'provider', 'api_format',
            'input_budget_bytes', 'maks_samtidige'}


def local_key(motor):
    from .credentials import get_key
    return get_key(API_MOTORER[motor][1])


AZURE_FORMATS = {'responses': ('openai_api', 'responses'),
                 'chat_completions': ('kompatibel_api', 'chat/completions'),
                 'anthropic_messages': ('anthropic_api', 'messages')}


def wire_engine(motor, valg):
    if motor != 'azure_foundry_api':
        return motor
    fmt = valg.get('api_format')
    if not isinstance(fmt, str) or fmt not in AZURE_FORMATS:
        raise ValueError('Azure requires explicit api_format: responses, chat_completions or anthropic_messages.')
    return AZURE_FORMATS[fmt][0]


def azure_base_url(base, api_format):
    wire_engine('azure_foundry_api', {'api_format': api_format})
    anthropic = api_format == 'anthropic_messages'
    suffixes = ('services.ai.azure.com',) if anthropic else ('openai.azure.com', 'services.ai.azure.com')
    path = '/anthropic/v1' if anthropic else '/openai/v1'
    if not isinstance(base, str):
        raise ValueError('Azure requires an HTTPS resource endpoint.')
    parts = urlsplit(base)
    host = parts.hostname or ''
    if (parts.scheme != 'https' or parts.username or parts.password or parts.query or parts.fragment
            or parts.port not in (None, 443) or any(c.isspace() for c in base)
            or not any(host.endswith('.' + suffix) for suffix in suffixes)
            or parts.path.rstrip('/') not in ('', path, '/anthropic' if anthropic else path)):
        raise ValueError('Azure requires an HTTPS resource endpoint matching api_format, not a project endpoint. '
                         'Use services.ai.azure.com for Claude; services.ai.azure.com or openai.azure.com for OpenAI-compatible APIs.')
    return f'https://{host}{path}'


def api_valg(motor, valg):
    """Normaliser bare tillatte, ikke-hemmelige parametre før lagring."""
    if set(valg) - API_FELT:
        raise ValueError('Ukjent API-innstilling. Nøkler, headers og vilkårlige request-felt skal ikke inn i planen.')
    base, key_env, path = API_MOTORER[motor]
    if 'api_format' in valg and motor != 'azure_foundry_api':
        raise ValueError('api_format is only supported for azure_foundry_api.')
    if motor == 'azure_foundry_api':
        base = azure_base_url(valg.get('base_url', ''), valg.get('api_format'))
    elif motor == 'kompatibel_api':
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
    extra = {}
    if motor == 'azure_foundry_api':
        fmt = valg.get('api_format')
        path = AZURE_FORMATS.get(fmt if isinstance(fmt, str) else '', ('', ''))[1]
        extra['api_format'] = fmt
    return {'endpoint': valg.get('base_url', base).rstrip('/') + '/' + path,
            **extra,
            'nokkelvariabel': key_env, 'maks_output_tokens': valg.get('maks_output_tokens', 16384),
            'provider': valg.get('provider') or ('automatisk valg hos OpenRouter' if motor == 'openrouter_api' else motor),
            'betaling': 'separat API-forbruk', 'harness': 'one independent API request per file, no model tools or automatic retries'}
