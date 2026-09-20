"""Install a reader CLI if missing; sign-in remains an explicit user action."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from kildeanalyse.cli_paths import find_cli

CODEX_URL = 'https://github.com/openai/codex/releases/download/rust-v0.155.1/codex-x86_64-pc-windows-msvc.exe'
CODEX_SHA256 = 'eba0f32c976667cb9298efafd98513e823eeda7b576a03ec658bb8be8d336316'


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
            raise RuntimeError('Claude Code installed. Restart this installer to refresh PATH, then retry.')
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
    parser.add_argument('--login', action='store_true')
    args = parser.parse_args()
    if args.reader is None:
        print('Set up a subscription reader and sign in: 1 = Codex, 2 = Claude Code')
        args.reader = {'1':'codex','2':'claude'}.get(input('Choose 1 or 2: ').strip())
        if args.reader is None:
            parser.error('Invalid choice. No installation started.')
        args.login = True
    binary = install(args.reader)
    subprocess.run([binary, '--version'], check=True)
    if args.login:
        command = ['login'] if args.reader == 'codex' else ['auth','login']
        subprocess.run([binary, *command], check=True)
    else:
        print(f'To sign in: reader_setup.cmd {args.reader} --login')


if __name__ == '__main__':
    main()
