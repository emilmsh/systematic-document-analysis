"""Data storage outside source, with an explicit SDA_DATA override."""
from __future__ import annotations

import os
from pathlib import Path


def brukermappe() -> Path:
    """One root for every app and terminal.

    The Claude and Codex desktop apps from the Microsoft Store redirect writes below
    %LOCALAPPDATA% into a private hidden copy per app, so data there would split
    between apps. The user profile itself is not redirected.
    """
    return Path.home() / '.systematic-document-analysis'


def datamappe() -> Path:
    env = os.environ.get("SDA_DATA")
    mappe = Path(env) if env else brukermappe() / 'data'
    mappe.mkdir(parents=True, exist_ok=True)
    return mappe


def undermappe(navn: str, rot: Path | None = None) -> Path:
    mappe = (rot or datamappe()) / navn
    mappe.mkdir(parents=True, exist_ok=True)
    return mappe
