"""Check published releases, choose update policy, or update a managed install."""
from __future__ import annotations
import argparse
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from kildeanalyse.maintenance import MaintenanceBusy, maintenance_lock, read_json, state_dir, write_json
from kildeanalyse.cli_paths import find_cli
from installer import MARKER, NAME, local_path, version, version_key, validate_package, package_hash

REPOSITORY = 'emilmsh/systematic-document-analysis'
API = f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
WEB = f'https://github.com/{REPOSITORY}/releases'
ARCHIVE = 'systematic-document-analysis-windows.zip'
DAY = 86400


def fetch(url, maximum=2_000_000):
    accept = 'application/octet-stream' if '/releases/assets/' in url else 'application/vnd.github+json'
    gh = shutil.which('gh')
    if gh and url.startswith('https://api.github.com/'):
        # Let GitHub CLI use its existing login. Never read, print or persist tokens.
        with tempfile.TemporaryFile() as output:
            result = subprocess.run([gh, 'api', '--hostname', 'github.com',
                                     url.removeprefix('https://api.github.com/'), '-H', f'Accept: {accept}'],
                                    stdout=output, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, timeout=60)
            if result.returncode:
                raise OSError('GitHub access unavailable. Sign in with gh auth login or use a shared release ZIP.')
            output.seek(0)
            payload = output.read(maximum + 1)
        if len(payload) > maximum:
            raise ValueError('Release download exceeds the size limit.')
        return payload
    request = urllib.request.Request(url, headers={'User-Agent':'Systematic-Document-Analysis-Updater',
                                                 'Accept':accept})
    with urllib.request.urlopen(request, timeout=8) as response:
        payload = response.read(maximum + 1)
    if len(payload) > maximum:
        raise ValueError('Release download exceeds the size limit.')
    return payload


def check(*, force=False):
    path = state_dir()/'last-check.json'
    cached = read_json(path)
    if not force and time.time() - cached.get('checked_at', 0) < DAY:
        return cached
    result = {'checked_at':time.time()}
    try:
        release = json.loads(fetch(API))
        tag = release['tag_name']
        if release.get('draft') or release.get('prerelease') or not re.fullmatch(r'v?\d+\.\d+\.\d+', tag):
            raise ValueError('No supported stable release.')
        assets = {a['name']:a['id'] for a in release.get('assets', [])}
        if not {ARCHIVE, 'SHA256SUMS.txt'} <= assets.keys():
            raise ValueError('The release does not contain the Windows archive and SHA256SUMS.txt.')
        result.update(version=tag.removeprefix('v'), tag=tag, url=f'{WEB}/tag/{tag}',
                      assets={name:assets[name] for name in (ARCHIVE, 'SHA256SUMS.txt')},
                      notes=str(release.get('body') or '')[:4000], message='Release information available.')
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        # Do not make offline startup fail or try again on every new conversation.
        result['message'] = (f'Update check unavailable ({type(exc).__name__}). Private repository access needs '
                             'an existing GitHub CLI login with repository access. Use gh auth login, or install a shared ZIP.')
    write_json(path, result)
    return result


def extract_release(payload, destination):
    """Reject traversal, Windows aliases, symlinks, duplicates and oversized ZIPs."""
    root = Path(destination).resolve()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        if len(archive.infolist()) > 10000:
            raise ValueError('Release contains too many files.')
        if sum(item.file_size for item in archive.infolist()) > 256_000_000:
            raise ValueError('Expanded release is too large.')
        seen = set()
        for item in archive.infolist():
            # ZipInfo normalizes backslashes on Windows; inspect the original.
            name = item.orig_filename
            path = PurePosixPath(name)
            parts = name.rstrip('/').split('/')
            if ('\\' in name or not parts or parts[0] != NAME or path.is_absolute()
                    or any(part in ('', '.', '..') or any(char in part for char in '<>:"|?*\x00') or part.endswith((' ', '.'))
                           or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part, re.I)
                           for part in parts)
                    or stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError('Unsafe path in release archive.')
            normalized = name.rstrip('/').casefold()
            if normalized in seen:
                raise ValueError('Duplicate path in release archive.')
            seen.add(normalized)
            target = root.joinpath(*parts).resolve()
            if not target.is_relative_to(root):
                raise ValueError('Release path leaves extraction directory.')
        archive.extractall(root)
    return root/NAME


def download(release, destination):
    tag = release['tag']
    if not re.fullmatch(r'v?\d+\.\d+\.\d+', tag):
        raise ValueError('Invalid release tag.')
    def asset_url(name):
        asset_id = release.get('assets', {}).get(name)
        if type(asset_id) is not int or asset_id <= 0:
            raise ValueError('Missing release asset ID. Check for updates again.')
        return f'https://api.github.com/repos/{REPOSITORY}/releases/assets/{asset_id}'
    checksums = fetch(asset_url('SHA256SUMS.txt'), 8192).decode('ascii')
    matches = re.findall(r'^([a-fA-F0-9]{64})\s+\*?' + re.escape(ARCHIVE) + r'\s*$', checksums, re.M)
    if len(matches) != 1:
        raise ValueError('Missing or ambiguous archive checksum.')
    payload = fetch(asset_url(ARCHIVE), 64_000_000)
    if hashlib.sha256(payload).hexdigest() != matches[0].lower():
        raise ValueError('Release checksum mismatch; installed files are unchanged.')
    source = extract_release(payload, destination)
    if validate_package(source) != release['version']:
        raise ValueError('Release tag and package version differ.')
    return source


def managed_install(root):
    marker = read_json(Path(root)/MARKER)
    if not marker:
        return None
    target = local_path(marker['target'])
    base = local_path(marker['base'])
    if marker.get('host') not in ('claude', 'codex') or target != base/marker['host']/NAME:
        raise ValueError('Invalid installation record.')
    current = read_json(target/MARKER)
    if current.get('target') != str(target) or current.get('host') != marker['host']:
        raise ValueError('The managed installation has moved. Run installer.cmd again.')
    return current


def apply_release(marker, release):
    """Caller holds the exclusive session lock; update only the registered source."""
    import installer
    target = local_path(marker['target'])
    if version_key(release['version']) <= version_key(version(target)):
        return False
    # Never overwrite a development copy or local edits during automatic updates.
    if package_hash(target) != marker.get('installed_sha256'):
        raise RuntimeError('Installed files have local changes. Use installer.cmd to repair or keep them.')
    exe = find_cli(marker['host'])
    if not Path(exe).is_file() and not shutil.which(exe):
        raise RuntimeError('The host CLI is unavailable. Run reader_setup.cmd before updating.')
    _, registered, plugin = installer.inspect(marker['host'], exe)
    if registered != target or not plugin or not plugin.get('enabled', True):
        raise RuntimeError('This copy is not the active enabled installation. Run installer.cmd.')
    with tempfile.TemporaryDirectory(prefix='sda-release-') as temporary:
        source = download(release, temporary)
        previous = installer.ROOT
        try:
            installer.ROOT = source
            result = installer.install(marker['host'], marker['base'], locked=True)
        finally:
            installer.ROOT = previous
    return result == 'installed'


def startup(root):
    """Runs before a session takes the shared lock. All output stays off MCP stdout."""
    try:
        marker = managed_install(root)
        if not marker:
            return False  # No checks or updates in development/unmanaged copies.
        mode = read_json(state_dir()/'updates.json').get('mode', 'notify')
        if mode == 'off':
            return False
        with redirect_stdout(sys.stderr):
            # The daily check and its notice only need the shared lock, so every
            # concurrent session still sees the notice. Installation needs exclusivity.
            with maintenance_lock(shared=True):
                release = check()
            target = Path(marker['target'])
            if not release.get('version') or version_key(release['version']) <= version_key(version(target)):
                return False
            print(f'[Systematic Document Analysis] Version {release["version"]} is available. Run {target / "update.cmd"}.', file=sys.stderr)
            if mode != 'auto':
                return False
            with maintenance_lock():
                # A failed download/install should not repeat for every new session.
                attempts_path = state_dir()/'update-attempts.json'
                attempts = read_json(attempts_path)
                if time.time() - attempts.get(str(target), 0) < DAY:
                    return False
                attempts[str(target)] = time.time()
                write_json(attempts_path, attempts)
                applied = apply_release(marker, release)
            if applied:
                print('[Systematic Document Analysis] Updated. Start a new conversation to load the new plugin and tools.', file=sys.stderr)
            return applied
    except MaintenanceBusy:
        return False  # Another live session: defer without disrupting that session.
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as exc:
        print(f'[Systematic Document Analysis] Update deferred: {exc}', file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('off','notify','auto'), help='Save the policy for future sessions in both apps')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--install', action='store_true', help='Install the latest stable release now')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        if not any((args.mode, args.check, args.install)):
            print('Updates: 1 = check now, 2 = update now, 3 = notify only (default), 4 = automatic, 5 = off')
            choice = input('Choose 1-5: ').strip()
            args.check = choice == '1'
            args.install = choice == '2'
            args.mode = {'3':'notify', '4':'auto', '5':'off'}.get(choice)
            if choice not in ('1','2','3','4','5'):
                parser.error('Invalid choice; no changes made.')
        # Checking and choosing a policy only need the shared lock, so they work
        # while plugin sessions are open. Installing still requires exclusivity.
        with maintenance_lock(shared=not args.install):
            if args.mode:
                write_json(state_dir()/'updates.json', {'mode':args.mode})
                print(f'Update policy: {args.mode}. Applies to managed installations in both apps.')
            if args.check or args.install:
                release = check(force=True)
                print(release['message'])
                if not release.get('version'):
                    return 1
                print(f'Latest stable version: {release["version"]}\n{release["url"]}\n{release["notes"]}')
                if args.install:
                    marker = managed_install(root)
                    if not marker:
                        raise RuntimeError('Run update.cmd from the installed plugin folder. For first setup, run installer.cmd.')
                    print('Updated. Start a new conversation.' if apply_release(marker, release) else 'Already up to date.')
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.SubprocessError) as exc:
        print(f'Update stopped: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
