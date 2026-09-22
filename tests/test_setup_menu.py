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
    choices = iter(['bad','2','1','0'])
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
    monkeypatch.setattr('builtins.input', lambda _: next(choices))
    calls = []
    monkeypatch.setattr(manage.subprocess, 'run', lambda cmd: calls.append(cmd) or SimpleNamespace(returncode=0))
    assert manage.main([]) == 0
    assert Path(calls[0][-1]).name == 'setup_reader.py'


def test_back_returns_to_main_menu_without_running_an_action(monkeypatch, capsys):
    choices = iter(['2','0','3','0','0'])
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
    monkeypatch.setattr('builtins.input', lambda _: next(choices))
    monkeypatch.setattr(manage.subprocess, 'run', lambda _: pytest.fail('Back must not run setup'))
    assert manage.main([]) == 0
    output = capsys.readouterr().out
    assert output.count('Systematic Document Analysis') == 3
    assert '0 = Back / Tilbake' in output


def test_maintenance_can_repair_ocr_without_reinstalling_plugin(monkeypatch):
    choices = iter(['3','3','0'])
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
    monkeypatch.setattr('builtins.input', lambda _: next(choices))
    calls = []
    monkeypatch.setattr(manage.subprocess, 'run', lambda cmd: calls.append(cmd) or SimpleNamespace(returncode=1))
    assert manage.main([]) == 1
    assert calls == [[sys.executable,'-X','utf8',str(manage.ROOT/'setup_ocr.py')]]


@pytest.mark.parametrize('first_status', [0, 7])
def test_return_to_start_runs_another_action_and_preserves_failures(monkeypatch, first_status):
    choices = iter(['2','1','1','2','2','1','0'])
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
    monkeypatch.setattr('builtins.input', lambda _: next(choices))
    calls = []
    def run(cmd):
        calls.append(cmd)
        return SimpleNamespace(returncode=first_status if len(calls) == 1 else 0)
    monkeypatch.setattr(manage.subprocess, 'run', run)
    assert manage.main([]) == first_status
    assert [Path(cmd[-1]).name for cmd in calls] == ['setup_reader.py', 'configure_keys.py']


def test_no_input_and_help_never_launch_setup(monkeypatch):
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)
    monkeypatch.setattr(manage.subprocess, 'run', lambda _: pytest.fail('Unexpected setup'))
    assert manage.main([]) == 2
    assert manage.main(['--help']) == 0
    assert manage.main(['settings','unexpected']) == 2
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
    monkeypatch.setattr('builtins.input', lambda _: '0')
    assert manage.main([]) == 0
