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
    'reader-update': ('setup_reader.py', ['--update']),
    'ocr': ('setup_ocr.py', []),
    'settings': ('configure_keys.py', []),
    'update': ('update_plugin.py', []),
}
HELP = '''Systematic Document Analysis

Double-click installer.cmd for the menu, or use:
  installer.cmd install [claude|codex|both] [installation options]
  installer.cmd repair [claude|codex|both]
  installer.cmd recover [claude|codex|both]
  installer.cmd reader [claude|codex|both] [--login]
  installer.cmd reader [claude|codex|both] --update
  installer.cmd ocr
  installer.cmd settings
  installer.cmd update [--check|--install|--mode notify|auto|off]

For updates, open installer.cmd in the installed plugin folder.
Existing commands such as installer.cmd both --non-interactive still work.
Use installer.cmd install --help for advanced installation options.
'''


def choose(title, options, *, back=False):
    print('\n' + title)
    for number, (_, label) in enumerate(options, 1):
        print(f'{number} = {label}')
    print('0 = Back / Tilbake' if back else '0 = Exit / Avslutt')
    while True:
        choice = input(f'Choose / Velg 0-{len(options)}: ').strip()
        if choice == '0':
            return None
        if choice in {str(number) for number in range(1, len(options) + 1)}:
            return options[int(choice) - 1][0]
        print(f'Choose a number from 0 to {len(options)}.')


def menu_action():
    while True:
        action = choose('Systematic Document Analysis', [
            ('install', 'Install / Installer'),
            ('account', 'Sign-in and settings / Innlogging og innstillinger'),
            ('maintenance', 'Update or repair / Oppdater eller reparer'),
        ])
        if action in (None, 'install'):
            return action
        if action == 'account':
            action = choose('Sign-in and settings / Innlogging og innstillinger', [
                ('reader', 'Reader sign-in / Lesermotor og innlogging'),
                ('settings', 'API settings / API-innstillinger'),
            ], back=True)
        else:
            action = choose('Update or repair / Oppdater eller reparer', [
                ('update', 'Updates / Oppdateringer'),
                ('repair', 'Repair plugin / Reparer plugin'),
                ('ocr', 'Repair OCR / Reparer OCR'),
                ('recover', 'Recover interrupted installation / Gjenopprett avbrutt installasjon'),
                ('reader-update', 'Check/update reader CLIs / Kontroller/oppdater leser-CLI-er'),
            ], back=True)
        if action is not None:
            return action


def run_action(args):
    args = list(args)
    if args[0] in ACTIONS:
        script, flags = ACTIONS[args.pop(0)]
    else:
        # Preserve direct installer flags/host syntax used by older instructions.
        script, flags = ACTIONS['install']
    if script in ('setup_ocr.py', 'configure_keys.py') and args:
        print('This action takes no additional arguments.', file=sys.stderr)
        return 2
    return subprocess.run([sys.executable, '-X', 'utf8', str(ROOT/script), *args, *flags]).returncode


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
            result = 0
            while True:
                action = menu_action()
                if action is None:
                    return result
                try:
                    status = run_action([action])
                except OSError as exc:
                    print(f'Could not start action / Kunne ikke starte handlingen: {exc}', file=sys.stderr)
                    status = 1
                # Keep failures visible even if another action succeeds later.
                result = result or status
                title = ('Action finished / Handlingen er ferdig' if status == 0 else
                         f'Action incomplete / Handlingen ble ikke fullført (exit code {status})')
                if choose(title, [('menu', 'Return to start menu / Tilbake til startmenyen')]) is None:
                    return result
        return run_action(args)
    except (OSError, KeyboardInterrupt, EOFError) as exc:
        print(f'Setup stopped: {exc or "cancelled"}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
