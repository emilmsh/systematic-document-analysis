"""Lag en liten plugin-kopi uten venv, cache eller analysedata.

Bruk: python bin/pakk_plugin.py <mappe>/systematic-document-analysis
Målkatalogen er en distribusjonskopi; navngitte pakkefiler oppdateres der.
"""
import argparse
from pathlib import Path
import shutil
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
FILER=('pyproject.toml','.mcp.json','installer.cmd','README.md','LICENSE',
       'docs/USAGE.md','docs/USAGE.no.md','docs/UPDATES.md','docs/SETUP_AND_SHARING.md',
       'docs/DOCUMENT_PROCESSING.md','docs/SOURCE_FORMATS.md','docs/PROJECT_FILES.md',
       'docs/providers.env.example','docs/TASKS.md','docs/CORE_REDESIGN.md',
       'bin/manage.py','bin/installer.py','bin/pakk_plugin.py','bin/launch.ps1',
       'bin/setup_reader.py','bin/setup_ocr.py','bin/configure_keys.py',
       'bin/update_plugin.py','bin/start_server.py','bin/start_server.cmd')
MAPPER=('.codex-plugin','.claude-plugin','skills','src/kildeanalyse','assets')

def pakkefiler(root=ROOT):
    """Eksplisitt filliste, også etter at pip har lagt byggemetadata i mappen."""
    files = [root/name for name in FILER]
    for name in MAPPER:
        files.extend(p for p in (root/name).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and p.suffix != '.pyc')
    return sorted(files)

def pakk(maal, codex=False, root=ROOT):
    maal=Path(maal).resolve()
    if maal==root or maal.name!='systematic-document-analysis':
        raise ValueError('Bruk en separat målmappe med navnet systematic-document-analysis.')
    maal.mkdir(parents=True,exist_ok=True)
    for source in pakkefiler(root):
        target=maal/source.relative_to(root)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
    if codex:
        configure_codex(maal)
    print(f'Plugin copy: {maal}')


def configure_codex(maal, launch_root=None):
    maal = Path(maal)
    launch_root = Path(launch_root or maal)
    # Lokal Codex-installasjon med eksplisitt Python og plugin-kopi.
    # Den personlige kildekopien må beholdes etter installasjon.
    config = {'mcpServers': {'document_analysis': {
        'command': sys._base_executable,
        'args': ['-X', 'utf8', str(launch_root/'bin'/'start_server.py')],
        'env': {'PYTHONUTF8': '1'},
        'env_vars': ['SDA_DATA', 'SDA_PROJECTS_ROOT', 'CODEX_HOME', 'SDA_CODEX_BIN', 'SDA_CLAUDE_BIN', 'SDA_TESSERACT_BIN', 'SDA_SETTINGS_DIR', 'SDA_MAINTENANCE_DIR',
                     'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'OPENROUTER_API_KEY', 'AZURE_AI_API_KEY', 'SDA_CUSTOM_API_KEY'],
        'startup_timeout_sec': 300,
    }}}
    (maal/'.mcp.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mappe',type=Path)
    parser.add_argument('--codex',action='store_true',help='Skriv lokal Codex-oppstart med absolutte stier')
    args=parser.parse_args()
    pakk(args.mappe,args.codex)
