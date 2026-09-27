"""OpenCode as host: managed copy plus one MCP server and skills path in its global config. No real profiles."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'bin'))
import installer
import opencode_host
import update_plugin as updater
from kildeanalyse.maintenance import maintenance_lock, read_json
from test_installer_updates import fake_download, release_info, release_payload, set_version, source  # noqa: F401


class Killed(BaseException):
    """A terminated process: ordinary rollback cannot catch it."""


@pytest.fixture
def opencode(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path/'xdg'))
    monkeypatch.setattr(opencode_host, 'check_opencode', lambda: 'opencode v2.0.18')
    monkeypatch.setattr(opencode_host, 'prepare_runtime', lambda target: True)
    monkeypatch.setattr(opencode_host, 'packaged_process', lambda: False)
    return tmp_path/'xdg'/'opencode'/'opencode.json'


def test_register_keeps_other_settings_and_replaces_only_its_own(opencode, tmp_path):
    opencode.parent.mkdir(parents=True)
    other = {'type': 'local', 'command': ['npx', 'other']}
    opencode.write_text(json.dumps({'model': 'anthropic/claude-sonnet-5', 'skills': ['~/team-skills'],
                                    'mcp': {'servers': {'other': other}}}), encoding='utf-8')
    first, second = tmp_path/'a'/installer.NAME, tmp_path/'b'/installer.NAME
    opencode_host.register(first)
    opencode_host.register(second)
    config = json.loads(opencode.read_text(encoding='utf-8'))
    assert config['model'] == 'anthropic/claude-sonnet-5' and config['mcp']['servers']['other'] == other
    assert config['skills'] == ['~/team-skills', str(second/'skills')]
    entry = config['mcp']['servers']['document_analysis']
    assert entry['command'][-1] == str(second/'bin'/'start_server.cmd')
    assert entry['timeout'] == {'startup': opencode_host.STARTUP_MS}
    assert entry['environment']['SDA_PLUGIN_DATA'] == str(opencode_host.plugin_data())
    assert opencode_host.registration()[1] == second


@pytest.mark.parametrize('text,message', [
    ('{\n  // comment\n  "model": "x"\n}', 'JSONC'),
    ('{"mcp": {"other": {"type": "local", "command": ["x"]}}}', 'OpenCode 1 layout'),
])
def test_jsonc_and_legacy_layout_are_never_rewritten(opencode, tmp_path, text, message):
    opencode.parent.mkdir(parents=True)
    opencode.write_text(text, encoding='utf-8')
    with pytest.raises(RuntimeError, match=message) as error:
        opencode_host.register(tmp_path/installer.NAME)
    assert '"document_analysis"' in str(error.value)
    assert opencode.read_text(encoding='utf-8') == text


def test_commented_jsonc_is_left_alone_and_merged_by_opencode(source, opencode, tmp_path):
    opencode.parent.mkdir(parents=True)
    commented = opencode.with_name('opencode.jsonc')
    text = '{\n  // Azure resource name\n  "providers": {"azure": {"settings": {"resourceName": "x"}}},\n}\n'
    commented.write_text(text, encoding='utf-8')
    assert opencode_host.install(tmp_path/'installed') == 'installed'
    assert commented.read_text(encoding='utf-8') == text
    assert opencode_host.installed_target() == tmp_path/'installed'/'opencode'/installer.NAME
    commented.write_text('{\n  // mine\n  "mcp": {"servers": {"document_analysis": {"type": "local", "command": ["x"]}}},\n}\n',
                         encoding='utf-8')
    with pytest.raises(RuntimeError, match='also defines document_analysis'):
        opencode_host.install(tmp_path/'installed', repair=True)


def test_install_noop_repair_and_managed_updates(source, opencode, tmp_path):
    base = tmp_path/'installed'
    assert opencode_host.install(base) == 'installed'
    target = base/'opencode'/installer.NAME
    assert opencode_host.installed_target() == target
    assert read_json(target/installer.MARKER)['host'] == 'opencode'
    assert updater.managed_install(target)['target'] == str(target)
    assert not opencode.with_name('opencode.json.sda-backup').exists()
    assert opencode_host.install(base) == 'already up to date'
    (target/'README.md').write_text('local change')
    with pytest.raises(RuntimeError, match='Same version'):
        opencode_host.install(base)
    assert opencode_host.install(base, repair=True) == 'installed'
    backup = next((target.parent/'backups').glob('*/'+installer.NAME))
    assert (backup/'README.md').read_text() == 'local change'
    assert list(opencode.parent.glob('opencode.json.sda-backup-*'))


def test_foreign_server_entry_needs_explicit_replacement(source, opencode, tmp_path):
    opencode.parent.mkdir(parents=True)
    foreign = {'mcp': {'servers': {'document_analysis': {'type': 'local', 'command': ['python', 'other.py']}}}}
    opencode.write_text(json.dumps(foreign), encoding='utf-8')
    with pytest.raises(RuntimeError, match='No files changed'):
        opencode_host.install(tmp_path/'installed')
    assert json.loads(opencode.read_text(encoding='utf-8')) == foreign
    assert not (tmp_path/'installed'/'opencode'/installer.NAME).exists()
    assert opencode_host.install(tmp_path/'installed', replace_source=True) == 'installed'


def test_failed_registration_restores_files_and_config(source, opencode, tmp_path, monkeypatch):
    base = tmp_path/'installed'
    opencode_host.install(base)
    target = base/'opencode'/installer.NAME
    before = opencode.read_bytes()
    (target/'README.md').write_text('previous')
    monkeypatch.setattr(opencode_host, 'register', lambda target: (_ for _ in ()).throw(OSError('disk full')))
    with pytest.raises(RuntimeError, match='restored'):
        opencode_host.install(base, repair=True)
    assert opencode.read_bytes() == before
    assert (target/'README.md').read_text() == 'previous'
    assert not installer.journal_path(target).exists()


def test_interrupted_install_is_recovered_without_deleting(source, opencode, tmp_path, monkeypatch):
    base = tmp_path/'installed'
    opencode_host.install(base)
    target = base/'opencode'/installer.NAME
    before = opencode.read_bytes()
    (target/'README.md').write_text('previous')
    original = opencode_host.register

    def killed(new_target):
        original(new_target)
        raise Killed()
    monkeypatch.setattr(opencode_host, 'register', killed)
    with pytest.raises(Killed):
        opencode_host.install(base, repair=True)
    assert installer.journal_path(target).exists()
    with pytest.raises(RuntimeError, match='recovery'):
        opencode_host.install(base, repair=True)
    assert opencode_host.recover(base) == 'recovered previous installation'
    assert opencode.read_bytes() == before
    assert (target/'README.md').read_text() == 'previous'
    assert list(target.parent.glob('failed-install-*')) and list(target.parent.glob('recovery-*.json'))


def test_managed_update_replaces_the_opencode_copy(source, opencode, tmp_path, monkeypatch):
    base = tmp_path/'installed'
    opencode_host.install(base)
    target = base/'opencode'/installer.NAME
    set_version(source, '99.0.0')
    fake_download(monkeypatch, release_payload(source))
    with maintenance_lock():
        assert updater.apply_release(updater.managed_install(target), release_info('99.0.0'))
    assert installer.version(target) == '99.0.0'
    assert opencode_host.installed_target() == target


def test_prepare_timeout_is_not_an_installation_failure(tmp_path):
    target = tmp_path/installer.NAME
    (target/'bin').mkdir(parents=True)
    (target/'bin'/'start_server.py').write_text('import time; time.sleep(60)', encoding='utf-8')
    assert opencode_host.prepare_runtime(target, timeout=2) is False


def test_prepare_only_builds_the_separate_opencode_environment(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('bootstrap_prepare', Path(__file__).resolve().parents[1]/'bin'/'start_server.py')
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    seen = []
    monkeypatch.setattr(bootstrap, 'prepare', lambda root, data: seen.append(data))
    monkeypatch.delenv('CLAUDE_PLUGIN_DATA', raising=False)
    monkeypatch.setenv('SDA_PLUGIN_DATA', str(tmp_path/'opencode-runtime'))
    monkeypatch.setattr(sys, 'argv', ['start_server.py', '--prepare-only'])
    assert bootstrap.main() == 0
    assert seen == [tmp_path/'opencode-runtime']
