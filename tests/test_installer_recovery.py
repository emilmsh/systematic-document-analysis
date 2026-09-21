"""Forced interruption at every installer step, then journal-based recovery.

A forced kill is modelled as a BaseException that the installer's ordinary
rollback (except Exception) cannot catch, exactly like a terminated process:
the pending-install.json journal stays behind. No network or real profiles.
"""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'bin'))
import installer
from kildeanalyse.maintenance import read_json, write_json
from test_installer_updates import Host, set_version, source  # noqa: F401  (fixture)


class Killed(BaseException):
    """Stands in for a process terminated by the user or the OS."""


def arm_kill(monkeypatch, step):
    """Terminate at the n-th file move or host command; later ticks are harmless."""
    counter = {'n':0}

    def tick():
        counter['n'] += 1
        if counter['n'] == step:
            raise Killed(step)
    original_rename = Path.rename
    monkeypatch.setattr(Path, 'rename', lambda self, target: (tick(), original_rename(self, target))[1])
    for name in ('remove_plugin', 'register_plugin', 'run', 'inspect'):
        original = getattr(installer, name)

        def wrapped(*args, _original=original, **kwargs):
            tick()
            return _original(*args, **kwargs)
        monkeypatch.setattr(installer, name, wrapped)
    return counter


def journal(base, host='codex'):
    return base/host/'pending-install.json'


def receipts(base, host='codex'):
    return sorted((base/host).glob('recovery-*.json'))


def failed_copies(base, host='codex'):
    return sorted((base/host).glob('failed-install-*'))


STEPS = range(1, 12)


@pytest.mark.parametrize('host_name', ['codex', 'claude'])
@pytest.mark.parametrize('step', STEPS)
def test_upgrade_interrupted_at_any_step_recovers_previous_or_completed_state(source, tmp_path, monkeypatch, step, host_name):
    host = Host(monkeypatch, host_name)
    base = tmp_path/'installed'
    assert installer.install(host_name, base) == 'installed'
    target = base/host_name/installer.NAME
    old_version = installer.version(target)
    old_hash = installer.package_hash(target)
    set_version(source, '99.0.0')
    arm_kill(monkeypatch, step)
    try:
        result = installer.install(host_name, base)
    except Killed:
        result = 'killed'
    if result == 'installed':
        assert not journal(base, host_name).exists()
        assert installer.version(target) == '99.0.0'
        return
    assert result == 'killed'
    if not journal(base, host_name).exists():
        # Terminated during preflight: nothing had changed yet.
        assert installer.version(target) == old_version and host.plugin['version'] == old_version
        return
    with pytest.raises(RuntimeError, match='--recover'):
        installer.install(host_name, base)
    outcome = installer.recover(host_name, base)
    assert not journal(base, host_name).exists()
    receipt = read_json(receipts(base, host_name)[0])
    assert receipt['result'] == outcome and receipt['record']['previous_version'] == old_version
    assert host.source == target and host.plugin and host.plugin['enabled']
    if outcome == 'recovered completed installation':
        assert installer.version(target) == '99.0.0' and host.plugin['version'] == '99.0.0'
        assert any(installer.version(b) == old_version for b in (base/host_name/'backups').glob('*/'+installer.NAME))
    else:
        assert outcome == 'recovered previous installation'
        assert installer.version(target) == old_version and host.plugin['version'] == old_version
        assert installer.package_hash(target) == old_hash
        assert all(installer.version(f) == '99.0.0' for f in failed_copies(base, host_name))
        assert installer.install(host_name, base) == 'installed'
        assert installer.version(target) == '99.0.0'
    assert installer.install(host_name, base) == 'already up to date'


@pytest.mark.parametrize('step', STEPS)
def test_source_switch_interrupted_restores_old_marketplace(source, tmp_path, monkeypatch, step):
    host = Host(monkeypatch)
    original = tmp_path/'old'; replacement = tmp_path/'new'
    installer.install('codex', original)
    old_source = host.source
    old_bytes = (old_source/installer.MARKER).read_bytes()
    arm_kill(monkeypatch, step)
    try:
        result = installer.install('codex', replacement, replace_source=True)
    except Killed:
        result = 'killed'
    if result == 'installed':
        assert host.source == replacement/'codex'/installer.NAME
        return
    if not journal(replacement).exists():
        assert host.source == old_source
        return
    outcome = installer.recover('codex', replacement)
    if outcome == 'recovered completed installation':
        assert host.source == replacement/'codex'/installer.NAME
    else:
        assert host.source == old_source and host.plugin['enabled']
        assert (old_source/installer.MARKER).read_bytes() == old_bytes
        assert not (replacement/'codex'/installer.NAME).exists()
        assert installer.install('codex', replacement, replace_source=True) == 'installed'
    assert not journal(replacement).exists() and receipts(replacement)


@pytest.mark.parametrize('step', STEPS)
def test_fresh_install_interrupted_leaves_nothing_registered(source, tmp_path, monkeypatch, step):
    host = Host(monkeypatch)
    base = tmp_path/'installed'
    arm_kill(monkeypatch, step)
    try:
        result = installer.install('codex', base)
    except Killed:
        result = 'killed'
    if result == 'installed' or not journal(base).exists():
        return
    outcome = installer.recover('codex', base)
    target = base/'codex'/installer.NAME
    if outcome == 'recovered completed installation':
        assert host.source == target and host.plugin
    else:
        assert host.source is None and host.plugin is None
        assert not target.exists()
        assert installer.install('codex', base) == 'installed'
    assert not journal(base).exists()


def test_record_from_release_0_8_2_without_new_fields_is_recovered(source, tmp_path, monkeypatch):
    host = Host(monkeypatch)
    base = tmp_path/'installed'
    installer.install('codex', base)
    target = base/'codex'/installer.NAME
    old_version = installer.version(target)
    set_version(source, '99.0.0')
    arm_kill(monkeypatch, 6)  # New copy in place and plugin removed; killed before re-registration.
    with pytest.raises(Killed):
        installer.install('codex', base)
    record = read_json(journal(base))
    assert installer.version(target) == '99.0.0' and host.plugin is None
    legacy = {key:record[key] for key in ('target', 'backup', 'old_source', 'host', 'previous_version')}
    write_json(journal(base), legacy)
    assert installer.recover('codex', base) == 'recovered previous installation'
    assert installer.version(target) == old_version
    assert host.source == target and host.plugin['version'] == old_version
    assert len(failed_copies(base)) == 1


def test_recovery_refuses_missing_or_foreign_records_and_never_deletes(source, tmp_path, monkeypatch):
    Host(monkeypatch)
    base = tmp_path/'installed'
    with pytest.raises(RuntimeError, match='Nothing to recover'):
        installer.recover('codex', base)
    installer.install('codex', base)
    target = base/'codex'/installer.NAME
    write_json(journal(base), {'target':str(tmp_path/'elsewhere'/installer.NAME), 'host':'codex'})
    with pytest.raises(RuntimeError, match='another installation'):
        installer.recover('codex', base)
    write_json(journal(base), {'target':str(target), 'backup':str(tmp_path/'outside'), 'host':'codex'})
    with pytest.raises(RuntimeError, match='outside the installation folder'):
        installer.recover('codex', base)
    assert journal(base).exists() and installer.version(target)


def test_recovery_stops_when_previous_files_are_missing(source, tmp_path, monkeypatch):
    Host(monkeypatch)
    base = tmp_path/'installed'
    installer.install('codex', base)
    target = base/'codex'/installer.NAME
    write_json(journal(base), {'target':str(target), 'backup':str(target.parent/'backups/x'/installer.NAME),
                               'old_source':str(target), 'host':'codex', 'previous_version':'0.1.0', 'target_existed':True})
    target.rename(target.parent/'moved-away')
    with pytest.raises(RuntimeError, match='Restore the files manually'):
        installer.recover('codex', base)
    assert journal(base).exists()
