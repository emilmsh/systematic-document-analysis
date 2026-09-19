"""Lag en liten plugin-kopi uten venv, cache eller analysedata.

Bruk: python bin/pakk_plugin.py <mappe>/oe-kildeanalyse
Målkatalogen er en distribusjonskopi; navngitte pakkefiler oppdateres der.
"""
import argparse
from pathlib import Path
import shutil
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
FILER=('pyproject.toml','.mcp.json','oppsett.cmd','installer.cmd','README.md','START_HER.md','UTVIKLINGSSTRATEGI.md','tests/TESTLOGG.md',
       'eksempler/arsrapporter-2024/kilder.json','eksempler/arsrapporter-2024/STARTPROMPT.md')
MAPPER=('.codex-plugin','.claude-plugin','bin','skills','src/kildeanalyse','tests/fixtures/syntetisk')

def pakkefiler(root=ROOT):
    """Eksplisitt filliste, også etter at pip har lagt byggemetadata i mappen."""
    files = [root/name for name in FILER]
    for name in MAPPER:
        files.extend(p for p in (root/name).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix != '.pyc')
    return sorted(files)

def pakk(maal, codex=False):
    maal=Path(maal).resolve()
    if maal==ROOT or maal.name!='oe-kildeanalyse':
        raise ValueError('Bruk en separat målmappe med navnet oe-kildeanalyse.')
    maal.mkdir(parents=True,exist_ok=True)
    for name in FILER:
        target=maal/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/name,target)
    for name in MAPPER:
        shutil.copytree(ROOT/name,maal/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    if codex:
        # Lokal Codex-installasjon med eksplisitt Python og plugin-kopi.
        # Den personlige kildekopien må beholdes etter installasjon.
        config = {'mcpServers': {'kildeanalyse': {
            'command': sys._base_executable,
            'args': ['-X', 'utf8', str(maal/'bin'/'start_server.py')],
            'env': {'PYTHONUTF8': '1'},
            'env_vars': ['OE_KILDEANALYSE_DATA', 'CODEX_HOME', 'OE_KILDEANALYSE_CODEX_BIN',
                         'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'OPENROUTER_API_KEY', 'OE_KILDEANALYSE_CUSTOM_API_KEY'],
            'startup_timeout_sec': 120,
        }}}
        (maal/'.mcp.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Plugin-kopi: {maal}')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mappe',type=Path)
    parser.add_argument('--codex',action='store_true',help='Skriv lokal Codex-oppstart med absolutte stier')
    args=parser.parse_args()
    pakk(args.mappe,args.codex)
