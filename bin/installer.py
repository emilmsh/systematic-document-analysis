"""Install, update or repair the Windows plugin, preserving the previous copy."""
from __future__ import annotations
import argparse
import ast
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import tomllib
import uuid

from pakk_plugin import ROOT, pakk, pakkefiler, configure_codex
from setup_reader import install as ensure_reader
from setup_reader import setup as setup_subscription_reader
from setup_ocr import install as setup_local_ocr
from kildeanalyse.maintenance import PACKAGED_MESSAGE, maintenance_lock, installation_lock, packaged_process, read_json, write_json

NAME = 'systematic-document-analysis'
MARKET = 'systematic-document-analysis-local'
SELECTOR = f'{NAME}@{MARKET}'
MARKER = '.sda-install.json'


def local_path(value):
    value = str(value)
    if value.startswith('\\\\?\\UNC\\'):
        value = '\\\\' + value[8:]
    elif value.startswith('\\\\?\\'):
        value = value[4:]
    return Path(value).resolve()


def version(root):
    return tomllib.loads((Path(root)/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']


def version_key(value):
    match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:\+[A-Za-z0-9.-]+)?', value)
    if not match:
        raise ValueError(f'Not a stable release version: {value}')
    return tuple(map(int, match.groups()))


def package_hash(root):
    digest = hashlib.sha256()
    for path in pakkefiler(root):
        digest.update(path.relative_to(root).as_posix().encode('utf-8'))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def validate_package(root):
    expected = version(root)
    version_key(expected)
    for directory in ('.codex-plugin', '.claude-plugin'):
        manifest = read_json(Path(root)/directory/'plugin.json')
        if manifest.get('name') != NAME or version_key(manifest.get('version', '')) != version_key(expected):
            raise ValueError('Package name/version differs between pyproject.toml and plugin manifests.')
    marketplace = read_json(Path(root)/'.claude-plugin/marketplace.json')
    if marketplace.get('name') != MARKET or [p['name'] for p in marketplace.get('plugins', [])] != [NAME]:
        raise ValueError('Unexpected marketplace contents.')
    if marketplace['plugins'][0].get('version') != expected:
        raise ValueError('Marketplace version differs from pyproject.toml.')
    module = ast.parse((Path(root)/'src/kildeanalyse/__init__.py').read_text(encoding='utf-8-sig'))
    versions = [ast.literal_eval(node.value) for node in module.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == 'VERSJON' for target in node.targets)]
    if versions != [expected]:
        raise ValueError('Runtime version differs from pyproject.toml.')
    return expected


def prepare(host, base):
    """Explicit prepare-only helper; registration is handled by install()."""
    target = Path(base).resolve()/host/NAME
    pakk(target, codex=host == 'codex')
    return target


def run(command):
    print('Running: ' + subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, check=True, timeout=120, stdout=sys.stdout, stderr=sys.stderr)


def query(command):
    return json.loads(subprocess.check_output(command, encoding='utf-8', timeout=60))


def inspect(host, exe):
    markets = query([exe, 'plugin', 'marketplace', 'list', '--json'])
    plugins = query([exe, 'plugin', 'list', '--json'])
    if host == 'codex':
        market = next((m for m in markets['marketplaces'] if m['name'] == MARKET), None)
        plugin = next((p for p in plugins['installed'] if p.get('name') == NAME and
                       p.get('marketplaceName', p.get('marketplace')) == MARKET), None)
        # Listing gives the resolved root, not Git/local origin. Read only this
        # entry; all registration changes still go through the vendor CLI.
        config_path = Path(os.environ.get('CODEX_HOME', Path.home()/'.codex'))/'config.toml'
        config = tomllib.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
        entry = config.get('marketplaces', {}).get(MARKET, {})
        source = entry.get('source') if entry.get('source_type') == 'local' else None
        if market and not entry:
            source = market.get('root')
    else:
        market = next((m for m in markets if m['name'] == MARKET), None)
        matches = [p for p in plugins if p.get('id') == SELECTOR]
        if any(p.get('scope') != 'user' for p in matches):
            raise RuntimeError('This plugin also has a project/local installation. Manage that scope in Claude first.')
        plugin = next(iter(matches), None)
        source = market.get('path') if market and market.get('source') == 'directory' else None
    return market, local_path(source) if source else None, plugin


def confirm(message, *, allowed=False, interactive=False):
    if allowed:
        return True
    if not interactive:
        raise RuntimeError(message + ' No files changed. Use the explicit option shown above or run installer.cmd interactively.')
    return input(message + ' [y/N]: ').strip().lower() in ('y', 'yes', 'j', 'ja')


def remove_plugin(host, exe):
    if host == 'codex':
        run([exe, 'plugin', 'remove', SELECTOR])
    else:
        run([exe, 'plugin', 'uninstall', SELECTOR, '--scope', 'user', '--keep-data'])


def register_plugin(host, exe, *, reinstall=False):
    if reinstall:
        remove_plugin(host, exe)
    if host == 'codex':
        run([exe, 'plugin', 'add', SELECTOR])
    else:
        run([exe, 'plugin', 'install', SELECTOR, '--scope', 'user'])
        run([exe, 'plugin', 'update', SELECTOR, '--scope', 'user'])


def codex_shadows(target):
    """Stale copies the packaged Codex desktop app would read instead of the target.

    The Store/MSIX Codex app redirects writes below LOCALAPPDATA into its
    LocalCache and reads a merged view in which those files win. A plugin copy
    installed from inside a Codex conversation therefore masks the registered
    installation for the desktop app, even after the real files are replaced.
    """
    local = os.environ.get('LOCALAPPDATA')
    if not local or os.name != 'nt':
        return []
    local = Path(local).resolve()
    if not target.is_relative_to(local):
        return []
    relative = target.relative_to(local)
    return sorted(p for p in (local/'Packages').glob('OpenAI.Codex_*/LocalCache/Local')
                  for p in [p/relative] if p.exists() and p != target)


def move_codex_shadows(shadows, version_hint):
    moved = []
    for shadow in shadows:
        aside = shadow.with_name(f'{shadow.name}.shadow-{version_hint}-{uuid.uuid4().hex[:8]}')
        shadow.rename(aside)
        moved.append(aside)
    return moved


def install(host, base, *, replace_source=False, repair=False, allow_downgrade=False,
            move_shadow=False, interactive=False, locked=False):
    if packaged_process():
        raise RuntimeError(PACKAGED_MESSAGE)
    with nullcontext() if locked else maintenance_lock():
        return _install(host, base, replace_source=replace_source, repair=repair,
                        allow_downgrade=allow_downgrade, move_shadow=move_shadow, interactive=interactive)


def _install(host, base, *, replace_source, repair, allow_downgrade, move_shadow, interactive):
    incoming = validate_package(ROOT)
    target = Path(base).resolve()/host/NAME
    if target == ROOT or ROOT.is_relative_to(target) or target.is_relative_to(ROOT):
        raise RuntimeError('Use an installation folder separate from the source package.')
    if target.is_symlink() or target.is_junction():
        raise RuntimeError('The install target is a link/junction. Choose a regular installation directory.')
    if target.resolve() != target:
        raise RuntimeError('An installation parent is a link/junction. Choose a regular installation directory.')
    transaction = journal_path(target)
    if transaction.exists():
        raise RuntimeError(f'An interrupted installation needs recovery; see {transaction}. '
                           f'Run installer.cmd {host} --recover. No new changes made.')
    exe = ensure_reader(host)
    market, old_source, plugin = inspect(host, exe)
    if market and old_source is None:
        raise RuntimeError('This marketplace uses a remote or unknown source. Manage it in the host app; no files changed.')
    switching = bool(market and old_source != target)
    if switching:
        print(f'{host}: existing source: {old_source}\nNew source: {target}\nOption: --replace-source')
        old_market = read_json(old_source/'.claude-plugin/marketplace.json')
        if old_market.get('name') != MARKET or [p['name'] for p in old_market.get('plugins', [])] != [NAME]:
            raise RuntimeError('Cannot safely replace a marketplace containing other plugins or an unreadable source.')
        if not confirm('Switch to this installation? The previous source folder is kept.',
                       allowed=replace_source, interactive=interactive):
            return 'kept existing source'
    if plugin and plugin.get('enabled') is False:
        print(f'{host}: plugin is disabled. Enable it in the host before updating; installation preserved.')
        return 'kept disabled installation'
    installed_version = (plugin or {}).get('version')
    previous_root = old_source if old_source and old_source.exists() else target
    if not installed_version and (previous_root/'pyproject.toml').exists():
        installed_version = version(previous_root)
    print(f'{host}: installed {installed_version or "none"}; package {incoming}')
    if installed_version and version_key(installed_version) > version_key(incoming):
        print('Option: --allow-downgrade')
        if not confirm('A newer version is installed. Downgrade explicitly?',
                       allowed=allow_downgrade, interactive=interactive):
            return 'kept newer version'
    wanted_hash = package_hash(ROOT)
    if target.exists() and not switching:
        try:
            record = read_json(target/MARKER)
            if not isinstance(record, dict):
                raise ValueError('Invalid installation record')
            identical = (record.get('package_sha256') == wanted_hash and
                         record.get('installed_sha256') == package_hash(target))
        except (OSError, ValueError):
            record = {}
            identical = False
        if (identical and plugin and record.get('target') == str(target) and not repair
                and installed_version and version_key(installed_version) == version_key(incoming)):
            print(f'{host}: already up to date. Use --repair to reinstall.')
            return 'already up to date'
        if not identical and installed_version and version_key(installed_version) == version_key(incoming) and not repair:
            print('Option: --repair')
            if not confirm('Same version, different files. Repair with this package?', interactive=interactive):
                return 'kept existing files'

    shadows = codex_shadows(target) if host == 'codex' else []
    if shadows:
        for shadow in shadows:
            shadow_version = version(shadow) if (shadow/'pyproject.toml').exists() else 'unknown version'
            print(f'{host}: the Codex desktop app reads a shadow copy ({shadow_version}) that masks this installation:\n{shadow}')
        print('Option: --move-shadow')
        if not confirm('Move the shadow copy aside (kept, not deleted) so the desktop app uses this installation?',
                       allowed=move_shadow, interactive=interactive):
            return 'kept shadow copy'

    # Complete preflight before copying; stage the full package before switching.
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = target.parent/'backups'/uuid.uuid4().hex/NAME
    if not backup.resolve().is_relative_to(target.parent):
        raise RuntimeError('The backup directory points outside the installation folder.')
    with tempfile.TemporaryDirectory(prefix='.sda-stage-', dir=target.parent) as temporary:
        staged = Path(temporary)/NAME
        pakk(staged, codex=False, root=ROOT)
        if host == 'codex':
            configure_codex(staged, launch_root=target)
        write_json(staged/MARKER, {'host':host, 'base':str(Path(base).resolve()), 'target':str(target),
                                 'version':incoming, 'package_sha256':wanted_hash,
                                 'installed_sha256':package_hash(staged)})
        validate_package(staged)
        # The journal describes the state before any change, so --recover can
        # restore it after a forced interruption at any later step.
        write_json(transaction, {'target':str(target), 'backup':str(backup), 'old_source':str(old_source) if old_source else None,
                                 'host':host, 'previous_version':installed_version,
                                 'target_existed':target.exists(), 'plugin_registered':bool(plugin),
                                 'incoming_version':incoming, 'incoming_sha256':wanted_hash,
                                 'started_at':time.time()})
        moved = False
        placed = False
        registered_new = False
        removed_old = False
        touched_plugin = False
        try:
            if target.exists():
                backup.parent.mkdir(parents=True)
                target.rename(backup)
                moved = True
            staged.rename(target)
            placed = True
            if plugin:
                touched_plugin = True
                remove_plugin(host, exe)
            if switching:
                run([exe, 'plugin', 'marketplace', 'remove', MARKET])
                removed_old = True
            if not market or switching:
                run([exe, 'plugin', 'marketplace', 'add', str(target)])
                registered_new = True
            elif host == 'claude':
                run([exe, 'plugin', 'marketplace', 'update', MARKET])
            touched_plugin = True
            register_plugin(host, exe)
            _, actual_source, actual = inspect(host, exe)
            if actual_source != target or not actual or actual.get('enabled') is False:
                raise RuntimeError('The host did not report the expected enabled plugin after installation.')
            if actual.get('version') and version_key(actual['version']) != version_key(incoming):
                raise RuntimeError('The host still reports a different plugin version.')
        except Exception as failure:
            try:
                # Preserve the failed copy for diagnosis; never recursively delete
                # an existing installation or its settings/data during recovery.
                if placed:
                    target.rename(target.parent/f'failed-install-{uuid.uuid4().hex}')
                if moved:
                    backup.rename(target)
                if touched_plugin and inspect(host, exe)[2]:
                    remove_plugin(host, exe)
                if registered_new:
                    run([exe, 'plugin', 'marketplace', 'remove', MARKET])
                if removed_old:
                    run([exe, 'plugin', 'marketplace', 'add', str(old_source)])
                if plugin:
                    register_plugin(host, exe)
                transaction.unlink()
            except Exception as recovery:
                raise RuntimeError(f'Installation failed: {failure}. Recovery also failed: {recovery}. Recovery record: {transaction}') from failure
            raise RuntimeError(f'Installation failed; previous source/files restored: {failure}') from failure
        transaction.unlink()
    print(f'{host}: installed {incoming}. Start a new conversation to load the plugin.')
    if moved:
        print(f'Previous copy kept at: {backup}')
    print(f'Updates: notify by default; run "{target / "installer.cmd"}" update to change this.')
    if shadows:
        try:
            for aside in move_codex_shadows(shadows, installed_version or 'previous'):
                print(f'{host}: shadow copy kept aside at: {aside}')
        except OSError as exc:
            return f'installed; the Codex desktop shadow copy could not be moved ({exc}). Close Codex and run installer.cmd codex --repair --move-shadow.'
    return 'installed'


def journal_path(target):
    return Path(target).parent/'pending-install.json'


def recover(host, base, *, locked=False):
    """Resolve an interrupted installation from its journal, restoring the previous state.

    The journal records the state before the installation started. Recovery
    restores that state (files and host registration), or closes the record when
    the interrupted installation had in fact completed. Nothing is deleted:
    incomplete copies become failed-install-<id> folders and backups are kept.
    """
    if packaged_process():
        raise RuntimeError(PACKAGED_MESSAGE)
    with nullcontext() if locked else maintenance_lock():
        return _recover(host, base)


def _recover(host, base):
    target = Path(base).resolve()/host/NAME
    transaction = journal_path(target)
    journal = read_json(transaction)
    if not journal:
        raise RuntimeError(f'No interrupted installation record at {transaction}. Nothing to recover.')
    if (not isinstance(journal, dict) or journal.get('host', host) != host
            or local_path(journal.get('target') or target) != target):
        raise RuntimeError(f'The recovery record {transaction} describes another installation. No files changed.')
    backup = local_path(journal['backup']) if journal.get('backup') else None
    if backup is not None and not backup.is_relative_to(target.parent):
        raise RuntimeError('The recovery record points outside the installation folder. No files changed.')
    old_source = local_path(journal['old_source']) if journal.get('old_source') else None
    previous_version = journal.get('previous_version')
    # Records written by 0.8.2 lack these fields; infer them from what that
    # installer could have seen. A backup folder proves the previous files moved.
    target_existed = journal.get('target_existed')
    if target_existed is None:
        target_existed = previous_version is not None and (old_source is None or old_source == target)
    plugin_registered = journal.get('plugin_registered', old_source is not None)
    incoming_sha256 = journal.get('incoming_sha256')
    actions = []

    def note(message):
        print(f'{host}: {message}', flush=True)
        actions.append(message)

    exe = ensure_reader(host)
    for leftover in sorted(target.parent.glob('.sda-stage-*')):
        note(f'staging folder left by the interrupted installation, kept for inspection: {leftover}')
    moved = backup is not None and backup.exists()
    target_is_new = moved or not target_existed

    # Case 1: every step had finished except closing the journal.
    market, source, plugin = inspect(host, exe)
    if target_is_new and target.exists() and _completed(target, source, plugin, incoming_sha256):
        note(f'the interrupted installation had completed as version {version(target)}; closing the record')
        return _finish(host, transaction, journal, actions, 'recovered completed installation')

    # Case 2: restore the previous files.
    if moved:
        if target.exists():
            failed = target.parent/f'failed-install-{uuid.uuid4().hex}'
            target.rename(failed)
            note(f'incomplete copy kept at {failed}')
        backup.rename(target)
        note(f'previous files restored from {backup}')
    elif target_existed:
        if not target.exists():
            raise RuntimeError(f'Neither {target} nor its backup exists. Restore the files manually; the record is kept.')
        note('previous files were never moved')
    elif target.exists():
        failed = target.parent/f'failed-install-{uuid.uuid4().hex}'
        target.rename(failed)
        note(f'incomplete copy kept at {failed}; nothing was installed before')
    if old_source is not None and not old_source.exists():
        raise RuntimeError(f'The previous source {old_source} is missing. Restore it manually; the record is kept.')

    # Case 2, continued: restore the host registration through the vendor CLI.
    market, source, plugin = inspect(host, exe)
    if old_source is None:
        if plugin:
            remove_plugin(host, exe)
            note('removed the plugin registration from the interrupted installation')
        if market:
            run([exe, 'plugin', 'marketplace', 'remove', MARKET])
            note('removed the marketplace registration from the interrupted installation')
    else:
        if market and source != old_source:
            if plugin:
                remove_plugin(host, exe)
                plugin = None
            run([exe, 'plugin', 'marketplace', 'remove', MARKET])
            market = None
            note('removed the marketplace registration pointing at the interrupted installation')
        if not market:
            run([exe, 'plugin', 'marketplace', 'add', str(old_source)])
            note(f'registered the previous source {old_source}')
        elif host == 'claude':
            run([exe, 'plugin', 'marketplace', 'update', MARKET])
        if plugin_registered:
            # Re-register after restored files so host caches match the restored copy.
            register_plugin(host, exe, reinstall=bool(plugin))
            note('re-registered the previous plugin')
        elif plugin:
            remove_plugin(host, exe)
            note('removed a plugin registration that did not exist before')

    market, source, plugin = inspect(host, exe)
    if old_source is None:
        consistent = market is None and plugin is None
    else:
        consistent = (source == old_source and bool(plugin) == bool(plugin_registered)
                      and (not plugin or plugin.get('enabled') is not False))
        if consistent and plugin and previous_version and plugin.get('version'):
            consistent = version_key(plugin['version']) == version_key(previous_version)
    if not consistent:
        raise RuntimeError('The host does not report the previous installation after recovery. '
                           f'The record {transaction} is kept for diagnosis.')
    restored = f'version {version(target)}' if (target/'pyproject.toml').exists() else 'no installation'
    note(f'previous state restored: {restored}. Run installer.cmd again to install the package.')
    return _finish(host, transaction, journal, actions, 'recovered previous installation')


def _completed(target, source, plugin, incoming_sha256):
    try:
        record = read_json(target/MARKER)
        if not isinstance(record, dict) or record.get('target') != str(target):
            return False
        if record.get('installed_sha256') != package_hash(target):
            return False
        if incoming_sha256 and record.get('package_sha256') != incoming_sha256:
            return False
        if source != target or not plugin or plugin.get('enabled') is False:
            return False
        return not plugin.get('version') or version_key(plugin['version']) == version_key(record['version'])
    except (OSError, ValueError, KeyError):
        return False


def _finish(host, transaction, journal, actions, result):
    receipt = transaction.parent/f'recovery-{uuid.uuid4().hex}.json'
    write_json(receipt, {'host':host, 'result':result, 'recovered_at':time.time(), 'record':journal, 'actions':actions})
    transaction.unlink()
    print(f'{host}: recovery record closed; receipt: {receipt}', flush=True)
    return result


def finish_reader_setup(reader, *, interactive):
    """Run after the installation transaction, so login cannot roll it back or hold its lock."""
    if reader is None and interactive:
        print('\nSet up subscription reading (independent of the app hosting the plugin):')
        print('1 = Codex / ChatGPT, 2 = Claude Code, 3 = Skip (API or set up later)')
        while reader is None:
            reader = {'1': 'codex', '2': 'claude', '3': 'none'}.get(input('Choose 1, 2 or 3: ').strip())
            if reader is None:
                print('Choose 1, 2 or 3.')
    if reader in (None, 'none'):
        print('Subscription reader setup skipped. '
              'For subscription reading, run installer.cmd reader later; for API reading, use installer.cmd settings.')
        return
    setup_subscription_reader(reader, allow_login=interactive)
    print('Subscription sign-in complete. Start a new local conversation after setup finishes.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app', nargs='?', choices=['claude','codex','both','begge'])
    parser.add_argument('--base-dir', type=Path, default=Path(os.environ.get('LOCALAPPDATA',Path.home()))/'systematic-document-analysis'/'plugins')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--replace-source', action='store_true', help='Explicitly replace this plugin\'s local marketplace source')
    parser.add_argument('--repair', action='store_true', help='Reinstall even when the version is unchanged')
    parser.add_argument('--allow-downgrade', action='store_true')
    parser.add_argument('--move-shadow', action='store_true',
                        help='Move aside a stale copy that the packaged Codex desktop app reads instead of the installation')
    parser.add_argument('--non-interactive', action='store_true', help='Never prompt; conflicts require explicit options')
    parser.add_argument('--reader', choices=['claude', 'codex', 'none'],
                        help='Subscription reader to set up after installation; none skips it. '
                             'Non-interactive mode only checks sign-in, never opens login.')
    parser.add_argument('--skip-ocr', action='store_true', help='Explicitly skip installation/check of local OCR.')
    parser.add_argument('--recover', action='store_true',
                        help='Resolve an interrupted installation (pending-install.json) by restoring the previous state')
    args = parser.parse_args()
    if args.reader is not None and (args.prepare_only or args.recover):
        parser.error('--reader cannot be combined with --prepare-only or --recover.')
    if sys.version_info < (3,12) or os.name != 'nt':
        parser.error('This installation package requires Windows and Python 3.12 or newer.')
    interactive = not args.non_interactive and sys.stdin.isatty()
    app = args.app
    if not interactive and not app:
        parser.error('Choose claude, codex or both when running without an interactive terminal.')
    if not app:
        print('Install Systematic Document Analysis: 1 = Claude Code, 2 = Codex, 3 = both')
        app = {'1':'claude','2':'codex','3':'begge'}.get(input('Choose 1, 2 or 3: ').strip())
        if not app:
            parser.error('Invalid choice; installation has not started.')
    failures = []
    installed = False
    try:
        if not args.prepare_only and packaged_process():
            raise RuntimeError(PACKAGED_MESSAGE)
        # One gate for both hosts: clients cannot reconnect between installations.
        with nullcontext() if args.prepare_only else installation_lock(notify=lambda message: print(message, flush=True)):
            for host in (['claude','codex'] if app in ('both','begge') else [app]):
                try:
                    if args.prepare_only:
                        print(prepare(host, args.base_dir))
                    elif args.recover:
                        print(f'{host}: {recover(host, args.base_dir, locked=True)}')
                    else:
                        result = install(host, args.base_dir, replace_source=args.replace_source, repair=args.repair,
                                         allow_downgrade=args.allow_downgrade, move_shadow=args.move_shadow,
                                         interactive=interactive, locked=True)
                        print(f'{host}: {result}')
                        installed = installed or result in ('installed', 'already up to date')
                except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as exc:
                    failures.append(host)
                    print(f'{host}: installation stopped: {exc}', file=sys.stderr)
    except (RuntimeError, OSError, ValueError) as exc:
        print(f'Installation stopped: {exc}', file=sys.stderr)
        return 1
    if installed and not failures:
        if not args.skip_ocr:
            try:
                setup_local_ocr()
            except (RuntimeError, OSError, ValueError, subprocess.SubprocessError, KeyboardInterrupt, EOFError) as exc:
                print(f'Plugin files are installed, but OCR setup is incomplete: {exc or "cancelled"}. '
                      'Run installer.cmd ocr to finish OCR; reinstalling the plugin is not necessary.', file=sys.stderr)
                failures.append('ocr')
        try:
            finish_reader_setup(args.reader, interactive=interactive)
        except (RuntimeError, OSError, ValueError, subprocess.SubprocessError, KeyboardInterrupt, EOFError) as exc:
            print(f'Plugin installation is complete, but reader setup is incomplete: {exc or "cancelled"}. '
                  'Run installer.cmd reader to finish; reinstalling the plugin is not necessary.', file=sys.stderr)
            return 1
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
