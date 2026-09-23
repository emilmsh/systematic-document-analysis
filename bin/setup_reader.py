"""Install or update a reader CLI; sign-in remains an explicit user action."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from kildeanalyse.cli_paths import find_cli, execution_env
from kildeanalyse.cli_auth import subscription_confirmed

CODEX_URL = 'https://github.com/openai/codex/releases/download/rust-v0.155.1/codex-x86_64-pc-windows-msvc.exe'
CODEX_SHA256 = 'eba0f32c976667cb9298efafd98513e823eeda7b576a03ec658bb8be8d336316'
CODEX_RELEASES_URL = 'https://api.github.com/repos/openai/codex/releases/latest'


def codex_version(value):
    match = re.search(r'(?<!\d)(\d+)\.(\d+)\.(\d+)(?!\d)', value)
    if not match:
        raise RuntimeError(f'Could not read Codex version from {value!r}.')
    return tuple(int(part) for part in match.groups())


def cli_version(binary):
    result = subprocess.run([binary, '--version'], check=True, capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=20,
                            env=subscription_env())
    version = (result.stdout or result.stderr).strip()
    if not version:
        raise RuntimeError('Reader CLI did not report a version.')
    return version.splitlines()[0]


def latest_codex_asset():
    """Require the official release asset and its published SHA-256 digest."""
    request = urllib.request.Request(CODEX_RELEASES_URL, headers={
        'Accept': 'application/vnd.github+json', 'User-Agent': 'systematic-document-analysis'})
    with urllib.request.urlopen(request, timeout=20) as response:
        release = json.load(response)
    asset = next((item for item in release.get('assets', [])
                  if item.get('name') == 'codex-x86_64-pc-windows-msvc.exe'), None)
    digest = (asset or {}).get('digest', '')
    if not asset or not digest.startswith('sha256:') or len(digest) != 71:
        raise RuntimeError('Latest Codex release has no verifiable Windows executable; update stopped.')
    return release['tag_name'], asset['browser_download_url'], digest[7:]


def update(name):
    """Explicit update action. Never replace a CLI managed by another installer."""
    binary = install(name)
    before = cli_version(binary)
    print(f'{name}: current version: {before}', flush=True)
    if name == 'claude':
        subprocess.run([binary, 'update'], check=True, env=subscription_env())
    elif name == 'codex':
        managed = Path(os.environ['LOCALAPPDATA'])/'systematic-document-analysis/readers/codex/codex.exe'
        if Path(binary).resolve() != managed.resolve():
            print('Codex CLI is managed by another installer or the Codex desktop app. '
                  'Update it there; see https://developers.openai.com/codex/cli . '
                  'No executable was replaced.', flush=True)
            return binary
        tag, url, digest = latest_codex_asset()
        target_version = codex_version(tag)
        if codex_version(before) >= target_version:
            print(f'codex: already at or newer than latest stable release {tag}.', flush=True)
            return binary
        temporary = managed.with_suffix('.download')
        backup = managed.with_suffix('.backup')
        if backup.exists():
            raise RuntimeError(f'Existing backup at {backup}; update stopped for inspection.')
        try:
            urllib.request.urlretrieve(url, temporary)
            with temporary.open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual != digest:
                raise RuntimeError('Latest Codex download checksum mismatch; update stopped.')
            managed.replace(backup)
            try:
                temporary.replace(managed)
                after = cli_version(str(managed))
                if codex_version(after) < target_version:
                    raise RuntimeError(f'Updated Codex reported {after}, older than {tag}.')
            except (OSError, RuntimeError, subprocess.SubprocessError):
                managed.unlink(missing_ok=True)
                backup.replace(managed)
                raise
            backup.unlink()
            print(f'codex: verified {tag}: {after}', flush=True)
            return str(managed)
        finally:
            temporary.unlink(missing_ok=True)
    else:
        raise ValueError('Choose codex or claude.')
    after = cli_version(binary)
    print(f'{name}: after update: {after}', flush=True)
    return binary


def subscription_env():
    """Use stored subscription sign-in, like the readers; never alter the parent environment."""
    excluded = {
        'ANTHROPIC_AUTH_TOKEN', 'CLAUDE_CODE_OAUTH_TOKEN', 'ANTHROPIC_PROFILE',
        'CLAUDE_CODE_USE_BEDROCK', 'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY',
        'OPENAI_BASE_URL', 'CODEX_ACCESS_TOKEN',
    }
    return execution_env({key: value for key, value in os.environ.items()
            if key.upper() not in excluded and not key.upper().endswith('_API_KEY')})


def signed_in(name, binary):
    """Check subscription authentication without printing account details or credentials."""
    command = ['auth', 'status'] if name == 'claude' else ['login', 'status']
    try:
        result = subprocess.run([binary, *command], capture_output=True, timeout=20,
                                stdin=subprocess.DEVNULL, env=subscription_env(),
                                text=True, encoding='utf-8', errors='replace')
    except (OSError, subprocess.SubprocessError):
        raise RuntimeError(f'Could not check {name} sign-in. Retry installer.cmd reader {name} --login.') from None
    if result.returncode != 0:
        return False
    if name == 'claude':
        try:
            json.loads(result.stdout)
        except ValueError:
            raise RuntimeError('Claude returned an unreadable sign-in status. Check the Claude Code CLI version.') from None
    return subscription_confirmed(name, result.returncode, result.stdout, result.stderr)


def reader_names(name):
    if name in ('both', 'begge'):
        return ('codex', 'claude')
    if name not in ('codex', 'claude'):
        raise ValueError('Choose codex, claude or both.')
    return (name,)


def setup(name, *, allow_login=True, force_login=False):
    """Install, reuse subscription sign-in, or log in and verify before reporting success."""
    readers = reader_names(name)
    if len(readers) > 1:
        failures = []
        for reader in readers:
            try:
                setup(reader, allow_login=allow_login, force_login=force_login)
            except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
                failures.append(f'{reader}: {exc}')
                print(f'{reader}: setup incomplete; continuing with the other selected reader.', flush=True)
        if failures:
            raise RuntimeError(' '.join(failures) + ' Successful sign-ins are kept.')
        return
    binary = install(name)
    print(f'{name}: using {binary}', flush=True)
    subprocess.run([binary, '--version'], check=True, env=subscription_env())
    print(f'{name}: to check for CLI updates, run installer.cmd reader {name} --update.', flush=True)
    if not force_login and signed_in(name, binary):
        print(f'{name}: existing subscription sign-in confirmed; no new login needed.', flush=True)
        return
    if not allow_login:
        raise RuntimeError(f'{name}: subscription sign-in is not confirmed. '
                           f'Run installer.cmd reader {name} --login in a terminal.')
    print(f'{name}: complete subscription sign-in in your browser using the intended account. '
          'This window will wait, then verify sign-in.', flush=True)
    command = ['auth', 'login'] if name == 'claude' else ['login']
    try:
        subprocess.run([binary, *command], check=True, env=subscription_env())
    except (OSError, subprocess.SubprocessError):
        raise RuntimeError(f'{name}: sign-in did not complete. Retry installer.cmd reader {name} --login.') from None
    if not signed_in(name, binary):
        raise RuntimeError(f'{name}: subscription sign-in could not be verified after login. '
                           f'Run installer.cmd reader {name} --login and choose your subscription account.')
    print(f'{name}: subscription sign-in verified.', flush=True)


def install(name):
    if name not in ('codex', 'claude'):
        raise ValueError('Choose codex or claude.')
    found = find_cli(name)
    if Path(found).is_file() or shutil.which(found):
        return found
    if os.name != 'nt':
        raise RuntimeError('Automatic CLI installation currently supports Windows only.')
    if name == 'claude':
        subprocess.run(['winget','install','--id','Anthropic.ClaudeCode','--exact',
                        '--accept-package-agreements','--accept-source-agreements'], check=True)
        found = find_cli(name)
        if found == name and not shutil.which(found):
            raise RuntimeError('WinGet completed, but the Claude Code executable could not be located. '
                               'Set SDA_CLAUDE_BIN to its full path and retry installer.cmd reader claude.')
        return found
    target = Path(os.environ['LOCALAPPDATA'])/'systematic-document-analysis/readers/codex/codex.exe'
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.download')
    print('Downloading the official Codex CLI into a private local folder.', flush=True)
    urllib.request.urlretrieve(CODEX_URL, temporary)
    with temporary.open('rb') as downloaded:
        digest = hashlib.file_digest(downloaded, 'sha256').hexdigest()
    if digest != CODEX_SHA256:
        temporary.unlink(missing_ok=True)
        raise RuntimeError('Codex download checksum mismatch; installation stopped.')
    temporary.replace(target)
    return str(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reader', nargs='?', choices=('codex','claude','both','begge'))
    parser.add_argument('--login', action='store_true',
                        help='Sign in again, even if already authenticated, to choose an account.')
    parser.add_argument('--update', action='store_true',
                        help='Update the selected reader CLI where this installer manages it.')
    args = parser.parse_args()
    if args.login and args.update:
        parser.error('--login and --update are separate actions.')
    force_login = args.login
    if args.reader is None:
        print('Set up subscription reading: 1 = Codex, 2 = Claude Code, 3 = Both / Begge')
        args.reader = {'1':'codex','2':'claude','3':'both'}.get(input('Choose 1, 2 or 3: ').strip())
        if args.reader is None:
            parser.error('Invalid choice. No installation started.')
        if not args.update:
            args.login = True
    if args.update:
        failures = []
        for reader in reader_names(args.reader):
            try:
                update(reader)
            except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
                failures.append(f'{reader}: {exc}')
                print(f'{reader}: update incomplete; continuing with the other selected reader.', flush=True)
        if failures:
            raise RuntimeError(' '.join(failures))
    elif args.login:
        setup(args.reader, force_login=force_login)
    else:
        for reader in reader_names(args.reader):
            binary = install(reader)
            subprocess.run([binary, '--version'], check=True)
        print(f'To sign in: installer.cmd reader {args.reader} --login')
        print(f'To check for CLI updates: installer.cmd reader {args.reader} --update')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError, KeyboardInterrupt, EOFError) as exc:
        print(f'Reader setup incomplete: {exc or "cancelled"}', file=sys.stderr)
        sys.exit(1)
