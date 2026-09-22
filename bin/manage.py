"""One Windows entry point for installation and maintenance; standard library only."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
ACTIONS = {
    'install': ('installer.py', []),
    'repair': ('installer.py', ['--repair']),
    'recover': ('installer.py', ['--recover']),
    'reader': ('setup_reader.py', []),
    'ocr': ('setup_ocr.py', []),
    'settings': ('configure_keys.py', []),
    'update': ('update_plugin.py', []),
}
HELP = '''Systematic Document Analysis

Double-click installer.cmd for the menu, or use:
  installer.cmd install [claude|codex|both] [installation options]
  installer.cmd repair [claude|codex|both]
  installer.cmd recover [claude|codex|both]
  installer.cmd reader [claude|codex] [--login]
  installer.cmd ocr
  installer.cmd settings
  installer.cmd update [--check|--install|--mode notify|auto|off]

For updates, open installer.cmd in the installed plugin folder.
Existing commands such as installer.cmd both --non-interactive still work.
Use installer.cmd install --help for advanced installation options.
'''


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ['--help'] or args == ['-h']:
        print(HELP)
        return 0
    try:
        if not args:
            if not sys.stdin.isatty():
                print('Choose an action or host. Use installer.cmd --help.', file=sys.stderr)
                return 2
            print('Systematic Document Analysis\n'
                  '1 = Install / Installer\n'
                  '2 = Repair plugin / Reparer plugin\n'
                  '3 = Reader sign-in / Lesermotor og innlogging\n'
                  '4 = Set up or repair OCR / Klargjor eller reparer OCR\n'
                  '5 = API settings / API-innstillinger\n'
                  '6 = Updates / Oppdateringer\n'
                  '7 = Recover interrupted installation / Gjenopprett avbrutt installasjon\n'
                  '0 = Exit / Avslutt')
            choices = {'1': 'install', '2': 'repair', '3': 'reader', '4': 'ocr',
                       '5': 'settings', '6': 'update', '7': 'recover'}
            while not args:
                choice = input('Choose / Velg 0-7: ').strip()
                if choice == '0':
                    return 0
                if choice in choices:
                    args = [choices[choice]]
                else:
                    print('Choose a number from 0 to 7.')
        if args[0] in ACTIONS:
            script, flags = ACTIONS[args.pop(0)]
        else:
            # Preserve direct installer flags/host syntax used by older instructions.
            script, flags = ACTIONS['install']
        if script in ('setup_ocr.py', 'configure_keys.py') and args:
            print('This action takes no additional arguments.', file=sys.stderr)
            return 2
        return subprocess.run([sys.executable, '-X', 'utf8', str(ROOT/script), *args, *flags]).returncode
    except (OSError, KeyboardInterrupt, EOFError) as exc:
        print(f'Setup stopped: {exc or "cancelled"}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
