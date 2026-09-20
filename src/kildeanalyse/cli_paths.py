"""Locate reader CLIs without requiring changes to the user's PATH."""
import os
from pathlib import Path
import shutil


def find_cli(name):
    explicit = os.environ.get(f'SDA_{name.upper()}_BIN')
    if explicit:
        return explicit
    found = shutil.which(name)
    if found:
        return found
    base = Path(os.environ.get('LOCALAPPDATA', Path.home()/'.local/share'))
    for path in (base/'systematic-document-analysis/readers'/name/f'{name}.exe',
                 base/'Microsoft/WinGet/Links'/f'{name}.exe',
                 Path.home()/'.local/bin'/f'{name}.exe'):
        if path.is_file():
            return str(path)
    return name
