"""Data storage outside source, with an explicit SDA_DATA override."""
from __future__ import annotations

import os
from pathlib import Path


def datamappe() -> Path:
    env = os.environ.get("SDA_DATA")
    if env:
        mappe = Path(env)
    else:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
        mappe = Path(base) / 'systematic-document-analysis'
    mappe.mkdir(parents=True, exist_ok=True)
    return mappe


def undermappe(navn: str, rot: Path | None = None) -> Path:
    mappe = (rot or datamappe()) / navn
    mappe.mkdir(parents=True, exist_ok=True)
    return mappe
