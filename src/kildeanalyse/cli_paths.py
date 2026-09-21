"""Locate reader CLIs without requiring changes to the user's PATH."""
import os
import ntpath
from pathlib import Path
import shutil


def windows_path_directories():
    """Read current persisted PATH even when the host inherited an older value.

    Read only: do not replace PATH or broadcast changes to unrelated applications.
    Inaccessible registry keys must not prevent standard-location discovery.
    """
    try:
        import winreg
    except ImportError:
        return []
    directories = []
    for hive, key in (
        (winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'),
        (winreg.HKEY_CURRENT_USER, 'Environment'),
    ):
        try:
            with winreg.OpenKey(hive, key) as handle:
                value, _ = winreg.QueryValueEx(handle, 'Path')
        except OSError:
            continue
        if not isinstance(value, str):
            continue
        for entry in value.split(';'):
            entry = ntpath.expandvars(entry.strip().strip('"'))
            # Empty/relative entries must not turn this fallback into a cwd search.
            if Path(entry).is_absolute() and entry not in directories:
                directories.append(entry)
    return directories


def winget_binaries(base, name):
    """Inspect only this reader's package directories, not arbitrary executables."""
    package_id = {'claude': 'Anthropic.ClaudeCode', 'codex': 'OpenAI.Codex'}.get(name)
    if not package_id:
        return
    try:
        packages = sorted((base/'Microsoft/WinGet/Packages').glob(f'{package_id}_*'))
        for package in packages:
            # Portable packages may contain the executable at root or in a subfolder.
            for pattern in (f'{name}.exe', f'*/{name}.exe'):
                yield from sorted(package.glob(pattern))
    except OSError:
        return


def execution_env(environment):
    """Refresh only the child PATH, including runtimes needed by npm-installed CLIs."""
    result = dict(environment)
    entries = result.get('PATH', '').split(os.pathsep)
    known = {entry.casefold() for entry in entries}
    for directory in windows_path_directories():
        if directory.casefold() not in known:
            entries.append(directory)
            known.add(directory.casefold())
    result['PATH'] = os.pathsep.join(entries)
    return result


def find_cli(name):
    explicit = os.environ.get(f'SDA_{name.upper()}_BIN')
    if explicit:
        return explicit
    found = shutil.which(name)
    if found:
        return found
    for directory in windows_path_directories():
        found = shutil.which(str(Path(directory)/name))
        if found:
            return found
    base = Path(os.environ.get('LOCALAPPDATA', Path.home()/'.local/share'))
    for path in (base/'systematic-document-analysis/readers'/name/f'{name}.exe',
                 base/'Microsoft/WinGet/Links'/f'{name}.exe',
                 Path.home()/'.local/bin'/f'{name}.exe'):
        if path.is_file():
            return str(path)
    roaming = os.environ.get('APPDATA')
    if roaming:
        found = shutil.which(str(Path(roaming)/'npm'/name))
        if found:
            return found
    for path in winget_binaries(base, name):
        if path.is_file():
            return str(path)
    return name
