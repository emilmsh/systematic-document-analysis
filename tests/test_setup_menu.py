"""The public launcher must route operations without swallowing failures or arguments."""
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'bin'))
import manage


@pytest.mark.parametrize('args,script,forwarded', [
    (['install','both','--skip-ocr'], 'installer.py', ['both','--skip-ocr']),
    (['codex','--non-interactive'], 'installer.py', ['codex','--non-interactive']),
    (['repair','claude'], 'installer.py', ['claude','--repair']),
    (['recover','codex'], 'installer.py', ['codex','--recover']),
    (['reader','claude','--login'], 'setup_reader.py', ['claude','--login']),
    (['ocr'], 'setup_ocr.py', []),
    (['settings'], 'configure_keys.py', []),
    (['update','--mode','notify'], 'update_plugin.py', ['--mode','notify']),
])
def test_dispatch_preserves_arguments_and_exit_status(monkeypatch,args,script,forwarded):
    calls = []
    monkeypatch.setattr(manage.subprocess, 'run', lambda cmd: calls.append(cmd) or SimpleNamespace(returncode=7))
    assert manage.main(args) == 7
    assert calls == [[sys.executable,'-X','utf8',str(manage.ROOT/script),*forwarded]]


def test_menu_reprompts_and_routes_reader_setup(monkeypatch):
    choices = iter(['bad','3'])
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
    monkeypatch.setattr('builtins.input', lambda _: next(choices))
    calls = []
    monkeypatch.setattr(manage.subprocess, 'run', lambda cmd: calls.append(cmd) or SimpleNamespace(returncode=0))
    assert manage.main([]) == 0
    assert Path(calls[0][-1]).name == 'setup_reader.py'


def test_no_input_and_help_never_launch_setup(monkeypatch):
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)
    monkeypatch.setattr(manage.subprocess, 'run', lambda _: pytest.fail('Unexpected setup'))
    assert manage.main([]) == 2
    assert manage.main(['--help']) == 0
    assert manage.main(['settings','unexpected']) == 2
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
    monkeypatch.setattr('builtins.input', lambda _: '0')
    assert manage.main([]) == 0
