"""Install a reader CLI if missing; sign-in remains an explicit user action."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from kildeanalyse.cli_paths import find_cli, execution_env
from kildeanalyse.cli_auth import subscription_confirmed

CODEX_URL = 'https://github.com/openai/codex/releases/download/rust-v0.155.1/codex-x86_64-pc-windows-msvc.exe'
CODEX_SHA256 = 'eba0f32c976667cb9298efafd98513e823eeda7b576a03ec658bb8be8d336316'


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


def setup(name, *, allow_login=True, force_login=False):
    """Install, reuse subscription sign-in, or log in and verify before reporting success."""
    binary = install(name)
    print(f'{name}: using {binary}', flush=True)
    subprocess.run([binary, '--version'], check=True, env=subscription_env())
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
    parser.add_argument('reader', nargs='?', choices=('codex','claude'))
    parser.add_argument('--login', action='store_true',
                        help='Sign in again, even if already authenticated, to choose an account.')
    args = parser.parse_args()
    force_login = args.login
    if args.reader is None:
        print('Set up a subscription reader and sign in: 1 = Codex, 2 = Claude Code')
        args.reader = {'1':'codex','2':'claude'}.get(input('Choose 1 or 2: ').strip())
        if args.reader is None:
            parser.error('Invalid choice. No installation started.')
        args.login = True
    if args.login:
        setup(args.reader, force_login=force_login)
    else:
        binary = install(args.reader)
        subprocess.run([binary, '--version'], check=True)
        print(f'To sign in: installer.cmd reader {args.reader} --login')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError, KeyboardInterrupt, EOFError) as exc:
        print(f'Reader setup incomplete: {exc or "cancelled"}', file=sys.stderr)
        sys.exit(1)
