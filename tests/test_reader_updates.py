"""Reader updates are explicit and never replace another installer's executable."""
import hashlib
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bin'))
import setup_reader


def test_claude_update_uses_selected_binary_and_verifies_version(monkeypatch):
    commands = []
    versions = iter(['2.1.274 (Claude Code)', '2.1.280 (Claude Code)'])
    monkeypatch.setattr(setup_reader, 'install', lambda name: 'C:/selected/claude.exe')
    monkeypatch.setattr(setup_reader, 'cli_version', lambda binary: next(versions))
    monkeypatch.setattr(setup_reader.subprocess, 'run',
                        lambda command, **kwargs: commands.append((command, kwargs)) or
                        subprocess.CompletedProcess(command, 0))
    assert setup_reader.update('claude') == 'C:/selected/claude.exe'
    assert commands[0][0] == ['C:/selected/claude.exe', 'update']


def test_other_codex_install_is_not_replaced(monkeypatch, tmp_path, capsys):
    external = tmp_path/'Codex-app/codex.exe'
    external.parent.mkdir()
    external.write_bytes(b'external')
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.setattr(setup_reader, 'install', lambda name: str(external))
    monkeypatch.setattr(setup_reader, 'cli_version', lambda binary: 'codex-cli 0.155.0')
    monkeypatch.setattr(setup_reader, 'latest_codex_asset',
                        lambda: pytest.fail('Must not fetch an update for an external CLI'))
    assert setup_reader.update('codex') == str(external)
    assert external.read_bytes() == b'external'
    assert 'No executable was replaced' in capsys.readouterr().out


def test_managed_codex_update_checks_digest_and_keeps_backup_until_verified(monkeypatch, tmp_path):
    target = tmp_path/'systematic-document-analysis/readers/codex/codex.exe'
    target.parent.mkdir(parents=True)
    target.write_bytes(b'old')
    payload = b'new verified codex binary'
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.setattr(setup_reader, 'install', lambda name: str(target))
    monkeypatch.setattr(setup_reader, 'latest_codex_asset',
                        lambda: ('rust-v9.9.9', 'https://example.test/codex.exe', hashlib.sha256(payload).hexdigest()))
    monkeypatch.setattr(setup_reader.urllib.request, 'urlretrieve',
                        lambda url, path: Path(path).write_bytes(payload))
    monkeypatch.setattr(setup_reader, 'cli_version',
                        lambda binary: 'codex-cli 9.9.9' if target.read_bytes() == payload else 'codex-cli 0.1.0')
    assert setup_reader.update('codex') == str(target)
    assert target.read_bytes() == payload
    assert not target.with_suffix('.backup').exists()


def test_managed_codex_bad_checksum_preserves_original(monkeypatch, tmp_path):
    target = tmp_path/'systematic-document-analysis/readers/codex/codex.exe'
    target.parent.mkdir(parents=True)
    target.write_bytes(b'old')
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.setattr(setup_reader, 'install', lambda name: str(target))
    monkeypatch.setattr(setup_reader, 'cli_version', lambda binary: 'codex-cli 0.1.0')
    monkeypatch.setattr(setup_reader, 'latest_codex_asset',
                        lambda: ('rust-v9.9.9', 'https://example.test/codex.exe', '0'*64))
    monkeypatch.setattr(setup_reader.urllib.request, 'urlretrieve',
                        lambda url, path: Path(path).write_bytes(b'unverified'))
    with pytest.raises(RuntimeError, match='checksum mismatch'):
        setup_reader.update('codex')
    assert target.read_bytes() == b'old'
    assert not target.with_suffix('.download').exists()


def test_managed_codex_current_version_skips_download(monkeypatch, tmp_path):
    target = tmp_path/'systematic-document-analysis/readers/codex/codex.exe'
    target.parent.mkdir(parents=True)
    target.write_bytes(b'current')
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    monkeypatch.setattr(setup_reader, 'install', lambda name: str(target))
    monkeypatch.setattr(setup_reader, 'cli_version', lambda binary: 'codex-cli 0.156.1')
    monkeypatch.setattr(setup_reader, 'latest_codex_asset',
                        lambda: ('rust-v0.156.1', 'https://example.test/codex.exe', '0'*64))
    monkeypatch.setattr(setup_reader.urllib.request, 'urlretrieve',
                        lambda url, path: pytest.fail('Current release must not be downloaded'))
    assert setup_reader.update('codex') == str(target)
    assert target.read_bytes() == b'current'


def test_reader_update_is_separate_from_login(monkeypatch):
    calls = []
    monkeypatch.setattr(sys, 'argv', ['setup_reader.py', 'claude', '--update'])
    monkeypatch.setattr(setup_reader, 'update', lambda name: calls.append(name))
    setup_reader.main()
    assert calls == ['claude']
    monkeypatch.setattr(sys, 'argv', ['setup_reader.py', 'claude', '--update', '--login'])
    with pytest.raises(SystemExit, match='2'):
        setup_reader.main()
