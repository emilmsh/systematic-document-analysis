"""Reader discovery with stale PATH, without installing or signing into real CLIs."""
from contextlib import contextmanager
from pathlib import Path
import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from kildeanalyse import cli_paths


@pytest.fixture
def discovery(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path/'local'))
    monkeypatch.setenv('APPDATA', str(tmp_path/'roaming'))
    monkeypatch.setenv('PATH', 'stale-process-path')
    for name in ('claude', 'codex'):
        monkeypatch.delenv(f'SDA_{name.upper()}_BIN', raising=False)
    monkeypatch.setattr(cli_paths.Path, 'home', lambda: tmp_path/'home')
    monkeypatch.setattr(cli_paths, 'windows_path_directories', lambda: [])

    def which(command):
        if not Path(command).is_absolute():
            return None
        for suffix in ('', '.exe', '.cmd'):
            candidate = Path(str(command) + suffix)
            if candidate.is_file():
                return str(candidate)
        return None

    monkeypatch.setattr(cli_paths.shutil, 'which', which)
    return tmp_path


def executable(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'fake executable, never launched')
    return str(path)


@pytest.mark.parametrize('name', ['claude', 'codex'])
def test_new_persisted_path_found_without_changing_process_path(discovery, monkeypatch, name):
    target = discovery/'new CLI location'/f'{name}.exe'
    executable(target)
    monkeypatch.setattr(cli_paths, 'windows_path_directories', lambda: [str(target.parent)])
    assert cli_paths.find_cli(name) == str(target)
    assert cli_paths.os.environ['PATH'] == 'stale-process-path'


def test_child_path_refresh_preserves_parent_and_existing_precedence(discovery, monkeypatch):
    monkeypatch.setattr(cli_paths, 'windows_path_directories', lambda: ['existing', str(discovery/'new Node runtime')])
    parent = {'PATH': 'existing', 'KEEP': 'value'}
    child = cli_paths.execution_env(parent)
    assert parent == {'PATH': 'existing', 'KEEP': 'value'}
    assert child['PATH'].split(cli_paths.os.pathsep) == ['existing', str(discovery/'new Node runtime')]
    assert child['KEEP'] == 'value'


@pytest.mark.parametrize('name,package', [('claude', 'Anthropic.ClaudeCode'), ('codex', 'OpenAI.Codex')])
@pytest.mark.parametrize('nested', ['', 'bin'])
def test_winget_package_without_path_or_link(discovery, name, package, nested):
    target = discovery/'local/Microsoft/WinGet/Packages'/f'{package}_test'/nested/f'{name}.exe'
    executable(target)
    assert cli_paths.find_cli(name) == str(target)


def test_unrelated_winget_package_is_not_used(discovery):
    executable(discovery/'local/Microsoft/WinGet/Packages/Other.Package_test/claude.exe')
    assert cli_paths.find_cli('claude') == 'claude'


def test_override_and_process_path_keep_precedence(discovery, monkeypatch):
    monkeypatch.setenv('SDA_CLAUDE_BIN', 'explicit-command')
    monkeypatch.setattr(cli_paths.shutil, 'which', lambda name: 'process-command')
    assert cli_paths.find_cli('claude') == 'explicit-command'
    monkeypatch.delenv('SDA_CLAUDE_BIN')
    assert cli_paths.find_cli('claude') == 'process-command'


@pytest.mark.parametrize('name', ['claude', 'codex'])
def test_npm_shim_found_without_path(discovery, name):
    target = discovery/'roaming/npm'/f'{name}.cmd'
    executable(target)
    assert cli_paths.find_cli(name) == str(target)


@pytest.mark.parametrize('denied', [None, 'machine', 'user'])
def test_registry_path_read_is_fresh_expanded_and_read_only(tmp_path, monkeypatch, denied):
    values = {'machine': f';relative;"{tmp_path}/machine"',
              'user': '%SDA_TEST_ROOT%/user;%SDA_TEST_ROOT%/user'}

    @contextmanager
    def open_key(hive, key):
        if hive == denied:
            raise PermissionError('Unavailable hive')
        yield hive

    fake = SimpleNamespace(HKEY_LOCAL_MACHINE='machine', HKEY_CURRENT_USER='user',
                           OpenKey=open_key, QueryValueEx=lambda hive, name: (values[hive], 2))
    monkeypatch.setitem(sys.modules, 'winreg', fake)
    monkeypatch.setenv('SDA_TEST_ROOT', str(tmp_path))
    expected = [str(tmp_path)+'/machine'] if denied != 'machine' else []
    if denied != 'user':
        expected.append(str(tmp_path)+'/user')
    assert cli_paths.windows_path_directories() == expected
    if denied != 'user':
        values['user'] = str(tmp_path/'changed')
        assert cli_paths.windows_path_directories()[-1] == str(tmp_path/'changed')


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows installer')
def test_winget_install_immediately_finds_cli_and_reuses_signin(discovery, monkeypatch, capsys):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'bin'))
    import setup_reader

    target = discovery/'local/Microsoft/WinGet/Packages/Anthropic.ClaudeCode_test/claude.exe'
    commands = []

    def run(command, **kwargs):
        commands.append(command)
        if command[0] == 'winget':
            executable(target)
        else:
            assert command[0] == str(target)
            assert command[1:] in (['--version'], ['auth', 'status'])
        return subprocess.CompletedProcess(command, 0, json.dumps({
            'loggedIn': True, 'authMethod': 'claude.ai', 'apiProvider': 'firstParty'}), '')

    monkeypatch.setattr(setup_reader.subprocess, 'run', run)
    setup_reader.setup('claude', allow_login=False)
    assert len(commands) == 3
    output = capsys.readouterr().out
    assert str(target) in output and 'existing subscription sign-in confirmed' in output
    # The worker uses the same lookup and can find it with the original stale PATH.
    from kildeanalyse.adaptere.claude_cli import ClaudeCliAdapter
    assert ClaudeCliAdapter()._bin() == str(target)
