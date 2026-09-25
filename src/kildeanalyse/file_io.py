"""Preserve files with Windows long-path support, including CopyFile2 on Python 3.12."""
import os
from pathlib import Path
import shutil


def native_path(path):
    """Use extended Windows paths for filesystem operations, without registry changes."""
    value = str(Path(path).absolute())
    if os.name != 'nt' or value.startswith('\\\\?\\'):
        return Path(value)
    return Path('\\\\?\\UNC\\' + value[2:] if value.startswith('\\\\') else '\\\\?\\' + value)


def display_path(path):
    value = str(path)
    if value.startswith('\\\\?\\UNC\\'):
        value = '\\\\' + value[8:]
    elif value.startswith('\\\\?\\'):
        value = value[4:]
    return Path(value)


def copy_file(source, target):
    shutil.copy2(native_path(source), native_path(target))
    return Path(target)
