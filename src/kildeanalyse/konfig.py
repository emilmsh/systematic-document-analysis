"""Plassering av data utenfor kildekoden.

Standard er %LOCALAPPDATA%\\oe-kildeanalyse på Windows. Miljøvariabelen
OE_KILDEANALYSE_DATA overstyrer. Mappen inneholder SQLite-basen, bevarte
dokumentkopier, inputpakker per forsøk og eksporter.
"""
from __future__ import annotations

import os
from pathlib import Path


def datamappe() -> Path:
    env = os.environ.get("OE_KILDEANALYSE_DATA")
    if env:
        mappe = Path(env)
    else:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
        mappe = Path(base) / "oe-kildeanalyse"
    mappe.mkdir(parents=True, exist_ok=True)
    return mappe


def undermappe(navn: str, rot: Path | None = None) -> Path:
    mappe = (rot or datamappe()) / navn
    mappe.mkdir(parents=True, exist_ok=True)
    return mappe
