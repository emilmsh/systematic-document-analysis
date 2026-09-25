import importlib.util
import json
import re
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
    assert {p.name for p in target.iterdir() if p.is_file()} == {
        'installer.cmd', 'README.md', 'LICENSE', 'pyproject.toml', '.mcp.json'}
    assert not any((target/name).exists() for name in (
        'tests', 'examples', 'eksempler', 'DEVELOPMENT.md',
        'oppsett.cmd', 'reader_setup.cmd', 'ocr_setup.cmd', 'settings.cmd', 'update.cmd',
        'bin/build_examples.py', 'bin/hent_arsrapporter.py', 'bin/lag_release.py'))


def test_compact_package_can_repackage_itself_and_has_no_broken_guide_links(tmp_path):
    first = tmp_path/'first/systematic-document-analysis'
    second = tmp_path/'second/systematic-document-analysis'
    pakk(first)
    pakk(second, root=first)
    assert {p.relative_to(first): p.read_bytes() for p in pakkefiler(first)} == {
        p.relative_to(second): p.read_bytes() for p in pakkefiler(second)}
    for guide in [first/'README.md', *first.joinpath('docs').glob('*.md')]:
        for link in re.findall(r'\]\(([^)]+)\)', guide.read_text(encoding='utf-8')):
            if '://' in link or link.startswith('#'):
                continue
            assert (guide.parent/link.split('#')[0]).exists(), (guide.name, link)


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
