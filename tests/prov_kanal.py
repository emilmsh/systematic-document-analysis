"""Install from the published release channel with the real host CLIs in temporary profiles. No models.

Requires the `stable` branch on GitHub. An earlier local installation
(`systematic-document-analysis-local`) is registered first to check the switch.
Both launchers are then started as each host would start them.
"""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

NAME = 'systematic-document-analysis'
SELECTOR = f'{NAME}@{NAME}'
LEGACY = f'{NAME}-local'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'bin'))


def cli(env, *args):
    return subprocess.run(list(args), env=env, check=True, timeout=240, capture_output=True, encoding='utf-8').stdout


def installer(env, *args):
    return subprocess.run([sys.executable, '-X', 'utf8', str(ROOT/'bin/installer.py'), *args],
                          env=env, check=True, timeout=600)


def legacy_package(base):
    """An earlier-style local copy under the old marketplace name."""
    from pakk_plugin import pakk
    copy = base/'legacy'/NAME
    pakk(copy)
    market = json.loads((copy/'.claude-plugin/marketplace.json').read_text(encoding='utf-8'))
    market['name'] = LEGACY
    (copy/'.claude-plugin/marketplace.json').write_text(json.dumps(market, indent=2), encoding='utf-8')
    return copy


async def start(command, args, cwd, env):
    params = StdioServerParameters(command=command, args=args, cwd=str(cwd), env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            info = await session.initialize()
            return info.server_info.version, len((await session.list_tools()).tools)


def main():
    with tempfile.TemporaryDirectory(prefix='sda-kanal-') as temp:
        base = Path(temp)
        env = dict(os.environ, CODEX_HOME=str(base/'codex-home'), CLAUDE_CONFIG_DIR=str(base/'claude-home'),
                   SDA_MAINTENANCE_DIR=str(base/'maintenance'), SDA_DATA=str(base/'data'),
                   SDA_PROJECTS_ROOT=str(base/'projects'), SDA_PYTHON=sys.executable)
        (base/'codex-home').mkdir()
        (base/'claude-home').mkdir()
        old = legacy_package(base)
        for host, install in (('codex', ['plugin', 'add', f'{NAME}@{LEGACY}']),
                              ('claude', ['plugin', 'install', f'{NAME}@{LEGACY}', '--scope', 'user'])):
            cli(env, host, 'plugin', 'marketplace', 'add', str(old))
            cli(env, host, *install)
        for round_ in range(2):
            print(f'Kanalinstallasjon, runde {round_ + 1}', flush=True)
            installer(env, 'begge', '--non-interactive', '--reader', 'none', '--skip-ocr')
        claude = json.loads(cli(env, 'claude', 'plugin', 'list', '--json'))
        entry = next(p for p in claude if p['id'] == SELECTOR)
        assert entry['enabled'] and not any(p['id'].endswith('@' + LEGACY) for p in claude)
        settings = json.loads((base/'claude-home/settings.json').read_text(encoding='utf-8'))
        declared = settings['extraKnownMarketplaces'][NAME]
        assert declared['source'] == {'source': 'github', 'repo': 'emilmsh/systematic-document-analysis', 'ref': 'stable'}
        assert declared['autoUpdate'] is True
        codex = json.loads(cli(env, 'codex', 'plugin', 'list', '--json'))
        installed = next(p for p in codex['installed'] if p.get('pluginId') == SELECTOR)
        assert installed['enabled'] and not any(p.get('marketplaceName') == LEGACY for p in codex['installed'])
        config = tomllib.loads((base/'codex-home/config.toml').read_text(encoding='utf-8'))
        assert config['marketplaces'][NAME]['ref'] == 'stable' and LEGACY not in config['marketplaces']
        assert (old/'README.md').exists(), 'the earlier copy must be kept'

        claude_root = Path(entry['installPath'])
        launcher = json.loads((claude_root/'.mcp.json').read_text(encoding='utf-8'))['mcpServers']['document_analysis']
        args = [a.replace('${CLAUDE_PLUGIN_ROOT}', str(claude_root)) for a in launcher['args']]
        version, tools = asyncio.run(start(launcher['command'], args, claude_root,
                                           dict(env, CLAUDE_PLUGIN_ROOT=str(claude_root), CLAUDE_PLUGIN_DATA=str(base/'claude-data'))))
        print(f'Claude-start: {version}, {tools} verktøy fra {claude_root}', flush=True)
        codex_root = Path(installed.get('installedPath') or next((base/'codex-home/plugins/cache'/NAME/NAME).iterdir()))
        server = json.loads((codex_root/'.codex-mcp.json').read_text(encoding='utf-8'))['mcpServers']['document_analysis']
        version_codex, tools_codex = asyncio.run(start(server['command'], server['args'], codex_root/server['cwd'],
                                                       dict(env, **server.get('env', {}), CLAUDE_PLUGIN_DATA=str(base/'codex-data'))))
        print(f'Codex-start: {version_codex}, {tools_codex} verktøy fra {codex_root}', flush=True)
        assert version == version_codex == entry['version'] and tools == tools_codex

        updater = [sys.executable, '-X', 'utf8', str(ROOT/'bin/update_plugin.py')]
        subprocess.run([*updater, '--mode', 'off'], env=env, check=True, timeout=240)
        settings = json.loads((base/'claude-home/settings.json').read_text(encoding='utf-8'))
        assert settings['extraKnownMarketplaces'][NAME]['autoUpdate'] is False
        subprocess.run([*updater, '--check', '--install', '--mode', 'auto'], env=env, check=True, timeout=600)
        settings = json.loads((base/'claude-home/settings.json').read_text(encoding='utf-8'))
        assert settings['extraKnownMarketplaces'][NAME]['autoUpdate'] is True
        print('BESTÅTT: kanalinstallasjon i begge CLI-er, bytte fra tidligere lokal kopi, automatisk oppdatering av/på, '
              'begge oppstarter; kun midlertidige profiler.', flush=True)


if __name__ == '__main__':
    main()
