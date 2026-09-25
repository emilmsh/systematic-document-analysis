"""Cooperative update shutdown with real local processes; no provider calls."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import anyio
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'bin'))

from kildeanalyse import maintenance, tjeneste
from kildeanalyse.kjoring import Koer
from kildeanalyse.lager import Lager
from test_flyt import _oppsett


def python_command(code, *args):
    # Windows venv python.exe is a redirector; test the actual process, not a
    # wrapper whose termination would leave its child interpreter running.
    bootstrap = 'import sys; sys.path[:] = '+repr(sys.path)+';\n'
    return [sys._base_executable, '-I', '-X', 'utf8', '-c', bootstrap+code, *map(str, args)]


def test_intent_excludes_reconnect_and_other_installer_and_clears_after_failure():
    with pytest.raises(ValueError, match='test interruption'):
        with maintenance.installation_lock(wait_seconds=0):
            assert maintenance.update_pending()
            with pytest.raises(maintenance.MaintenanceBusy):
                with maintenance.maintenance_lock(shared=True):
                    pass
            with pytest.raises(maintenance.MaintenanceBusy):
                with maintenance.installation_lock(wait_seconds=0):
                    pass
            raise ValueError('test interruption')
    assert not maintenance.update_pending()
    with maintenance.maintenance_lock(shared=True):
        pass


def test_old_session_times_out_without_releasing_its_lock():
    with maintenance.maintenance_lock(shared=True):
        with pytest.raises(maintenance.MaintenanceBusy, match='0.8.4 or earlier'):
            with maintenance.installation_lock(wait_seconds=0):
                pytest.fail('Must not enter the installation')
        assert not maintenance.update_pending()
        with pytest.raises(maintenance.MaintenanceBusy):
            with maintenance.maintenance_lock():
                pass


def test_killed_installer_leaves_no_shutdown_request():
    code = ('from kildeanalyse.maintenance import installation_lock; import time\n'
            'with installation_lock():\n print("LOCKED", flush=True)\n time.sleep(30)')
    child = subprocess.Popen(python_command(code), stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == 'LOCKED'
        assert maintenance.update_pending()
    finally:
        child.kill()  # Only this test's deliberately blocked child process.
        child.wait(timeout=10)
        child.stdout.close()
    assert not maintenance.update_pending()
    with maintenance.maintenance_lock(shared=True):
        pass


@pytest.mark.parametrize('activity', ['idle', 'tool', 'worker'])
def test_real_mcp_session_drains_and_closes_with_stdin_still_open(tmp_path, activity):
    started, done = tmp_path/'started', tmp_path/'saved'
    code = '''
import anyio, sys, threading, time
from pathlib import Path
from kildeanalyse.mcp_server import server, main
from kildeanalyse import tjeneste
started, done, mode = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
@server.tool()
async def controlled_work() -> str:
    if mode == 'worker':
        def work():
            started.write_text('started')
            time.sleep(1.5)
            done.write_text('saved')
        worker = threading.Thread(target=work, daemon=True)
        tjeneste._traader['test'] = worker
        worker.start()
    else:
        started.write_text('started')
        await anyio.sleep(1.5)
        done.write_text('saved')
    return 'saved'
main()
'''
    env = {**os.environ, 'SDA_DATA':str(tmp_path/'data')}
    with (tmp_path/'server.stderr').open('w', encoding='utf-8') as error:
        child = subprocess.Popen(python_command(code, started, done, activity),
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=error,
                                 text=True, encoding='utf-8', env=env)
        def send(value):
            child.stdin.write(json.dumps({'jsonrpc':'2.0', **value})+'\n')
            child.stdin.flush()
        try:
            send({'id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25',
                  'capabilities':{},'clientInfo':{'name':'update-test','version':'1'}}})
            assert 'result' in json.loads(child.stdout.readline())
            send({'method':'notifications/initialized'})
            if activity != 'idle':
                send({'id':2,'method':'tools/call','params':{'name':'controlled_work','arguments':{}}})
                deadline = time.monotonic()+10
                while not started.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                assert started.exists()
            with maintenance.installation_lock(wait_seconds=10):
                if activity != 'idle':
                    assert done.read_text() == 'saved'
                child.wait(timeout=5)
                assert child.returncode == 0
                assert not child.stdin.closed  # The update, not client EOF, closed it.
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=10)
            child.stdin.close()
            child.stdout.close()
    assert 'Connection closed for update' in (tmp_path/'server.stderr').read_text(encoding='utf-8')


def test_current_document_saved_and_remaining_queue_preserved(tmp_path, monkeypatch):
    store = Lager(tmp_path/'data')
    _, aid, runs = _oppsett(store)
    begun, release = threading.Event(), threading.Event()
    original = Koer._kjor_en
    def slow_document(self, *args):
        begun.set()
        assert release.wait(10)
        return original(self, *args)
    monkeypatch.setattr(Koer, '_kjor_en', slow_document)
    results = []
    worker = threading.Thread(target=lambda: results.append(tjeneste.start(store, aid)))
    worker.start()
    assert begun.wait(10)
    # The installer signals while the document is active; it is allowed to finish.
    with maintenance._file_lock('update.lock'):
        release.set()
        worker.join(timeout=10)
        assert not worker.is_alive()
    assert len(results[0]['startet']) == 1
    assert len(results[0]['stoppet_foer']) == 2
    assert [r['status'] for r in store.kjoringer(aid)] == ['fullført','planlagt','planlagt']
    assert tjeneste.vis_kjoring(store, runs[0]['id'])['forsok'][-1]['forsok']['raasvar']


def test_pipe_input_keeps_split_unicode_and_multiple_messages():
    from kildeanalyse.stdio_input import PipeInput
    stream = object.__new__(PipeInput)
    chunks = iter([b'first \xc3', None, b'\xb8\nsecond\nlast', b''])
    stream._read = lambda: next(chunks)
    async def collect():
        return [line async for line in stream]
    assert anyio.run(collect) == ['first ø\n', 'second\n', 'last']


def test_new_tool_call_during_update_reports_reason_and_does_no_work(tmp_path, monkeypatch):
    from kildeanalyse.mcp_server import server
    from mcp.server.mcpserver.exceptions import ToolError
    monkeypatch.setattr(maintenance, '_draining', threading.Event())
    monkeypatch.setenv('SDA_DATA', str(tmp_path/'unused-data'))
    async def call():
        return await server.call_tool('create_project', {'name':'Must not be created'})
    with maintenance.installation_lock():
        with pytest.raises(ToolError, match='Plugin update in progress'):
            anyio.run(call)
    assert not (tmp_path/'unused-data').exists()


@pytest.mark.parametrize('recover', [False, True])
def test_installer_holds_one_gate_for_both_hosts(tmp_path, monkeypatch, recover):
    import installer
    monkeypatch.setattr(installer, 'packaged_process', lambda: False)
    called = []
    def operate(host, base, **kwargs):
        assert kwargs['locked'] and maintenance.update_pending()
        with pytest.raises(maintenance.MaintenanceBusy):
            with maintenance.maintenance_lock(shared=True):
                pass
        called.append(host)
        return 'done'
    monkeypatch.setattr(installer, 'recover' if recover else 'install', operate)
    monkeypatch.setattr(sys, 'argv', ['installer.py', 'both', '--non-interactive', '--local-copy',
        '--base-dir', str(tmp_path/'installed')] + (['--recover'] if recover else []))
    assert installer.main() == 0
    assert called == ['claude','codex']
    assert not maintenance.update_pending()
