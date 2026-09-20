import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bin'))
from pakk_plugin import pakk, pakkefiler
from installer import prepare


def test_felles_pakke_uten_maskinstier_og_byggemetadata(tmp_path):
    target=tmp_path/'systematic-document-analysis'
    pakk(target)
    (target/'build').mkdir()
    (target/'build'/'ikke_del.txt').write_text('generert')
    files=pakkefiler(target)
    assert target/'installer.cmd' in files
    assert not any('build' in p.relative_to(target).parts for p in files)
    assert str(Path.home()) not in (target/'.mcp.json').read_text(encoding='utf-8')
    assert (target/'START_HER.md').is_file()


def test_installer_forbereder_begge_verter_separat(tmp_path):
    claude=prepare('claude',tmp_path)
    codex=prepare('codex',tmp_path)
    a=json.loads((claude/'.mcp.json').read_text(encoding='utf-8'))['mcpServers']['document_analysis']
    b=json.loads((codex/'.mcp.json').read_text(encoding='utf-8'))['mcpServers']['document_analysis']
    assert a['command']=='cmd' and '${CLAUDE_PLUGIN_ROOT}' in a['args'][-1]
    assert b['args'][-1]==str(codex/'bin/start_server.py')
    assert Path(b['command']).is_absolute()
    assert 'SDA_DATA' in b['env_vars']
    assert (claude/'src/kildeanalyse/parametre.py').read_bytes()==(codex/'src/kildeanalyse/parametre.py').read_bytes()
