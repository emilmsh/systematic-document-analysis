"""Install the same Windows package in Claude Code, Codex or both."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from pakk_plugin import ROOT, pakk
from setup_reader import install as ensure_reader

NAME = 'systematic-document-analysis'
MARKET = 'systematic-document-analysis-local'


def prepare(host, base):
    target = Path(base).resolve()/host/NAME
    pakk(target, codex=host == 'codex')
    return target


def run(command):
    print('Running: ' + subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, check=True)


def install(host, base):
    exe = ensure_reader(host)
    target = prepare(host, base)
    if host == 'claude':
        items = json.loads(subprocess.check_output([exe,'plugin','marketplace','list','--json'], encoding='utf-8'))
        existing = next((m for m in items if m['name'] == MARKET), None)
        if existing:
            if existing.get('source') != 'directory' or Path(existing.get('path','')).resolve() != target:
                raise RuntimeError(f'{MARKET} is already registered from a different directory. Update that installation or remove its marketplace registration before reinstalling. The existing registration was not changed.')
            run([exe,'plugin','marketplace','update',MARKET])
        else:
            run([exe,'plugin','marketplace','add',str(target)])
        # install er idempotent; update plukker opp nyere versjoner etter install.
        run([exe,'plugin','install',f'{NAME}@{MARKET}'])
        run([exe,'plugin','update',f'{NAME}@{MARKET}'])
    else:
        run([exe,'plugin','marketplace','add',str(target)])
        run([exe,'plugin','add',f'{NAME}@{MARKET}'])
    print(f'{host}: installed. Start a new conversation to load the plugin.')
    print(f'For subscription reading, sign in once with: reader_setup.cmd {host} --login')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app', nargs='?', choices=['claude','codex','both','begge'])
    parser.add_argument('--base-dir', type=Path, default=Path(os.environ.get('LOCALAPPDATA',Path.home()))/'systematic-document-analysis'/'plugins')
    parser.add_argument('--prepare-only', action='store_true', help='Prepare copies without registering in either app')
    args = parser.parse_args()
    if sys.version_info < (3,12):
        parser.error('Python 3.12 or newer is required.')
    if os.name != 'nt':
        parser.error('This installation package currently supports Windows only.')
    app = args.app
    if not app:
        print('Install Systematic Document Analysis: 1 = Claude Code, 2 = Codex, 3 = both')
        app = {'1':'claude','2':'codex','3':'begge'}.get(input('Choose 1, 2 or 3: ').strip())
        if not app:
            parser.error('Invalid choice; installation has not started.')
    try:
        for host in (['claude','codex'] if app in ('both','begge') else [app]):
            if args.prepare_only:
                print(prepare(host,args.base_dir))
            else:
                install(host,args.base_dir)
    except (RuntimeError,OSError,ValueError,subprocess.SubprocessError) as exc:
        print(f'Installation stopped: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
