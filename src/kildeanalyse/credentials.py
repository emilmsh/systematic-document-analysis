"""Optional local key file. Never export values or copy them into subprocess environments."""
import os
from pathlib import Path

NAMES = ('OPENAI_API_KEY','ANTHROPIC_API_KEY','OPENROUTER_API_KEY','SDA_CUSTOM_API_KEY')
TEMPLATE = '''# Private API settings for Systematic Document Analysis.
# Optional: fill only the provider(s) you use. Subscription CLI readers need no keys.
# Paste after =, save, then close this file. Never share this completed file or paste it into chat.
# Plain text on this computer; not an encrypted vault. Keep it outside projects/cloud sync.
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
OPENROUTER_API_KEY=
SDA_CUSTOM_API_KEY=
'''


def settings_path():
    base = Path(os.environ.get('SDA_SETTINGS_DIR') or
                Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local/share'))/'systematic-document-analysis/settings')
    return base/'providers.env'


def file_values():
    path = settings_path()
    if not path.is_file():
        return {}
    if path.stat().st_size > 65536:
        raise ValueError('API settings file is too large. Open settings.cmd to correct it.')
    result = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        name, sep, value = line.partition('=')
        name, value = name.strip(), value.strip()
        if not sep or name not in NAMES or name in result:
            raise ValueError('Invalid API settings entry. Only the four provided key names are allowed; values are not displayed.')
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        result[name] = value
    return result


def get_key(name):
    return os.environ.get(name,'').strip() or file_values().get(name,'').strip()


def prepare_file():
    path = settings_path()
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open('x',encoding='utf-8') as f:
            f.write(TEMPLATE)
    except FileExistsError:
        pass  # Never replace a user's existing keys.
    return path
