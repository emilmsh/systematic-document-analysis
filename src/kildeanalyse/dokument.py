"""Dokumentbehandling: import, bevart kopi, tekstuttrekk per fysisk side og sitatkontroll.

Første prototype leser PDF med tekstlag via pypdf. Sider uten tekst oppdages og gjør
dokumentet «uleselig» eller «delvis» lesbart; tekstuttrekk beviser ikke at innholdet er
riktig lest, men gir grunnlaget for belegg og lesedekning.
"""
from __future__ import annotations

import hashlib
import re
import shutil
import unicodedata
from pathlib import Path
from typing import Any

from pypdf import PdfReader
import pypdf

from .konfig import undermappe
from .lager import Lager

LESBAR, DELVIS, ULESELIG = "lesbar", "delvis", "uleselig"
MIN_TEGN_PER_SIDE = 25


class DokumentFeil(Exception):
    pass


def sha256_fil(sti: Path) -> str:
    h = hashlib.sha256()
    with open(sti, "rb") as f:
        for blokk in iter(lambda: f.read(1 << 20), b""):
            h.update(blokk)
    return h.hexdigest()


def trekk_ut_tekst(sti: Path) -> tuple[list[dict[str, Any]], str, str]:
    """Returnerer (sider, lesbarhet, metode). Hver side: {nr, tegn, tekst}."""
    try:
        leser = PdfReader(str(sti))
        if leser.is_encrypted:
            try:
                leser.decrypt("")
            except Exception as e:  # noqa: BLE001
                raise DokumentFeil(f"PDF-en er kryptert og kunne ikke åpnes: {e}") from e
        sider = []
        for i, side in enumerate(leser.pages, start=1):
            tekst = side.extract_text() or ""
            tegn = len(re.sub(r"\s+", "", tekst))
            sider.append({"nr": i, "tegn": tegn, "tekst": tekst})
    except DokumentFeil:
        raise
    except Exception as e:  # noqa: BLE001
        raise DokumentFeil(f"Kunne ikke lese PDF: {e}") from e
    if not sider:
        raise DokumentFeil("PDF-en har ingen sider.")
    uten_tekst = [s["nr"] for s in sider if s["tegn"] < MIN_TEGN_PER_SIDE]
    if len(uten_tekst) == len(sider):
        lesbarhet = ULESELIG
    elif uten_tekst:
        lesbarhet = DELVIS
    else:
        lesbarhet = LESBAR
    return sider, lesbarhet, f"pypdf {pypdf.__version__}"


def importer_dokument(lager: Lager, prosjekt_id: str, sti: str | Path) -> tuple[dict[str, Any], bool]:
    """Kopierer filen inn i datamappen, trekker ut tekst og registrerer dokumentet.

    Returnerer (dokument, nytt). Samme innhold (SHA-256) i samme prosjekt gjenbrukes.
    """
    kilde = Path(sti)
    if not kilde.is_file():
        raise DokumentFeil(f"Finner ikke filen «{kilde}».")
    if kilde.suffix.lower() != ".pdf":
        raise DokumentFeil(f"Bare PDF støttes i denne versjonen. Fikk «{kilde.suffix}» for {kilde.name}.")
    sha = sha256_fil(kilde)
    eksisterende = lager.finn_dokument_sha(prosjekt_id, sha)
    if eksisterende:
        eksisterende["sider"] = __import__("json").loads(eksisterende.pop("sider_json"))
        return eksisterende, False
    kopi = undermappe("dokumenter", lager.mappe) / f"{sha}.pdf"
    if not kopi.exists():
        shutil.copy2(kilde, kopi)
    sider, lesbarhet, metode = trekk_ut_tekst(kopi)
    dok = lager.legg_til_dokument(
        prosjekt_id,
        navn=kilde.name,
        sha256=sha,
        bytes=kopi.stat().st_size,
        antall_sider=len(sider),
        lesbarhet=lesbarhet,
        sider=sider,
        kilde_opphav=str(kilde.resolve()),
        uttrekk_metode=metode,
        lagret_kopi=str(kopi),
    )
    return dok, True


def sider_uten_tekst(dokument: dict[str, Any]) -> list[int]:
    return [s["nr"] for s in dokument["sider"] if s["tegn"] < MIN_TEGN_PER_SIDE]


# --- sitatkontroll -------------------------------------------------------------------

_BINDESTREKER = dict.fromkeys(map(ord, "‐‑‒–—―−"), "-")
_SITATTEGN = {ord(c): '"' for c in "“”„«»"} | {ord(c): "'" for c in "‘’‚"}


def normaliser(tekst: str) -> str:
    """Gjør tekst sammenlignbar: NFKC, myke bindestreker bort, ens strek- og sitattegn, ett mellomrom, små bokstaver."""
    t = unicodedata.normalize("NFKC", tekst)
    t = t.replace("­", "")
    t = t.translate(_BINDESTREKER).translate(_SITATTEGN)
    t = re.sub(r"\s+", " ", t).strip()
    return t.casefold()


def sitat_finnes(sitat: str, sidetekst: str) -> bool:
    s = normaliser(sitat)
    if not s:
        return False
    if s in normaliser(sidetekst):
        return True
    # Tillat at et linjeskift i PDF-en har delt et ord med bindestrek: «arbeids-\ntrening».
    uten_orddeling = re.sub(r"-\s+", "", normaliser(sidetekst))
    return s in uten_orddeling


def finn_sitat_side(sitat: str, sider: list[dict[str, Any]]) -> int | None:
    for side in sider:
        if sitat_finnes(sitat, side["tekst"]):
            return side["nr"]
    return None
