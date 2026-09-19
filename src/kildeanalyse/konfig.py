"""Data storage outside source: SDA_DATA, legacy override, or a compatible default."""
from __future__ import annotations

import os
from pathlib import Path


def datamappe() -> Path:
    env = os.environ.get("SDA_DATA") or os.environ.get("OE_KILDEANALYSE_DATA")
    if env:
        mappe = Path(env)
    else:
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
        legacy = Path(base) / 'oe-kildeanalyse'
        current = Path(base) / 'systematic-document-analysis'
        # Existing records stay in place; a rename must not create an empty replacement database.
        if (legacy/'kildeanalyse.sqlite').exists() and (current/'kildeanalyse.sqlite').exists():
            raise RuntimeError('Two data stores found. Set SDA_DATA explicitly to select one; neither was changed.')
        mappe = legacy if (legacy/'kildeanalyse.sqlite').exists() else current
    mappe.mkdir(parents=True, exist_ok=True)
    return mappe


def undermappe(navn: str, rot: Path | None = None) -> Path:
    mappe = (rot or datamappe()) / navn
    mappe.mkdir(parents=True, exist_ok=True)
    return mappe
