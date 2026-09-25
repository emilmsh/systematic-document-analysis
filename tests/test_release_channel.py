"""GitHub release channel: host-managed installs and updates, without network or real profiles."""
import json
from pathlib import Path
import subprocess
import sys
import tomllib

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'bin'))
import installer
import lag_stable
import pakk_plugin
import update_plugin as updater
from kildeanalyse.maintenance import read_json, write_json


class ChannelHost:
    """Fake Claude/Codex CLI that records marketplaces the way each host declares them."""

    def __init__(self, monkeypatch, tmp_path, host):
        self.host = host
        self.markets = {}
        self.plugins = set()
        self.commands = []
        self.claude_settings = tmp_path/'claude'/'settings.json'
        self.codex_config = tmp_path/'codex'/'config.toml'
        monkeypatch.setenv('CLAUDE_CONFIG_DIR', str(self.claude_settings.parent))
        monkeypatch.setenv('CODEX_HOME', str(self.codex_config.parent))
        monkeypatch.setattr(installer, 'ensure_reader', lambda host: 'fake-cli')
        monkeypatch.setattr(installer, 'query', self.query)
        monkeypatch.setattr(installer, 'run', self.run)

    def local(self, name, path):
        """An existing registration of a local directory, as earlier releases made."""
        self.markets[name] = {'source': 'directory', 'path': str(path)}
        self.plugins.add(name)

    def query(self, command):
        args = command[1:]
        if args[:3] == ['plugin', 'marketplace', 'list']:
            if self.host == 'codex':
                return {'marketplaces': [{'name': n, 'root': m.get('path', 'snapshot')} for n, m in self.markets.items()]}
            return [{'name': n, **m} for n, m in self.markets.items()]
        assert args[:2] == ['plugin', 'list']
        if self.host == 'codex':
            return {'installed': [{'name': installer.NAME, 'marketplaceName': m, 'version': '0.12.0', 'enabled': True}
                                  for m in sorted(self.plugins)]}
        return [{'id': f'{installer.NAME}@{m}', 'scope': 'user', 'version': '0.12.0', 'enabled': True}
                for m in sorted(self.plugins)]

    def declare(self, name, source):
        if self.host == 'claude':
            settings = read_json(self.claude_settings)
            known = settings.setdefault('extraKnownMarketplaces', {})
            if source is None:
                known.pop(name, None)
            else:
                known[name] = {'source': source}
            write_json(self.claude_settings, settings)
        else:
            config = tomllib.loads(self.codex_config.read_text(encoding='utf-8')) if self.codex_config.exists() else {}
            markets = config.setdefault('marketplaces', {})
            if source is None:
                markets.pop(name, None)
            else:
                markets[name] = source
            self.codex_config.parent.mkdir(parents=True, exist_ok=True)
            self.codex_config.write_text(''.join(
                f'[marketplaces.{n}]\n' + ''.join(f'{k} = "{v}"\n' for k, v in entry.items())
                for n, entry in markets.items()), encoding='utf-8')

    def run(self, command):
        args = command[1:]
        self.commands.append(args)
        if args[:3] == ['plugin', 'marketplace', 'add']:
            name = installer.MARKET
            self.markets[name] = {'source': 'github'}
            if self.host == 'claude':
                repo, ref = args[3].split('#')
                self.declare(name, {'source': 'github', 'repo': repo, 'ref': ref})
            else:
                assert args[4] == '--ref'
                self.declare(name, {'source_type': 'git', 'source': f'https://github.com/{args[3]}.git', 'ref': args[5]})
        elif args[:3] == ['plugin', 'marketplace', 'remove']:
            self.markets.pop(args[3])
            self.plugins.discard(args[3])
            self.declare(args[3], None)
        elif args[:2] in (['plugin', 'remove'], ['plugin', 'uninstall']):
            self.plugins.discard(args[2].split('@')[1])
        elif args[:2] in (['plugin', 'add'], ['plugin', 'install']):
            self.plugins.add(args[2].split('@')[1])


@pytest.mark.parametrize('host_name', ['claude', 'codex'])
def test_fresh_install_follows_the_stable_channel(tmp_path, monkeypatch, host_name):
    host = ChannelHost(monkeypatch, tmp_path, host_name)
    assert installer.install_github(host_name) == 'installed'
    add = host.commands[0]
    if host_name == 'claude':
        assert add == ['plugin', 'marketplace', 'add', 'emilmsh/systematic-document-analysis#stable']
        assert installer.claude_auto_update() is True
    else:
        assert add == ['plugin', 'marketplace', 'add', 'emilmsh/systematic-document-analysis', '--ref', 'stable']
    assert installer.MARKET in host.plugins
    # A repeat refreshes the channel instead of registering it again.
    host.commands.clear()
    assert installer.install_github(host_name) == 'installed'
    assert ['plugin', 'marketplace', 'add'] not in [c[:3] for c in host.commands]
    refresh = ['plugin', 'marketplace', 'upgrade' if host_name == 'codex' else 'update', installer.MARKET]
    assert refresh in host.commands


@pytest.mark.parametrize('host_name', ['claude', 'codex'])
def test_earlier_local_installation_is_unregistered_but_kept(tmp_path, monkeypatch, host_name):
    host = ChannelHost(monkeypatch, tmp_path, host_name)
    old = tmp_path/'old-copy'
    old.mkdir()
    (old/'README.md').write_text('kept')
    host.local(installer.LEGACY_MARKET, old)
    assert installer.install_github(host_name) == 'installed'
    assert installer.LEGACY_MARKET not in host.markets and installer.LEGACY_MARKET not in host.plugins
    assert host.plugins == {installer.MARKET}
    assert (old/'README.md').read_text() == 'kept'


def test_other_source_under_the_same_name_needs_explicit_switch(tmp_path, monkeypatch):
    host = ChannelHost(monkeypatch, tmp_path, 'claude')
    host.local(installer.MARKET, tmp_path/'managed-copy')
    with pytest.raises(RuntimeError, match='Switch to automatic updates'):
        installer.install_github('claude')
    assert host.markets[installer.MARKET]['source'] == 'directory'
    assert installer.install_github('claude', replace_source=True) == 'installed'
    assert host.markets[installer.MARKET]['source'] == 'github'


def test_auto_update_switch_keeps_other_claude_settings(tmp_path, monkeypatch):
    ChannelHost(monkeypatch, tmp_path, 'claude')
    installer.install_github('claude')
    path = installer.claude_settings_path()
    settings = read_json(path)
    settings['model'] = 'keep-me'
    write_json(path, settings)
    installer.set_claude_auto_update(False)
    settings = read_json(path)
    assert settings['model'] == 'keep-me' and installer.claude_auto_update() is False
    assert settings['extraKnownMarketplaces'][installer.MARKET]['source']['ref'] == 'stable'


def test_update_menu_adjusts_the_host_channel(tmp_path, monkeypatch, capsys):
    host = ChannelHost(monkeypatch, tmp_path, 'claude')
    installer.install_github('claude')
    monkeypatch.setattr(updater, 'find_cli', lambda name: sys.executable)
    monkeypatch.setattr(updater, 'channel_installs', lambda: [('claude', 'fake-cli', {'version': '0.12.0'})])
    monkeypatch.setattr(updater, 'check', lambda force=False: {'message': 'ok', 'version': '0.12.1', 'url': 'u'})
    args = type('Args', (), {'mode': 'off', 'check': False, 'install': True})()
    host.commands.clear()
    assert updater.channel_updates(args, None) == 0
    assert installer.claude_auto_update() is False
    assert ['plugin', 'update', installer.SELECTOR, '--scope', 'user'] in host.commands
    assert 'automatic updates off' in capsys.readouterr().out


def test_codex_launcher_is_relative_and_local_copy_rewrites_it(tmp_path):
    root = Path(__file__).resolve().parents[1]
    manifest = read_json(root/'.codex-plugin/plugin.json')
    assert manifest['mcpServers'] == './.codex-mcp.json'
    assert manifest['interface']['logo'] == './assets/icon.svg'
    server = read_json(root/'.codex-mcp.json')['mcpServers']['document_analysis']
    assert server['cwd'] == '.' and server['args'][-1] == './bin/start_server.cmd'
    copy = tmp_path/installer.NAME
    pakk_plugin.pakk(copy, codex=True)
    local = read_json(copy/'.codex-mcp.json')['mcpServers']['document_analysis']
    assert 'cwd' not in local and local['args'][-1] == str(copy/'bin/start_server.py')
    assert local['env_vars'] == server['env_vars']


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, encoding='utf-8').stdout.strip()


def test_stable_branch_holds_exactly_the_release_package(tmp_path, monkeypatch):
    for key in ('GIT_AUTHOR_NAME', 'GIT_COMMITTER_NAME'):
        monkeypatch.setenv(key, 'Release test')
    for key in ('GIT_AUTHOR_EMAIL', 'GIT_COMMITTER_EMAIL'):
        monkeypatch.setenv(key, 'release@example.org')
    repo = tmp_path/'repo'/installer.NAME
    pakk_plugin.pakk(repo)
    (repo/'tests').mkdir()
    (repo/'tests'/'dev_only.py').write_text('not shipped')
    git(repo, 'init', '-q', '-b', 'main')
    git(repo, 'add', '-A')
    git(repo, '-c', 'user.name=t', '-c', 'user.email=t@example.org', 'commit', '-q', '-m', 'release')
    head = git(repo, 'rev-parse', 'HEAD')
    commit, changed = lag_stable.build(repo, require_release=False)
    assert changed and git(repo, 'rev-parse', 'HEAD') == head  # current branch untouched
    shipped = git(repo, 'ls-tree', '-r', '--name-only', 'stable').splitlines()
    assert sorted(shipped) == sorted(p.relative_to(repo).as_posix() for p in pakk_plugin.pakkefiler(repo))
    assert 'tests/dev_only.py' not in shipped and '.codex-mcp.json' in shipped
    marketplace = json.loads(git(repo, 'show', 'stable:.claude-plugin/marketplace.json'))
    assert marketplace['name'] == installer.MARKET
    assert lag_stable.build(repo, require_release=False) == (commit, False)
    with pytest.raises(RuntimeError, match='Tag v'):
        lag_stable.build(repo)


def test_host_copies_report_host_managed_updates(tmp_path, monkeypatch):
    import start_server
    from kildeanalyse.maintenance import update_status
    monkeypatch.setenv('CLAUDE_CONFIG_DIR', str(tmp_path/'claude'))
    monkeypatch.setenv('CODEX_HOME', str(tmp_path/'codex'))
    monkeypatch.setenv('SDA_MAINTENANCE_DIR', str(tmp_path/'maintenance'))
    monkeypatch.delenv('SDA_RELEASE_CHANNEL', raising=False)
    copy = tmp_path/'codex/plugins/cache'/installer.NAME/installer.NAME/'0.12.0'
    copy.mkdir(parents=True)
    assert start_server.host_cache(copy) and not start_server.host_cache(tmp_path)
    assert update_status()['mode'] == 'notify'
    monkeypatch.setenv('SDA_RELEASE_CHANNEL', '1')
    assert update_status()['mode'] == 'host'


def test_default_install_uses_the_channel_without_closing_sessions(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(installer, 'packaged_process', lambda: False)
    monkeypatch.setattr(installer, 'installation_lock', lambda **kw: pytest.fail('The channel must not close sessions'))
    monkeypatch.setattr(installer, 'install', lambda *a, **kw: pytest.fail('No local copy by default'))
    monkeypatch.setattr(installer, 'install_github', lambda host, **kw: calls.append((host, kw)) or 'installed')
    monkeypatch.setattr(installer, 'setup_local_ocr', lambda: calls.append('ocr'))
    monkeypatch.setattr(sys, 'argv', ['installer.py', 'both', '--non-interactive', '--reader', 'none'])
    assert installer.main() == 0
    assert [c[0] for c in calls[:2]] == ['claude', 'codex'] and calls[2] == 'ocr'
    assert calls[0][1] == {'replace_source': False, 'repair': False, 'interactive': False}
    monkeypatch.setattr(sys, 'argv', ['installer.py', 'codex', '--move-shadow', '--non-interactive'])
    with pytest.raises(SystemExit):
        installer.main()


def test_disabled_plugin_is_kept(tmp_path, monkeypatch):
    host = ChannelHost(monkeypatch, tmp_path, 'claude')
    installer.install_github('claude')
    listed = host.query
    monkeypatch.setattr(installer, 'query', lambda command: [dict(p, enabled=False) for p in listed(command)]
                        if command[1:3] == ['plugin', 'list'] else listed(command))
    host.commands.clear()
    assert installer.install_github('claude') == 'kept disabled installation'
    assert not any(c[:2] in (['plugin', 'install'], ['plugin', 'update']) for c in host.commands)
