"""OpenCode as host: a managed local copy registered in OpenCode's global configuration.

OpenCode has no plugin marketplace for skills and MCP servers, so the installer copies the
package, adds one MCP server and one skills path to ~/.config/opencode/opencode.json, and
keeps a backup of that file. OpenCode merges opencode.json with opencode.jsonc (combining
skills lists and MCP servers by name), so a commented opencode.jsonc is never rewritten.
Updates use the managed-copy policy (installer.cmd update).
"""
from __future__ import annotations
from contextlib import nullcontext
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

import installer
from installer import MARKER, NAME, local_path, version, version_key, package_hash, validate_package, journal_path, confirm
from pakk_plugin import pakk
# Standard library only: this runs before the plugin's Python environment exists.
from kildeanalyse.cli_paths import OPENCODE_MIN_VERSION as MIN_VERSION, opencode_bin, version_tuple
from kildeanalyse.konfig import brukermappe
from kildeanalyse.maintenance import PACKAGED_MESSAGE, maintenance_lock, packaged_process, read_json, write_json

HOST = 'opencode'
SERVER = 'document_analysis'
# The first start prepares the Python environment, which takes about a minute.
STARTUP_MS = 300_000


def config_dir():
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')/'opencode'


def config_file():
    """Plain JSON that this installer may rewrite; opencode.jsonc, which may carry comments, is left alone."""
    return config_dir()/'opencode.json'


def plugin_data():
    """Separate from the Codex runtime, so different installed versions never rebuild each other's environment."""
    return brukermappe()/'plugin-data-opencode'


def server_entry(target):
    return {'type': 'local', 'command': ['cmd.exe', '/d', '/s', '/c', 'call', str(Path(target)/'bin'/'start_server.cmd')],
            'environment': {'PYTHONUTF8': '1', 'SDA_PLUGIN_DATA': str(plugin_data())},
            'timeout': {'startup': STARTUP_MS}}


MOVE_TIMEOUT_SEC = 30


def skills_root(target):
    """Beside the installation, not inside it: OpenCode watches its skills paths, and Windows
    refuses to move a folder while any folder below it is watched. Files inside can still change."""
    return Path(target).parent/'skills'


def skill_file(target):
    return skills_root(target)/NAME/'SKILL.md'


def write_skill(package, target):
    """Copy the skill in place; its guide links point at the installed documentation."""
    text = (Path(package)/'skills'/NAME/'SKILL.md').read_text(encoding='utf-8')
    destination = skill_file(target)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text.replace('](../../docs/', f']({Path(target).as_posix()}/docs/'), encoding='utf-8')


def move_when_released(source, destination, timeout=MOVE_TIMEOUT_SEC):
    """OpenCode releases a watched folder about a second after its configuration stops naming it."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            Path(source).rename(destination)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise RuntimeError(f'{source} is still in use, probably by OpenCode. Close OpenCode, run '
                                   '"opencode service stop", then run the installer again.') from None
            time.sleep(0.5)


def snippet(target):
    return json.dumps({'mcp': {'servers': {SERVER: server_entry(target)}}, 'skills': [str(skills_root(target))]},
                      ensure_ascii=False, indent=2)


def read_config(path, target):
    """Only plain JSON is edited; comments would be lost in a rewrite."""
    if not path.exists():
        return {}
    text = path.read_text(encoding='utf-8-sig')
    try:
        config = json.loads(text) if text.strip() else {}
    except ValueError:
        config = None
    if not isinstance(config, dict):
        raise RuntimeError(f'{path} contains comments or other JSONC syntax, which this installer does not rewrite. '
                           f'No files changed. Add these entries yourself, then start a new OpenCode session:\n{snippet(target)}')
    mcp = config.get('mcp', {})
    if not isinstance(mcp, dict) or any(key not in ('servers', 'timeout') for key in mcp):
        raise RuntimeError(f'{path} uses the OpenCode 1 layout for MCP servers. Move them under mcp.servers '
                           f'(OpenCode 2), or add these entries yourself. No files changed.\n{snippet(target)}')
    commented = path.with_name('opencode.jsonc')
    if commented.is_file() and f'"{SERVER}"' in commented.read_text(encoding='utf-8-sig'):
        raise RuntimeError(f'{commented} also defines {SERVER}, which would conflict with this installation. '
                           'Remove that entry there, then run the installer again. No files changed.')
    return config


def ours(entry):
    """The source folder of a server entry this installer wrote, else None."""
    command = entry.get('command') if isinstance(entry, dict) else None
    if not isinstance(command, list) or not command or not str(command[-1]).lower().endswith('start_server.cmd'):
        return None
    root = Path(command[-1]).parents[1]
    return root if root.name == NAME else None


def registration(path=None, target=None):
    """(server entry, source folder it starts) for this plugin in the global configuration."""
    config = read_config(path or config_file(), target or Path(NAME))
    entry = config.get('mcp', {}).get('servers', {}).get(SERVER)
    return entry, ours(entry) if entry else None


def skill_paths(config):
    skills = config.get('skills')
    return skills.get('paths', []) if isinstance(skills, dict) else skills if isinstance(skills, list) else []


def our_skills(item):
    """A skills path this installer wrote: inside an installation (0.13.0-0.13.1) or beside one."""
    if not isinstance(item, str):
        return False
    path = Path(item)
    if path.name != 'skills':
        return False
    # Beside an installation only when that installation's record is there, so a user's
    # own .../opencode/skills folder (such as ~/.config/opencode/skills) is never removed.
    return path.parent.name == NAME or (path.parent/NAME/MARKER).is_file()


def register(target):
    """Point this plugin's MCP server and skills path at target, keeping every other setting."""
    path = config_file()
    config = read_config(path, target)
    config.setdefault('mcp', {}).setdefault('servers', {})[SERVER] = server_entry(target)
    skills = str(skills_root(target))
    kept = [item for item in skill_paths(config) if not our_skills(item) and item != skills]
    if isinstance(config.get('skills'), dict):
        config['skills']['paths'] = [*kept, skills]
    else:
        config['skills'] = [*kept, skills]
    config.setdefault('$schema', 'https://opencode.ai/config.json')
    write_json(path, config)


def backup_config(path):
    if not path.exists():
        return None
    backup = path.with_name(f'{path.name}.sda-backup-{time.strftime("%Y%m%d-%H%M%S")}-{uuid.uuid4().hex[:6]}')
    backup.write_bytes(path.read_bytes())
    return backup


def restore_config(path, backup, existed):
    if backup and Path(backup).exists():
        Path(path).write_bytes(Path(backup).read_bytes())
    elif not existed and Path(path).exists():
        Path(path).rename(Path(path).with_name(f'{Path(path).name}.sda-failed-{uuid.uuid4().hex[:8]}'))


def check_opencode():
    binary = opencode_bin()
    try:
        output = subprocess.run([binary, '--version'], capture_output=True, text=True, timeout=30,
                                encoding='utf-8', errors='replace', stdin=subprocess.DEVNULL).stdout
    except (OSError, subprocess.SubprocessError):
        output = ''
    found = version_tuple(output)
    if not found:
        raise RuntimeError('OpenCode was not found. Install OpenCode 2 (https://opencode.ai), then run this installer again.')
    if found < MIN_VERSION:
        raise RuntimeError(f'OpenCode {output.strip()} is too old. Run "opencode upgrade", then run this installer again.')
    return output.strip()


def reconnect():
    """Reload a running OpenCode after an update, once the installation lock is released.

    The update closes the plugin's connection, and OpenCode's own reload of the changed
    configuration fails while the installer holds the lock. A stopped OpenCode is left stopped.
    """
    binary = opencode_bin()
    try:
        status = subprocess.run([binary, 'service', 'status'], capture_output=True, text=True, encoding='utf-8',
                                errors='replace', timeout=30, stdin=subprocess.DEVNULL).stdout.strip()
        if not status.startswith('http'):
            return False
        return subprocess.run([binary, 'reload'], capture_output=True, timeout=60, stdin=subprocess.DEVNULL).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


PREPARE_TIMEOUT_SEC = 900


def prepare_runtime(target, timeout=PREPARE_TIMEOUT_SEC):
    """Build the Python environment now, so the first OpenCode session starts quickly.

    A failure or timeout is not an installation failure: OpenCode prepares it on first start.
    """
    env = dict(os.environ, PYTHONUTF8='1', SDA_PLUGIN_DATA=str(plugin_data()))
    try:
        process = subprocess.Popen([sys.executable, '-X', 'utf8', str(Path(target)/'bin'/'start_server.py'),
                                    '--prepare-only'], env=env, stdin=subprocess.DEVNULL)
    except OSError:
        return False
    try:
        return process.wait(timeout=timeout) == 0
    except subprocess.TimeoutExpired:
        # pip runs as a grandchild; stop the whole tree rather than leave it hanging.
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], capture_output=True)
        if process.poll() is None:
            process.kill()
        process.wait()
        return False


def install(base, *, root=None, replace_source=False, repair=False, allow_downgrade=False, interactive=False, locked=False):
    if packaged_process():
        raise RuntimeError(PACKAGED_MESSAGE)
    with nullcontext() if locked else maintenance_lock():
        return _install(Path(base), Path(root or installer.ROOT), replace_source=replace_source, repair=repair,
                        allow_downgrade=allow_downgrade, interactive=interactive)


def _install(base, root, *, replace_source, repair, allow_downgrade, interactive):
    incoming = validate_package(root)
    target = base.resolve()/HOST/NAME
    if target == root or root.is_relative_to(target) or target.is_relative_to(root):
        raise RuntimeError('Use an installation folder separate from the source package.')
    if target.is_symlink() or target.is_junction() or target.resolve() != target:
        raise RuntimeError('The install target or a parent is a link/junction. Choose a regular installation directory.')
    transaction = journal_path(target)
    if transaction.exists():
        raise RuntimeError(f'An interrupted installation needs recovery; see {transaction}. '
                           f'Run installer.cmd {HOST} --recover. No new changes made.')
    print(f'{HOST}: {check_opencode()}')
    path = config_file()
    entry, source = registration(path, target)
    if entry and not source:
        print(f'{HOST}: {path} already defines another MCP server named {SERVER}.\nOption: --replace-source')
        if not confirm('Replace that server entry? The previous file is kept as a backup.',
                       allowed=replace_source, interactive=interactive):
            return 'kept existing server entry'
    elif source and source != target:
        print(f'{HOST}: existing source: {source}\nNew source: {target}\nOption: --replace-source')
        if not confirm('Switch to this installation? The previous source folder is kept.',
                       allowed=replace_source, interactive=interactive):
            return 'kept existing source'
    installed_version = version(target) if (target/'pyproject.toml').exists() else None
    print(f'{HOST}: installed {installed_version or "none"}; package {incoming}')
    if installed_version and version_key(installed_version) > version_key(incoming):
        print('Option: --allow-downgrade')
        if not confirm('A newer version is installed. Downgrade explicitly?', allowed=allow_downgrade, interactive=interactive):
            return 'kept newer version'
    wanted_hash = package_hash(root)
    record = read_json(target/MARKER) if (target/MARKER).exists() else {}
    identical = (record.get('package_sha256') == wanted_hash and target.exists()
                 and record.get('installed_sha256') == package_hash(target))
    if identical and source == target and not repair:
        print(f'{HOST}: already up to date. Use --repair to reinstall.')
        return 'already up to date'
    if (target.exists() and not identical and installed_version
            and version_key(installed_version) == version_key(incoming) and not repair):
        print('Option: --repair')
        if not confirm('Same version, different files. Repair with this package?', interactive=interactive):
            return 'kept existing files'

    target.parent.mkdir(parents=True, exist_ok=True)
    backup = target.parent/'backups'/uuid.uuid4().hex/NAME
    with tempfile.TemporaryDirectory(prefix='.sda-stage-', dir=target.parent) as temporary:
        staged = Path(temporary)/NAME
        pakk(staged, codex=False, root=root)
        write_json(staged/MARKER, {'host': HOST, 'base': str(base.resolve()), 'target': str(target), 'version': incoming,
                                   'package_sha256': wanted_hash, 'installed_sha256': package_hash(staged)})
        validate_package(staged)
        config_existed = path.exists()
        config_backup = backup_config(path)
        skill = skill_file(target)
        if target.exists() or skill.exists():
            backup.parent.mkdir(parents=True)
        skill_backup = backup.parent/'SKILL.md' if skill.exists() else None
        if skill_backup:
            skill_backup.write_bytes(skill.read_bytes())
        # The journal describes the state before any change, so --recover can restore it at any later step.
        write_json(transaction, {'host': HOST, 'target': str(target), 'backup': str(backup), 'config': str(path),
                                 'config_existed': config_existed, 'config_backup': str(config_backup) if config_backup else None,
                                 'skill': str(skill), 'skill_backup': str(skill_backup) if skill_backup else None,
                                 'previous_source': str(source) if source else None, 'previous_version': installed_version,
                                 'target_existed': target.exists(), 'incoming_version': incoming,
                                 'incoming_sha256': wanted_hash, 'started_at': time.time()})
        moved = placed = False
        try:
            # Register first, so OpenCode watches the skill copy beside the installation and
            # releases any watch inside it (installations from 0.13.0-0.13.1) before the move.
            write_skill(staged, target)
            register(target)
            if target.exists():
                move_when_released(target, backup)
                moved = True
            staged.rename(target)
            placed = True
            if registration(path, target)[1] != target:
                raise RuntimeError('The OpenCode configuration does not point at the new installation.')
        except Exception as failure:
            try:
                # Files first: a restored configuration can make OpenCode watch the installation folder again.
                if placed:
                    move_when_released(target, target.parent/f'failed-install-{uuid.uuid4().hex}')
                if moved:
                    backup.rename(target)
                restore_config(path, config_backup, config_existed)
                if skill_backup:
                    skill.write_bytes(skill_backup.read_bytes())
                transaction.unlink()
            except Exception as recovery:
                raise RuntimeError(f'Installation failed: {failure}. Recovery also failed: {recovery}. '
                                   f'Recovery record: {transaction}') from failure
            raise RuntimeError(f'Installation failed; previous files and configuration restored: {failure}') from failure
        transaction.unlink()
    print(f'{HOST}: installed {incoming} and registered it in {path}.')
    if config_backup:
        print(f'{HOST}: previous configuration kept at {config_backup}')
    if moved:
        print(f'Previous copy kept at: {backup}')
    print(f'{HOST}: preparing the Python environment for the first session...', flush=True)
    if not prepare_runtime(target):
        print(f'{HOST}: the Python environment was not prepared now; OpenCode prepares it on first start (up to a few minutes).')
    print(f'{HOST}: start a new OpenCode session to load the plugin. OpenCode can also read documents itself: '
          'choose the opencode_cli reader with a provider/model you have signed in to in OpenCode.')
    print(f'Updates: notify by default; run "{target / "installer.cmd"}" update to change this.')
    return 'installed'


def recover(base, *, locked=False):
    if packaged_process():
        raise RuntimeError(PACKAGED_MESSAGE)
    with nullcontext() if locked else maintenance_lock():
        return _recover(Path(base))


def _recover(base):
    """Restore the files and configuration recorded before an interrupted installation. Nothing is deleted."""
    target = base.resolve()/HOST/NAME
    transaction = journal_path(target)
    journal = read_json(transaction)
    if not journal:
        raise RuntimeError(f'No interrupted installation record at {transaction}. Nothing to recover.')
    if journal.get('host') != HOST or local_path(journal.get('target') or target) != target:
        raise RuntimeError(f'The recovery record {transaction} describes another installation. No files changed.')
    backup = local_path(journal['backup'])
    if not backup.is_relative_to(target.parent):
        raise RuntimeError('The recovery record points outside the installation folder. No files changed.')
    actions = []
    # Files first: a restored configuration can make OpenCode watch the installation folder again.
    if backup.exists():
        if target.exists():
            failed = target.parent/f'failed-install-{uuid.uuid4().hex}'
            move_when_released(target, failed)
            actions.append(f'incomplete copy kept at {failed}')
        backup.rename(target)
        actions.append(f'previous files restored from {backup}')
    elif not journal.get('target_existed') and target.exists():
        failed = target.parent/f'failed-install-{uuid.uuid4().hex}'
        move_when_released(target, failed)
        actions.append(f'incomplete copy kept at {failed}; nothing was installed before')
    restore_config(Path(journal['config']), journal.get('config_backup'), journal.get('config_existed', True))
    actions.append('restored the OpenCode configuration from before the installation')
    if journal.get('skill_backup') and Path(journal['skill_backup']).exists():
        Path(journal['skill']).write_bytes(Path(journal['skill_backup']).read_bytes())
        actions.append('restored the previous skill copy')
    receipt = transaction.parent/f'recovery-{uuid.uuid4().hex}.json'
    write_json(receipt, {'host': HOST, 'recovered_at': time.time(), 'record': journal, 'actions': actions})
    transaction.unlink()
    for action in actions:
        print(f'{HOST}: {action}')
    print(f'{HOST}: recovery record closed; receipt: {receipt}')
    return 'recovered previous installation'


def installed_target():
    """The registered managed copy, for update checks."""
    return registration()[1]
