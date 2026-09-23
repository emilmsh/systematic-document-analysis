"""Authentication loss must never dispatch a model call or a replacement reader."""
import io
import json
from pathlib import Path
import subprocess

import pytest

from kildeanalyse import tjeneste
from kildeanalyse.adaptere import claude_cli, codex_cli
from kildeanalyse.cli_auth import subscription_confirmed
from kildeanalyse.lager import Lager

READERS = [('claude', claude_cli.ClaudeCliAdapter), ('codex', codex_cli.CodexCliAdapter)]


def ready(name):
    if name == 'claude':
        return 0, json.dumps({'loggedIn': True, 'authMethod': 'claude.ai', 'apiProvider': 'firstParty'}), ''
    return 0, '', 'Logged in using ChatGPT'


def status_cli(monkeypatch, name, reader_class, responses):
    replies = iter(responses)
    observed = []
    monkeypatch.setattr(reader_class, '_bin', lambda self: 'test-cli')
    monkeypatch.setattr(reader_class, '_env', lambda self: {})

    def run(command, **kwargs):
        observed.append(command)
        assert command[1:] in (['--version'], ['--help'], ['auth', 'status'], ['login', 'status'])
        if command[1:] == ['--version']:
            code, stdout, stderr = 0, 'test-version', ''
        elif command[1:] == ['--help']:
            code, stdout, stderr = 0, '--restricted', ''
        else:
            reply = next(replies)
            if isinstance(reply, Exception):
                raise reply
            code, stdout, stderr = reply
        return subprocess.CompletedProcess(command, code, stdout.encode(), stderr.encode())

    monkeypatch.setattr(subprocess, 'run', run)
    return observed


def process_cli(monkeypatch, name, payload, *, failure=False, crash=False):
    calls = []

    class Process:
        pid = 23456
        returncode = 1 if failure else 0

        def __init__(self, command, **kwargs):
            calls.append(command)
            if crash:
                raise OSError('Executable disappeared after sign-in check')
            value = payload() if callable(payload) else payload
            if name == 'claude':
                data = {'session_id': 'test-session', 'structured_output': value,
                        'is_error': failure, 'result': 'Authentication expired' if failure else ''}
                raw = json.dumps(data)
            else:
                events = [{'type': 'thread.started', 'thread_id': 'test-session'}]
                events += ([{'type': 'turn.failed', 'error': {'message': 'Authentication expired'}}] if failure else [
                    {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(value)}},
                    {'type': 'turn.completed'}])
                raw = '\n'.join(json.dumps(event) for event in events)
            self.raw = raw.encode()
            self.stdin, self.stdout, self.stderr = io.BytesIO(), io.BytesIO(self.raw), io.BytesIO()

        def communicate(self, **kwargs): return self.raw, b''
        def poll(self): return self.returncode
        def wait(self): return self.returncode

    monkeypatch.setattr(subprocess, 'Popen', Process)
    return calls


@pytest.mark.parametrize('name,code,out,err', [
    ('claude', 1, ready('claude')[1], ''),
    ('claude', 0, '{"loggedIn":"true","authMethod":"claude.ai","apiProvider":"firstParty"}', ''),
    ('claude', 0, '{"loggedIn":true,"authMethod":"api_key","apiProvider":"firstParty"}', ''),
    ('claude', 0, '{"loggedIn":true,"authMethod":"claude.ai","apiProvider":"bedrock"}', ''),
    ('claude', 0, '[]', ''), ('claude', 0, 'not json', ''),
    ('codex', 1, '', 'Logged in using ChatGPT'),
    ('codex', 0, '', 'Previously Logged in using ChatGPT; session expired'),
    ('codex', 0, '', 'Logged in using an API key'),
    ('codex', 0, '', ''),
])
def test_ambiguous_failed_and_api_auth_never_pass(name, code, out, err):
    assert not subscription_confirmed(name, code, out, err)


@pytest.mark.parametrize('name,reader_class', READERS)
@pytest.mark.parametrize('failure', ['missing', 'malformed', 'timeout', 'executable'])
def test_blocked_reader_never_prepares_files_or_launches_model(monkeypatch, tmp_path, name, reader_class, failure):
    response = {'missing': (1, '', 'Not signed in'), 'malformed': (0, 'private-secret', ''),
                'timeout': subprocess.TimeoutExpired('status', 20, output='private-secret'),
                'executable': OSError('private-secret')}[failure]
    status_cli(monkeypatch, name, reader_class, [response])
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: pytest.fail('Model must not start'))
    target = tmp_path / 'must-not-exist'
    result = reader_class().kjor(None, 'test-model', lambda: False, str(target))
    assert result.svar is None and result.motorinfo['stopp_ko']
    assert result.motorinfo['auth_gate']['code'] == 'CLI_AUTH_REQUIRED'
    assert result.motorinfo['auth_gate']['automatic_fallback_allowed'] is False
    assert 'private-secret' not in result.feil and not target.exists()


@pytest.mark.parametrize('name,reader_class', READERS)
def test_previous_success_does_not_authorize_later_call(monkeypatch, tmp_path, name, reader_class):
    status_cli(monkeypatch, name, reader_class, [ready(name), (1, '', 'Expired')])
    reader = reader_class()
    assert reader.sjekk_stotte().egenskaper['auth_gate']['status'] == 'verified'
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: pytest.fail('Stale sign-in must not be reused'))
    result = reader.kjor(None, 'test-model', lambda: False, str(tmp_path / 'call'))
    assert result.motorinfo['auth_gate']['status'] == 'blocked'


@pytest.mark.parametrize('name,reader_class', READERS)
def test_setup_exposes_machine_readable_block_and_recovery(monkeypatch, tmp_path, name, reader_class):
    from kildeanalyse import ocr
    from kildeanalyse.languages import public_result
    status_cli(monkeypatch, name, reader_class, [(1, '', 'private-secret')])
    monkeypatch.setattr(tjeneste, 'ADAPTERE', {name + '_cli': reader_class})
    monkeypatch.setattr(tjeneste.platform, 'platform', lambda: 'Test Windows')
    monkeypatch.setattr(ocr, 'setup', lambda: {})
    result = public_result(tjeneste.oppsett(Lager(tmp_path / 'store')))
    # Inspect the public payload without depending on translated legacy key names.
    def gates(value):
        if isinstance(value, dict):
            if 'auth_gate' in value:
                yield value['auth_gate']
            for child in value.values():
                yield from gates(child)
        elif isinstance(value, list):
            for child in value:
                yield from gates(child)
    gate, = gates(result)
    assert gate['code'] == 'CLI_AUTH_REQUIRED'
    assert gate['recovery_command'] == f'installer.cmd reader {name} --login'
    assert 'private-secret' not in json.dumps(result)


def analysis(tmp_path, name):
    store = Lager(tmp_path / 'store')
    project = tjeneste.opprett_prosjekt(store, 'Auth test')
    files = []
    for index in range(3):
        path = tmp_path / f'source-{index}.txt'
        path.write_text(f'Ordinary source document {index}.', encoding='utf-8')
        files.append(str(path))
    tjeneste.importer_dokumenter(store, project['id'], files)
    criteria = {'name': 'Policy', 'version': 1, 'criteria': [{'id': 'policy', 'name': 'Policy',
        'question': 'Is a policy described?', 'allowed_answers': ['yes', 'not_mentioned'],
        'evidence_required_for': ['yes'], 'rule': 'Use the document.'}]}
    result = tjeneste.opprett_analyse(store, project['id'], 'Test', 'Test',
                                    motor=name + '_cli', motorinnstillinger={'file_tools': False})
    aid = result['analyse']['id']
    tjeneste.godkjenn_plan(store, aid, 'Test user')
    runs = tjeneste.legg_til_kjoringer(store, aid)['nye']
    return store, aid, [run['id'] for run in runs]


@pytest.mark.parametrize('name,reader_class', READERS)
@pytest.mark.parametrize('background', [False, True])
def test_initial_gate_keeps_all_runs_planned(monkeypatch, tmp_path, name, reader_class, background):
    store, aid, runs = analysis(tmp_path, name)
    status_cli(monkeypatch, name, reader_class, [(1, '', 'No sign-in')])
    monkeypatch.setattr(subprocess, 'Popen', lambda *a, **k: pytest.fail('No model dispatch'))
    start = tjeneste.start_i_bakgrunnen if background else tjeneste.start
    with pytest.raises(tjeneste.TjenesteFeil, match='CLI_AUTH_REQUIRED'):
        start(store, aid)
    assert all(store.kjoring(run)['status'] == 'planlagt' for run in runs)
    assert not any(store.forsok_for_kjoring(run) for run in runs)


@pytest.mark.parametrize('name,reader_class', READERS)
@pytest.mark.parametrize('failure', ['before_call', 'during_call', 'spawn'])
def test_missing_auth_blocks_queue_but_call_errors_do_not(monkeypatch, tmp_path, name, reader_class, failure):
    store, aid, runs = analysis(tmp_path, name)
    status_cli(monkeypatch, name, reader_class,
               [ready(name), (1, '', 'Expired')] if failure == 'before_call' else [ready(name)] * 4)
    calls = process_cli(monkeypatch, name, {}, failure=failure == 'during_call', crash=failure == 'spawn')
    report = tjeneste.start(store, aid)
    assert report['startet'] == ([runs[0]] if failure == 'before_call' else runs)
    assert report['stoppet_foer'] == (runs[1:] if failure == 'before_call' else [])
    assert len(calls) == (0 if failure == 'before_call' else 3)
    assert store.kjoring(runs[0])['status'] == 'feilet'
    assert all(store.kjoring(run)['status'] == ('planlagt' if failure == 'before_call' else 'feilet') for run in runs[1:])
    assert bool(report['workflow_block']) == (failure == 'before_call')
    attempt = tjeneste.vis_kjoring(store, runs[0])['forsok'][0]
    assert attempt['result'] is None


@pytest.mark.parametrize('name,reader_class', READERS)
def test_revocation_between_documents_keeps_completed_result(monkeypatch, tmp_path, name, reader_class):
    store, aid, runs = analysis(tmp_path, name)
    status_cli(monkeypatch, name, reader_class, [ready(name), ready(name), (1, '', 'Expired')])
    payload = {'result':'No policy mentioned.', 'source_units_read':[1], 'limitations':[]}
    calls = process_cli(monkeypatch, name, payload)
    report = tjeneste.start(store, aid)
    assert len(calls) == 1 and report['startet'] == runs[:2]
    assert [store.kjoring(run)['status'] for run in runs] == ['fullført', 'feilet', 'planlagt']
    assert tjeneste.vis_kjoring(store, runs[0])['forsok'][0]['result'] == 'No policy mentioned.'
