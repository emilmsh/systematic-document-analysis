"""Installer den samme pakken i Claude Code, Codex eller begge på Windows."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from pakk_plugin import ROOT, pakk

NAME = 'oe-kildeanalyse'
MARKET = 'oe-kildeanalyse-lokal'


def prepare(host, base):
    target = Path(base).resolve()/host/NAME
    pakk(target, codex=host == 'codex')
    return target


def run(command):
    print('Kjører: ' + subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, check=True)


def install(host, base):
    exe = shutil.which(host)
    if not exe:
        raise RuntimeError(f'Fant ikke {host} på PATH. Installer CLI-en og åpne terminalen på nytt.')
    target = prepare(host, base)
    if host == 'claude':
        items = json.loads(subprocess.check_output([exe,'plugin','marketplace','list','--json'], encoding='utf-8'))
        existing = next((m for m in items if m['name'] == MARKET), None)
        if existing:
            if existing.get('source') != 'directory' or Path(existing.get('path','')).resolve() != target:
                raise RuntimeError(f'{MARKET} er allerede registrert fra en annen mappe. Oppdater den eksisterende installasjonen, eller fjern bare markedsplassregistreringen før ny installasjon. Eksisterende registrering er ikke endret.')
            run([exe,'plugin','marketplace','update',MARKET])
        else:
            run([exe,'plugin','marketplace','add',str(target)])
        # install er idempotent; update plukker opp nyere versjoner etter install.
        run([exe,'plugin','install',f'{NAME}@{MARKET}'])
        run([exe,'plugin','update',f'{NAME}@{MARKET}'])
    else:
        run([exe,'plugin','marketplace','add',str(target)])
        run([exe,'plugin','add',f'{NAME}@{MARKET}'])
    print(f'{host}: installert. Start en ny samtale for å laste pluginen.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app', nargs='?', choices=['claude','codex','begge'])
    parser.add_argument('--base-dir', type=Path, default=Path(os.environ.get('LOCALAPPDATA',Path.home()))/'oe-kildeanalyse'/'plugins')
    parser.add_argument('--prepare-only', action='store_true', help='Klargjør kopier uten å registrere i appene')
    args = parser.parse_args()
    if sys.version_info < (3,12):
        parser.error('Python 3.12 eller nyere kreves.')
    if os.name != 'nt':
        parser.error('Denne installasjonspakken støtter foreløpig Windows.')
    app = args.app
    if not app:
        print('Installer OE Kildeanalyse: 1 = Claude Code, 2 = Codex, 3 = begge')
        app = {'1':'claude','2':'codex','3':'begge'}.get(input('Velg 1, 2 eller 3: ').strip())
        if not app:
            parser.error('Ugyldig valg; ingen installasjon er startet.')
    try:
        for host in (['claude','codex'] if app == 'begge' else [app]):
            if args.prepare_only:
                print(prepare(host,args.base_dir))
            else:
                install(host,args.base_dir)
    except (RuntimeError,OSError,ValueError,subprocess.SubprocessError) as exc:
        print(f'Installasjonen stoppet: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
