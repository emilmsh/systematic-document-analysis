"""One-window onboarding without touching real accounts, browsers or host profiles."""
from contextlib import contextmanager
import io
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
import installer
import setup_reader


@pytest.fixture
def cli(monkeypatch):
    calls = []
    replies = []
    monkeypatch.setattr(setup_reader, 'install', lambda name: f'{name}.exe')

    def run(command, **kwargs):
        calls.append((command, kwargs))
        if command[1:] in (['auth', 'status'], ['login', 'status']):
            reply = replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            code, stdout, stderr = reply
            return subprocess.CompletedProcess(command, code, stdout, stderr)
        return subprocess.CompletedProcess(command, 0, '', '')

    monkeypatch.setattr(setup_reader.subprocess, 'run', run)
    return calls, replies


def authenticated(name):
    if name == 'claude':
        return (0, json.dumps({'loggedIn': True, 'authMethod': 'claude.ai',
                               'apiProvider': 'firstParty', 'email': 'private@example.test'}), '')
    # Codex reports sign-in to stderr.
    return (0, '', 'Logged in using ChatGPT')


def logins(calls):
    return [command for command, _ in calls if command[1:] in (['auth', 'login'], ['login'])]


def test_both_readers_reuse_existing_signins(cli):
    calls, replies = cli
    replies.extend([authenticated('codex'), authenticated('claude')])
    setup_reader.setup('both')
    assert not replies and not logins(calls)
    assert {command[0] for command, _ in calls} == {'codex.exe', 'claude.exe'}


def test_both_readers_sign_in_and_verify_separately(cli):
    calls, replies = cli
    replies.extend([(1, '', ''), authenticated('codex'), (1, '', ''), authenticated('claude')])
    setup_reader.setup('both')
    assert logins(calls) == [['codex.exe', 'login'], ['claude.exe', 'auth', 'login']]
    assert not replies


def test_both_noninteractive_continues_other_reader_without_browser(cli, capsys):
    calls, replies = cli
    replies.extend([(1, '', ''), authenticated('claude')])
    with pytest.raises(RuntimeError, match='Successful sign-ins are kept'):
        setup_reader.setup('both', allow_login=False)
    assert not replies and not logins(calls)
    assert 'claude: existing subscription sign-in confirmed' in capsys.readouterr().out


def test_both_install_failure_still_checks_other_reader(cli, monkeypatch):
    calls, replies = cli
    def install(name):
        if name == 'codex':
            raise OSError('test installation failure')
        return 'claude.exe'
    monkeypatch.setattr(setup_reader, 'install', install)
    replies.append(authenticated('claude'))
    with pytest.raises(RuntimeError, match='test installation failure'):
        setup_reader.setup('both')
    assert not replies and not logins(calls)


def test_both_cancel_stops_before_second_reader(cli, monkeypatch):
    installed = []
    def install(name):
        installed.append(name)
        raise KeyboardInterrupt()
    monkeypatch.setattr(setup_reader, 'install', install)
    with pytest.raises(KeyboardInterrupt):
        setup_reader.setup('both')
    assert installed == ['codex']


@pytest.mark.parametrize('name', ['claude', 'codex'])
def test_existing_subscription_never_opens_login(cli, capsys, name):
    calls, replies = cli
    replies.append(authenticated(name))
    setup_reader.setup(name)
    assert not logins(calls)
    assert 'existing subscription sign-in confirmed' in capsys.readouterr().out


@pytest.mark.parametrize('name', ['claude', 'codex'])
def test_new_user_logs_in_once_and_is_verified(cli, monkeypatch, capsys, name):
    calls, replies = cli
    replies.extend([(1, '', 'Not logged in'), authenticated(name)])
    for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'CLAUDE_CODE_OAUTH_TOKEN',
                'CLAUDE_CODE_USE_BEDROCK', 'CODEX_ACCESS_TOKEN'):
        monkeypatch.setenv(key, 'private-secret')
    setup_reader.setup(name)
    assert len(logins(calls)) == 1 and not replies
    assert calls[-1][0][1:] in (['auth', 'status'], ['login', 'status'])
    assert all('private-secret' not in options['env'].values() for _, options in calls)
    output = capsys.readouterr().out
    assert 'sign-in verified' in output and 'private@example.test' not in output


@pytest.mark.parametrize('name,reply', [
    ('claude', (0, '{"loggedIn":true,"authMethod":"api_key","apiProvider":"firstParty"}', '')),
    ('claude', (0, '{"loggedIn":true,"authMethod":"claude.ai","apiProvider":"bedrock"}', '')),
    ('claude', (0, '[]', '')),
    ('codex', (0, '', 'Logged in using an API key: private-secret')),
    ('codex', (1, '', 'Logged in using ChatGPT')),
])
def test_noninteractive_rejects_missing_or_wrong_auth_without_login(cli, name, reply):
    calls, replies = cli
    replies.append(reply)
    with pytest.raises(RuntimeError, match='subscription sign-in is not confirmed') as error:
        setup_reader.setup(name, allow_login=False)
    assert not logins(calls) and 'private-secret' not in str(error.value)


@pytest.mark.parametrize('name', ['claude', 'codex'])
def test_successful_login_exit_without_subscription_is_not_success(cli, capsys, name):
    calls, replies = cli
    replies.extend([(1, '', ''), (1, '', '')])
    with pytest.raises(RuntimeError, match='could not be verified after login'):
        setup_reader.setup(name)
    assert len(logins(calls)) == 1
    assert 'sign-in verified' not in capsys.readouterr().out


@pytest.mark.parametrize('reply', [(0, 'private-secret invalid json', ''),
                                 subprocess.TimeoutExpired('auth status', 20, output='private-secret')])
def test_unreadable_or_timed_out_status_is_private_and_does_not_launch_login(cli, reply):
    calls, replies = cli
    replies.append(reply)
    with pytest.raises(RuntimeError) as error:
        setup_reader.setup('claude')
    assert 'private-secret' not in str(error.value) and not logins(calls)


def test_explicit_helper_login_can_switch_accounts(cli, monkeypatch):
    calls, replies = cli
    replies.append(authenticated('claude'))
    monkeypatch.setattr(sys, 'argv', ['setup_reader.py', 'claude', '--login'])
    setup_reader.main()
    assert len(logins(calls)) == 1 and not replies


def test_double_clicked_helper_reuses_subscription(cli, monkeypatch):
    calls, replies = cli
    replies.append(authenticated('claude'))
    monkeypatch.setattr(sys, 'argv', ['setup_reader.py'])
    monkeypatch.setattr('builtins.input', lambda prompt: '2')
    setup_reader.main()
    assert not logins(calls) and not replies


def test_failed_login_process_does_not_claim_success(cli, monkeypatch, capsys):
    calls, replies = cli
    replies.append((1, '', 'Not logged in'))
    original = setup_reader.subprocess.run

    def fail_login(command, **kwargs):
        if command[1:] == ['auth', 'login']:
            raise subprocess.CalledProcessError(1, command, output='private-secret')
        return original(command, **kwargs)

    monkeypatch.setattr(setup_reader.subprocess, 'run', fail_login)
    with pytest.raises(RuntimeError, match='sign-in did not complete') as error:
        setup_reader.setup('claude')
    assert 'private-secret' not in str(error.value)
    assert 'sign-in verified' not in capsys.readouterr().out


@pytest.fixture
def main_setup(monkeypatch, tmp_path):
    state = {'locked': False, 'installs': [], 'readers': [], 'updates': [], 'ocr': 0}
    monkeypatch.setattr(sys, 'stdin', type('Terminal', (io.StringIO,), {'isatty': lambda self: True})())
    monkeypatch.setattr(sys, 'argv', ['installer.py', 'claude', '--base-dir', str(tmp_path / 'installed')])
    monkeypatch.setattr(installer, 'packaged_process', lambda: False)

    @contextmanager
    def lock(**kwargs):
        state['locked'] = True
        try:
            yield
        finally:
            state['locked'] = False

    def install(host, base, **kwargs):
        assert state['locked']
        state['installs'].append(host)
        (base / host).mkdir(parents=True)
        return state.get('result', 'installed')

    def reader(name, **kwargs):
        assert not state['locked'], 'Browser login must not hold the installation lock'
        state['readers'].append((name, kwargs))
        if 'reader_error' in state:
            raise state['reader_error']

    monkeypatch.setattr(installer, 'installation_lock', lock)
    monkeypatch.setattr(installer, 'install', install)
    monkeypatch.setattr(installer, 'setup_subscription_reader', reader)
    def update(name):
        assert not state['locked'], 'CLI updates must not hold the installation lock'
        state['updates'].append(name)
        if 'update_error' in state:
            raise state['update_error']
    monkeypatch.setattr(installer, 'update_subscription_readers', update)
    def ocr_setup():
        assert not state['locked']
        state['ocr'] += 1
        if 'ocr_error' in state:
            raise state['ocr_error']
    monkeypatch.setattr(installer, 'setup_local_ocr', ocr_setup)
    return state


@pytest.mark.parametrize('result', ['installed', 'already up to date'])
def test_interactive_install_selects_independent_reader_after_unlock(main_setup, monkeypatch, result):
    main_setup['result'] = result
    choices = iter(['invalid', '1', 'n'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(choices))
    assert installer.main() == 0
    assert main_setup['installs'] == ['claude']
    assert main_setup['readers'] == [('codex', {'allow_login': True})]


def test_double_click_both_hosts_asks_for_reader_only_once(main_setup, monkeypatch):
    monkeypatch.setattr(sys, 'argv', [sys.argv[0], *sys.argv[2:]])
    choices = iter(['3', '2', 'n'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(choices))
    assert installer.main() == 0
    assert main_setup['installs'] == ['claude', 'codex']
    assert main_setup['readers'] == [('claude', {'allow_login': True})]


def test_redirected_input_never_opens_login(main_setup, monkeypatch):
    monkeypatch.setattr(sys, 'stdin', io.StringIO())
    monkeypatch.setattr(sys, 'argv', sys.argv + ['--reader', 'claude'])
    monkeypatch.setattr('builtins.input', lambda prompt: pytest.fail('Unexpected prompt'))
    assert installer.main() == 0
    assert main_setup['readers'] == [('claude', {'allow_login': False})]


@pytest.mark.parametrize('flags,choice,expected', [
    ([], '4', []),
    ([], '3', [('both', {'allow_login': True})]),
    (['--reader', 'none'], None, []),
    (['--non-interactive'], None, []),
    (['--reader', 'claude', '--non-interactive'], None, [('claude', {'allow_login': False})]),
    (['--reader', 'codex'], None, [('codex', {'allow_login': True})]),
    (['--reader', 'both', '--non-interactive'], None, [('both', {'allow_login': False})]),
])
def test_skip_and_explicit_or_noninteractive_reader(main_setup, monkeypatch, flags, choice, expected):
    monkeypatch.setattr(sys, 'argv', sys.argv + flags)
    replies = iter([choice, 'n'])
    def choose(prompt):
        assert choice is not None, 'Must not prompt in this mode'
        return next(replies)
    monkeypatch.setattr('builtins.input', choose)
    assert installer.main() == 0
    assert main_setup['readers'] == expected


def test_menu_install_offers_reader_update_after_signin(main_setup, monkeypatch):
    choices = iter(['3', 'invalid', 'ja'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(choices))
    assert installer.main() == 0
    assert main_setup['readers'] == [('both', {'allow_login': True})]
    assert main_setup['updates'] == ['both']


def test_declined_update_leaves_reader_versions_untouched(main_setup, monkeypatch):
    choices = iter(['1', ''])
    monkeypatch.setattr('builtins.input', lambda prompt: next(choices))
    assert installer.main() == 0
    assert main_setup['updates'] == []


def test_update_failure_reports_manual_retry_without_undoing_install(main_setup, monkeypatch, tmp_path, capsys):
    main_setup['update_error'] = RuntimeError('release lookup failed')
    choices = iter(['2', 'y'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(choices))
    assert installer.main() == 1
    assert (tmp_path / 'installed' / 'claude').is_dir()
    assert main_setup['updates'] == ['claude']
    assert 'installer.cmd reader claude --update' in capsys.readouterr().err


@pytest.mark.parametrize('error', [RuntimeError('Sign-in failed'), KeyboardInterrupt(), EOFError()])
def test_reader_failure_keeps_installed_plugin_and_prints_recovery(main_setup, monkeypatch, tmp_path, capsys, error):
    main_setup['reader_error'] = error
    monkeypatch.setattr(sys, 'argv', sys.argv + ['--reader', 'claude'])
    assert installer.main() == 1
    assert (tmp_path / 'installed' / 'claude').is_dir()
    assert 'reader setup is incomplete' in capsys.readouterr().err


@pytest.mark.parametrize('mode', ['--recover', '--prepare-only', 'kept disabled installation', 'failure'])
def test_recovery_preparation_and_unsuccessful_install_do_not_setup_reader(main_setup, monkeypatch, mode):
    monkeypatch.setattr('builtins.input', lambda prompt: pytest.fail('Unexpected reader prompt'))
    if mode.startswith('--'):
        monkeypatch.setattr(sys, 'argv', sys.argv + [mode])
        monkeypatch.setattr(installer, 'recover', lambda *args, **kwargs: 'recovered')
        monkeypatch.setattr(installer, 'prepare', lambda *args: 'prepared')
    elif mode == 'failure':
        def fail(*args, **kwargs):
            raise RuntimeError('Registration failed')
        monkeypatch.setattr(installer, 'install', fail)
    else:
        main_setup['result'] = mode
    assert installer.main() == (1 if mode == 'failure' else 0)
    assert main_setup['readers'] == []
    assert main_setup['ocr'] == 0


def test_ocr_is_default_even_when_reader_is_skipped(main_setup, monkeypatch):
    monkeypatch.setattr(sys, 'argv', sys.argv + ['--reader', 'none'])
    assert installer.main() == 0
    assert main_setup['ocr'] == 1


def test_ocr_failure_preserves_plugin_and_still_finishes_reader(main_setup, monkeypatch, capsys):
    main_setup['ocr_error'] = RuntimeError('OCR installation failed')
    monkeypatch.setattr(sys, 'argv', sys.argv + ['--reader', 'claude'])
    assert installer.main() == 1
    assert main_setup['installs'] == ['claude'] and main_setup['readers']
    assert 'OCR setup is incomplete' in capsys.readouterr().err


def test_explicit_ocr_skip(main_setup, monkeypatch):
    monkeypatch.setattr(sys, 'argv', sys.argv + ['--reader', 'none', '--skip-ocr'])
    assert installer.main() == 0
    assert main_setup['ocr'] == 0
