"""Installer transactions and release updates, without network or real profiles."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'bin'))
import installer
import pakk_plugin
import update_plugin as updater
from kildeanalyse.maintenance import MaintenanceBusy, maintenance_lock, read_json, state_dir, write_json


class Host:
    def __init__(self, monkeypatch, host='codex'):
        self.host = host
        self.source = None
        self.plugin = None
        self.fail_next_install = False
        self.commands = []
        monkeypatch.setattr(installer, 'ensure_reader', lambda host:'fake-cli')
        monkeypatch.setattr(updater, 'find_cli', lambda host:sys.executable)
        monkeypatch.setattr(installer, 'inspect', self.inspect)
        monkeypatch.setattr(installer, 'run', self.run)

    def inspect(self, host, exe):
        return ({'name':installer.MARKET} if self.source else None, self.source, self.plugin)

    def run(self, command):
        args = command[1:]
        self.commands.append(args)
        if args[:3] == ['plugin','marketplace','add']:
            self.source = Path(args[3]).resolve()
        elif args[:3] == ['plugin','marketplace','remove']:
            self.source = None
        elif args[:2] in (['plugin','remove'], ['plugin','uninstall']):
            self.plugin = None
        elif args[:2] in (['plugin','add'], ['plugin','install']):
            if self.fail_next_install:
                self.fail_next_install = False
                raise subprocess.CalledProcessError(1, command)
            self.plugin = {'name':installer.NAME, 'version':installer.version(self.source), 'enabled':True}


def set_version(root, value):
    previous = installer.version(root)
    runtime = root/'src/kildeanalyse/__init__.py'
    runtime.write_text(runtime.read_text(encoding='utf-8').replace('VERSJON = "'+previous+'"',
                       'VERSJON = "'+value+'"'), encoding='utf-8')
    path = root/'pyproject.toml'
    text = path.read_text(encoding='utf-8')
    text = text.replace('version = "'+installer.version(root)+'"', 'version = "'+value+'"')
    path.write_text(text, encoding='utf-8')
    for directory in ('.codex-plugin','.claude-plugin'):
        path = root/directory/'plugin.json'
        manifest = read_json(path); manifest['version'] = value; write_json(path, manifest)
    path = root/'.claude-plugin/marketplace.json'
    manifest = read_json(path); manifest['plugins'][0]['version'] = value; write_json(path, manifest)


@pytest.fixture
def source(tmp_path, monkeypatch):
    root = tmp_path/'release'/installer.NAME
    pakk_plugin.pakk(root)
    monkeypatch.setattr(installer, 'ROOT', root)
    return root


def test_new_install_noop_and_repair_keep_backup(source, tmp_path, monkeypatch):
    host = Host(monkeypatch)
    base = tmp_path/'installed'
    assert installer.install('codex',base) == 'installed'
    target = base/'codex'/installer.NAME
    launcher = read_json(target/'.mcp.json')['mcpServers']['document_analysis']
    assert launcher['args'][-1] == str(target/'bin/start_server.py')
    commands = len(host.commands)
    assert installer.install('codex',base) == 'already up to date'
    assert len(host.commands) == commands
    (target/'README.md').write_text('local change')
    with pytest.raises(RuntimeError, match='Same version'):
        installer.install('codex',base)
    assert (target/'README.md').read_text() == 'local change'
    assert installer.install('codex',base,repair=True) == 'installed'
    backups = list((target.parent/'backups').glob('*/'+installer.NAME))
    assert len(backups) == 1
    assert (backups[0]/'README.md').read_text() == 'local change'


@pytest.mark.parametrize('host_name', ['codex','claude'])
def test_source_conflict_is_checked_before_copy_and_can_switch(source,tmp_path,monkeypatch,host_name):
    host = Host(monkeypatch,host_name)
    original = tmp_path/'old'; replacement = tmp_path/'new'
    installer.install(host_name, original)
    old_source = host.source
    original_bytes = (old_source/'README.md').read_bytes()
    with pytest.raises(RuntimeError,match='Switch to this installation'):
        installer.install(host_name, replacement)
    assert not replacement.exists()
    assert host.source == old_source
    assert installer.install(host_name,replacement,replace_source=True) == 'installed'
    assert host.source == replacement/host_name/installer.NAME
    assert (old_source/'README.md').read_bytes() == original_bytes


@pytest.mark.parametrize('switch', [False,True])
def test_failed_host_registration_restores_source_files_and_plugin(source,tmp_path,monkeypatch,switch):
    host = Host(monkeypatch)
    base = tmp_path/'installed'
    installer.install('codex',base)
    original_source = host.source
    original_manifest = read_json(original_source/installer.MARKER)
    set_version(source,'99.0.0')
    host.fail_next_install = True
    replacement = tmp_path/'new' if switch else base
    with pytest.raises(RuntimeError,match='previous source/files restored'):
        installer.install('codex',replacement,replace_source=switch)
    assert host.source == original_source
    assert host.plugin['version'] == original_manifest['version']
    assert read_json(original_source/installer.MARKER) == original_manifest
    assert not (replacement/'codex'/'pending-install.json').exists()


def test_newer_disabled_and_shared_marketplace_are_preserved(source,tmp_path,monkeypatch):
    host = Host(monkeypatch)
    base = tmp_path/'installed'; installer.install('codex',base)
    before = (host.source/installer.MARKER).read_bytes()
    host.plugin['version'] = '99.0.0'
    with pytest.raises(RuntimeError,match='newer version'):
        installer.install('codex',base)
    assert (host.source/installer.MARKER).read_bytes() == before
    host.plugin['enabled'] = False
    assert installer.install('codex',base) == 'kept disabled installation'
    path = host.source/'.claude-plugin/marketplace.json'
    marketplace = read_json(path); marketplace['plugins'].append({'name':'another-plugin'}); write_json(path,marketplace)
    with pytest.raises(RuntimeError,match='other plugins'):
        installer.install('codex',tmp_path/'elsewhere',replace_source=True)


def test_upgrade_replaces_full_package_without_stale_files(source,tmp_path,monkeypatch):
    Host(monkeypatch)
    base = tmp_path/'installed'; installer.install('codex',base)
    target = base/'codex'/installer.NAME
    (target/'obsolete.py').write_text('old')
    set_version(source,'99.0.0')
    assert installer.install('codex',base) == 'installed'
    assert not (target/'obsolete.py').exists()
    assert len(list((target.parent/'backups').glob('*/'+installer.NAME+'/obsolete.py'))) == 1


def test_live_sessions_and_workers_exclude_installer(source,tmp_path,monkeypatch):
    Host(monkeypatch)
    with maintenance_lock(shared=True), maintenance_lock(shared=True):
        with pytest.raises(MaintenanceBusy):
            installer.install('codex',tmp_path/'installed')
    with maintenance_lock():
        with pytest.raises(MaintenanceBusy):
            with maintenance_lock(shared=True):
                pass
    assert installer.install('codex',tmp_path/'installed') == 'installed'


def test_codex_extended_windows_path_normalizes():
    if sys.platform == 'win32':
        assert installer.local_path('\\\\?\\C:\\example\\plugin') == installer.local_path('C:\\example\\plugin')


def release_payload(root):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer,'w') as archive:
        for path in pakk_plugin.pakkefiler(root):
            archive.write(path, Path(installer.NAME)/path.relative_to(root))
    return buffer.getvalue()


def fake_download(monkeypatch,payload):
    checksum = (hashlib.sha256(payload).hexdigest()+'  '+updater.ARCHIVE+'\n').encode()
    monkeypatch.setattr(updater,'fetch',lambda url,maximum:checksum if url.endswith('/1') else payload)


def release_info(value):
    return {'version':value,'tag':'v'+value,'assets':{'SHA256SUMS.txt':1,updater.ARCHIVE:2}}


def test_release_checksum_and_manifest_version_required(source,tmp_path,monkeypatch):
    payload = release_payload(source)
    fake_download(monkeypatch,payload)
    current = installer.version(source)
    assert updater.download(release_info(current),tmp_path/'download')
    with pytest.raises(ValueError,match='version differ'):
        updater.download(release_info('99.0.0'),tmp_path/'wrong-version')
    monkeypatch.setattr(updater,'fetch',lambda url,maximum: b'0'*64+b'  '+updater.ARCHIVE.encode() if url.endswith('/1') else payload)
    with pytest.raises(ValueError,match='checksum mismatch'):
        updater.download(release_info(current),tmp_path/'bad-checksum')
    assert not (tmp_path/'bad-checksum').exists()


@pytest.mark.parametrize('name', ['../outside','systematic-document-analysis/../../outside','systematic-document-analysis/C:bad',
                                  'systematic-document-analysis/a\\b','systematic-document-analysis/NUL.txt',
                                  'systematic-document-analysis/./alias','systematic-document-analysis/a?b'])
def test_archive_cannot_escape_or_use_windows_aliases(tmp_path,name):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:
        entry = zipfile.ZipInfo('safe')
        entry.filename = name  # Avoid ZipInfo normalizing backslashes on Windows.
        archive.writestr(entry,'bad')
    with pytest.raises(ValueError,match='Unsafe path'):
        updater.extract_release(stream.getvalue(),tmp_path/'extract')
    assert not (tmp_path/'extract').exists()


def test_daily_check_caches_offline_and_never_executes_release_notes(monkeypatch):
    calls = []
    def unavailable(*args):
        calls.append(args); raise OSError('offline')
    monkeypatch.setattr(updater,'fetch',unavailable)
    first = updater.check(); assert 'unavailable' in first['message']
    assert updater.check() == first and len(calls) == 1
    monkeypatch.setattr(updater,'fetch',lambda *args:json.dumps({'tag_name':'v99.0.0','body':'Untrusted release notes',
                        'assets':[{'name':updater.ARCHIVE,'id':2},{'name':'SHA256SUMS.txt','id':1}]}).encode())
    assert updater.check(force=True)['version'] == '99.0.0'


def test_unmanaged_and_off_startup_never_contact_network(source,tmp_path,monkeypatch):
    monkeypatch.setattr(updater,'fetch',lambda *args:pytest.fail('Unexpected network'))
    assert updater.startup(source) is False
    Host(monkeypatch); installer.install('codex',tmp_path/'installed')
    target = tmp_path/'installed/codex'/installer.NAME
    write_json(state_dir()/'updates.json',{'mode':'off'})
    assert updater.startup(target) is False


def test_auto_update_applies_verified_release_and_keeps_old_copy(source,tmp_path,monkeypatch):
    host = Host(monkeypatch)
    base = tmp_path/'installed'; installer.install('codex',base)
    target = host.source
    old_version = installer.version(target)
    set_version(source,'99.0.0')
    fake_download(monkeypatch,release_payload(source))
    release = release_info('99.0.0')
    with maintenance_lock():
        assert updater.apply_release(updater.managed_install(target),release)
    assert installer.version(target) == '99.0.0'
    backup = next((target.parent/'backups').glob('*/'+installer.NAME))
    assert installer.version(backup) == old_version
    assert read_json(target/installer.MARKER)['installed_sha256'] == installer.package_hash(target)


@pytest.mark.parametrize('changed_file', ['README.md','.mcp.json'])
def test_auto_update_refuses_local_changes(source,tmp_path,monkeypatch,changed_file):
    Host(monkeypatch); installer.install('codex',tmp_path/'installed')
    target = tmp_path/'installed/codex'/installer.NAME
    (target/changed_file).write_text('local edits')
    with pytest.raises(RuntimeError,match='local changes'):
        updater.apply_release(updater.managed_install(target),{'version':'99.0.0','tag':'v99.0.0'})


def test_notify_auto_off_and_busy_startup_policies(source,tmp_path,monkeypatch,capsys):
    import time
    Host(monkeypatch); installer.install('codex',tmp_path/'installed')
    target = tmp_path/'installed/codex'/installer.NAME
    release = {**release_info('99.0.0'),'checked_at':time.time(),'message':'Available'}
    write_json(state_dir()/'last-check.json',release)
    calls = []
    monkeypatch.setattr(updater,'apply_release',lambda *args:calls.append(args) or True)
    monkeypatch.setattr(updater,'fetch',lambda *args:pytest.fail('Cached checks should not access the network'))
    capsys.readouterr()
    assert updater.startup(target) is False  # Default is notify, no installation.
    assert not calls
    output = capsys.readouterr(); assert output.out == '' and '99.0.0' in output.err
    with maintenance_lock(shared=True):  # A concurrent session must still see the notice.
        assert updater.startup(target) is False
    assert '99.0.0' in capsys.readouterr().err
    write_json(state_dir()/'updates.json',{'mode':'auto'})
    with maintenance_lock(shared=True):
        assert updater.startup(target) is False
    assert not calls
    assert updater.startup(target) is True
    assert len(calls) == 1
    assert updater.startup(target) is False  # One automatic attempt per day.
    assert len(calls) == 1


def test_github_cli_transport_uses_existing_login_without_token(monkeypatch):
    monkeypatch.setattr(updater.shutil,'which',lambda name:'gh.exe')
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        kwargs['stdout'].write(b'{"tag_name":"v1.0.0"}')
        return subprocess.CompletedProcess(command,0)
    monkeypatch.setattr(updater.subprocess,'run',run)
    assert json.loads(updater.fetch(updater.API))['tag_name'] == 'v1.0.0'
    assert commands[0][:4] == ['gh.exe','api','--hostname','github.com']
    assert not any('token' in arg.lower() or 'auth login' in arg.lower() for arg in commands[0])


def test_failed_fresh_install_leaves_no_registration_or_incomplete_target(source,tmp_path,monkeypatch):
    host = Host(monkeypatch); host.fail_next_install = True
    with pytest.raises(RuntimeError,match='restored'):
        installer.install('codex',tmp_path/'installed')
    assert host.source is None and host.plugin is None
    assert not (tmp_path/'installed/codex'/installer.NAME).exists()
    assert not (tmp_path/'installed/codex/pending-install.json').exists()


def test_corrupt_install_record_can_be_repaired_but_pending_transaction_blocks(source,tmp_path,monkeypatch):
    Host(monkeypatch); base=tmp_path/'installed'; installer.install('codex',base)
    target=base/'codex'/installer.NAME
    (target/installer.MARKER).write_text('corrupt metadata')
    assert installer.install('codex',base,repair=True) == 'installed'
    write_json(target.parent/'pending-install.json', {'target':str(target)})
    with pytest.raises(RuntimeError,match='interrupted installation'):
        installer.install('codex',base)


@pytest.mark.parametrize('file', ['src/kildeanalyse/__init__.py','.claude-plugin/marketplace.json'])
def test_release_rejects_runtime_or_marketplace_version_drift(source,file):
    path = source/file
    path.write_text(path.read_text(encoding='utf-8').replace(installer.version(source),'99.88.77'),encoding='utf-8')
    with pytest.raises(ValueError,match='version differs'):
        installer.validate_package(source)


def test_codex_desktop_shadow_copy_is_detected_and_moved_aside_only_on_request(source, tmp_path, monkeypatch):
    host = Host(monkeypatch)
    local = tmp_path/'L'  # Short paths: Windows MAX_PATH applies in the fake LocalAppData.
    monkeypatch.setenv('LOCALAPPDATA', str(local))
    base = local/'systematic-document-analysis'/'plugins'
    target = base/'codex'/installer.NAME
    shadow = local/'Packages'/'OpenAI.Codex_x'/'LocalCache'/'Local'/target.relative_to(local)
    shadow.mkdir(parents=True)
    (shadow/'pyproject.toml').write_text((source/'pyproject.toml').read_text(encoding='utf-8').replace(
        installer.version(source), '0.1.0'), encoding='utf-8')
    (shadow/'README.md').write_text('stale desktop copy', encoding='utf-8')
    with pytest.raises(RuntimeError, match='shadow copy'):
        installer.install('codex', base)
    assert not target.exists() and shadow.exists() and host.source is None
    assert installer.install('codex', base, move_shadow=True) == 'installed'
    assert not shadow.exists()
    aside = list(shadow.parent.glob(installer.NAME+'.shadow-*'))
    assert len(aside) == 1 and (aside[0]/'README.md').read_text(encoding='utf-8') == 'stale desktop copy'
    assert installer.version(target) == installer.version(source)
    # Shadow-free Codex reinstalls and Claude installations are unaffected.
    assert installer.install('codex', base) == 'already up to date'
    Host(monkeypatch, 'claude')
    (shadow.parents[1]/'claude'/installer.NAME).mkdir(parents=True)
    assert installer.install('claude', base) == 'installed'


def test_update_command_checks_and_sets_policy_beside_open_sessions(source, tmp_path, monkeypatch, capsys):
    Host(monkeypatch); installer.install('codex', tmp_path/'installed')
    target = tmp_path/'installed/codex'/installer.NAME
    monkeypatch.setattr(updater, 'fetch', lambda *args: json.dumps({'tag_name':'v99.0.0', 'body':'notes',
                        'assets':[{'name':updater.ARCHIVE,'id':2},{'name':'SHA256SUMS.txt','id':1}]}).encode())
    monkeypatch.setattr(updater, 'apply_release', lambda *args: pytest.fail('No installation expected'))
    monkeypatch.setattr(updater.Path, 'resolve', lambda self: target/'bin'/'update_plugin.py' if self.name == 'update_plugin.py' else Path.__new__(Path, self))
    with maintenance_lock(shared=True):  # Another plugin session is open.
        monkeypatch.setattr(sys, 'argv', ['update_plugin.py', '--check', '--mode', 'auto'])
        assert updater.main() == 0
        assert read_json(state_dir()/'updates.json') == {'mode':'auto'}
        assert '99.0.0' in capsys.readouterr().out
        monkeypatch.setattr(sys, 'argv', ['update_plugin.py', '--install'])
        assert updater.main() == 1
        assert 'Close other plugin sessions' in capsys.readouterr().err
