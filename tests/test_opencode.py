import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from kildeanalyse.adaptere.opencode_cli import OpencodeCliAdapter, les_hendelser, json_answer, permissions, reader_config
from kildeanalyse.cli_paths import opencode_bin, version_tuple
from kildeanalyse.modell import Inputpakke, Plan, Side
from kildeanalyse.parametre import normaliser


def event(kind, session='ses_one', **part):
    return {'type': kind, 'sessionID': session, 'part': {'sessionID': session, **part}}


def stream(*extra, answer='{"result": {}}', tools=True):
    events = [event('step_start'), event('text', messageID='msg_1', text='Reading the source.'),
              *([event('tool_use', tool='read', state={'status': 'completed'})] if tools else []),
              event('step_finish', cost=0.01, tokens={'input': 100, 'output': 5}),
              *extra, event('text', messageID='msg_2', text=answer)]
    return '\n'.join(json.dumps(e) for e in events)


def test_final_message_is_the_answer():
    result, blocked = les_hendelser(stream(), 0, file_tools=True)
    assert result.svar == {'result': {}} and result.feil is None and blocked is None
    assert result.sesjon_id == 'ses_one'
    assert result.forbruk['tokens'] == {'input': 100, 'output': 5}


def test_one_fenced_json_object_is_accepted_but_bare_prose_is_not():
    assert json_answer('{"a": 1}') == ({'a': 1}, 'message')
    assert json_answer('```json\n{"a": 1}\n```') == ({'a': 1}, 'fenced message')
    assert json_answer('Findings below.\n\n```json\n{"a": 1}\n```') == ({'a': 1}, 'only fenced block in the message')
    for text in ('Here: {"a": 1}', '[1]', '', '```json\n{"a": 1}\n```\n```json\n{"a": 2}\n```'):
        with pytest.raises(ValueError):
            json_answer(text)


@pytest.mark.parametrize('extra,code', [
    ((), 1),
    (({'type': 'error', 'sessionID': 'ses_one', 'error': {'type': 'unknown', 'message': 'boom'}},), 0),
    ((event('text', session='ses_two', messageID='m', text='{}'),), 0),
])
def test_fail_closed(extra, code):
    result, _ = les_hendelser(stream(*extra), code, file_tools=True)
    assert result.svar is None and result.feil and result.raasvar


def test_inline_reading_rejects_tool_use():
    result, _ = les_hendelser(stream(), 0, file_tools=False)
    assert result.svar is None and 'Unexpected tool use' in result.feil


def test_unavailable_provider_blocks_the_queue():
    error = {'type': 'error', 'sessionID': 'ses_one',
             'error': {'type': 'provider.no-route', 'message': 'Model unavailable: anthropic/x'}}
    result, blocked = les_hendelser(json.dumps(error), 1, file_tools=True)
    assert blocked == 'provider.no-route' and result.svar is None


def test_permissions_deny_by_default_and_keep_edits_in_the_workspace(tmp_path):
    assert permissions(None, tmp_path, tmp_path) == [{'action': '*', 'resource': '*', 'effect': 'deny'}]
    python, helper = tmp_path/'python'/'python.exe', tmp_path/'attempt'/'reader-helper.py'
    workspace = {'python': python.as_posix(), 'helper': str(helper),
                 'bash_prefix': f'{python.as_posix()} -I {helper.as_posix()}',
                 'powershell_prefix': f"& '{python.as_posix()}' -I '{helper.as_posix()}'"}
    rules = permissions(workspace, tmp_path/'attempt', python.parent)
    assert rules[0] == {'action': '*', 'resource': '*', 'effect': 'deny'}
    allowed = {rule['action'] for rule in rules if rule['effect'] == 'allow' and rule['resource'] == '*'}
    assert allowed == {'read', 'glob', 'grep', 'edit'}
    assert not {'skill', 'subagent', 'question', 'webfetch', 'websearch', 'shell'} & allowed
    shell = [rule['resource'] for rule in rules if rule['action'] == 'shell']
    assert f"{workspace['bash_prefix']} *" in shell and f"{workspace['powershell_prefix']} *" in shell
    assert all(helper.as_posix() in command or str(helper) in command for command in shell)
    boundary = (tmp_path/'attempt').resolve().as_posix() + '/*'
    assert {'action': 'edit', 'resource': boundary, 'effect': 'deny'} in rules
    config = reader_config('Instruction', workspace, tmp_path, tmp_path)
    assert config['agents']['sda-reader']['system'] == 'Instruction' and config['default_agent'] == 'sda-reader'


def test_npm_shim_resolves_to_native_executable(tmp_path):
    shim = tmp_path/'npm'/'opencode.cmd'
    native = tmp_path/'npm'/'node_modules'/'@opencode'/'cli'/'bin'/'opencode.exe'
    native.parent.mkdir(parents=True)
    shim.write_text('@echo off')
    native.write_bytes(b'')
    assert opencode_bin(str(shim)) == str(native)
    assert opencode_bin(str(tmp_path/'other.exe')) == str(tmp_path/'other.exe')


def test_version_gate(monkeypatch):
    monkeypatch.setattr(OpencodeCliAdapter, '_bin', lambda self: 'opencode')
    monkeypatch.setattr('subprocess.run', lambda *a, **k: SimpleNamespace(returncode=0, stdout=b'opencode v1.9.0', stderr=b''))
    assert not OpencodeCliAdapter().sjekk_stotte().ok
    monkeypatch.setattr('subprocess.run', lambda *a, **k: SimpleNamespace(returncode=0, stdout=b'opencode v2.0.18', stderr=b''))
    assert OpencodeCliAdapter().sjekk_stotte().ok
    assert version_tuple('opencode v2.0.18') == (2, 0, 18)


def test_model_must_name_the_provider():
    model, settings = normaliser('opencode_cli', 'anthropic/claude-sonnet-5')
    assert model == 'anthropic/claude-sonnet-5'
    assert settings['tenkenivaa'] == 'standard' and settings['file_tools'] is True
    assert normaliser('opencode_cli', 'openrouter/vendor/model', tenkenivaa='high')[1]['tenkenivaa'] == 'high'
    for bad in ('', 'claude-sonnet-5', 'anthropic/claude-sonnet-5#high', 'anthropic/ x'):
        with pytest.raises(ValueError):
            normaliser('opencode_cli', bad)
    with pytest.raises(ValueError):
        normaliser('opencode_cli', 'anthropic/claude-sonnet-5', tenkenivaa='ultra')


def test_run_isolates_config_and_removes_the_session(tmp_path, monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'not-a-real-key')
    monkeypatch.setenv('OPENCODE_CONFIG', str(tmp_path/'user.json'))
    monkeypatch.setenv('PWD', str(tmp_path))
    monkeypatch.setattr(OpencodeCliAdapter, '_bin', lambda self: 'opencode')
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        if args[1] == '--version':
            return SimpleNamespace(returncode=0, stdout=b'opencode v2.0.18', stderr=b'')
        if args[1:3] == ['session', 'export']:
            info = {'info': {'model': {'providerID': 'anthropic', 'id': 'claude-sonnet-5', 'variant': 'high'}, 'cost': 0.02,
                             'tokens': {'input': 120, 'output': 9}}}
            return SimpleNamespace(returncode=0, stdout=json.dumps(info).encode(), stderr=b'')
        return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')

    class Process:
        def __init__(self, args, **kwargs):
            calls.append((args, kwargs))
            self.pid, self.returncode = 42, 0

        def communicate(self, input=None, timeout=None):
            self.stdin = input
            return stream(answer='{"result": {"ok": true}}', tools=False).encode(), b''

        def poll(self):
            return 0

    monkeypatch.setattr('subprocess.run', run)
    monkeypatch.setattr('subprocess.Popen', Process)
    plan = Plan(formaal='Test', task_instructions='Read', motor='opencode_cli', modell='anthropic/claude-sonnet-5')
    package = Inputpakke(forsok_id='f', kjoring_id='k', dokument_id='d', dokument_navn='n', dokument_sha256='s',
                         sider=[Side(nr=1, tekst='text', tegn=4)], systeminstruks='Instruction', brukermelding='Document',
                         svarskjema={'type': 'object'}, kjoreparametre={'file_tools': False})
    adapter = OpencodeCliAdapter({'tenkenivaa': 'high', 'file_tools': False})
    result = adapter.kjor(package, plan.modell, lambda: False, str(tmp_path/'attempt'))
    assert result.svar == {'result': {'ok': True}} and result.feil is None
    assert result.modell_rapportert == 'anthropic/claude-sonnet-5'
    assert result.motorinfo['tenkenivaa_rapportert'] == 'high'
    assert result.motorinfo['opencode_session']['deleted'] is True
    assert result.forbruk['tokens'] == {'input': 120, 'output': 9} and result.forbruk['cost_usd_estimate'] == 0.02
    assert result.motorinfo['answer_extraction'] == 'message'
    run_args, run_kwargs = next((a, k) for a, k in calls if a[1] == 'run')
    assert run_args[run_args.index('--model') + 1] == 'anthropic/claude-sonnet-5#high' and '--standalone' in run_args
    env = run_kwargs['env']
    assert 'ANTHROPIC_API_KEY' not in env and 'OPENCODE_CONFIG' not in env
    assert env['OPENCODE_DISABLE_PROJECT_CONFIG'] == '1'
    # OpenCode resolves its working directory from PWD, so it must be the run workspace.
    assert env['PWD'] == run_kwargs['cwd'] == str((tmp_path/'attempt'/'tom_arbeidsmappe').resolve())
    config = json.loads((Path(env['XDG_CONFIG_HOME'])/'opencode'/'opencode.json').read_text(encoding='utf-8'))
    assert config['permissions'] == [{'action': '*', 'resource': '*', 'effect': 'deny'}]
    assert config['agents']['sda-reader']['system'].startswith('Instruction\n\nResponse format:')
    assert [a[1:3] for a, _ in calls if a[1] == 'session'] == [['session', 'export'], ['session', 'delete']]
