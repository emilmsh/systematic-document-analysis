"""Dokumentbehandling: import, bevart kopi, tekstuttrekk per fysisk side.

Første prototype leser PDF med tekstlag via pypdf. Sider uten tekst oppdages og gjør
dokumentet «uleselig» eller «delvis» lesbart; tekstuttrekk beviser ikke at innholdet er
riktig lest, men gir grunnlaget for belegg og lesedekning.
"""
from __future__ import annotations

import hashlib
import re
from .file_io import copy_file
from pathlib import Path
from typing import Any

from pypdf import PdfReader
import pypdf

from .konfig import undermappe
from .lager import Lager
from .source_formats import SUPPORTED, extract

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


def importer_dokument(lager: Lager, prosjekt_id: str, sti: str | Path, *, ocr_mode: str = 'off', ocr_languages: str = 'eng+nor') -> tuple[dict[str, Any], bool]:
    """Kopierer filen inn i datamappen, trekker ut tekst og registrerer dokumentet.

    Returnerer (dokument, nytt). Samme innhold (SHA-256) i samme prosjekt gjenbrukes.
    """
    kilde = Path(sti)
    if not kilde.is_file():
        raise DokumentFeil(f"Finner ikke filen «{kilde}».")
    if kilde.suffix.lower() not in SUPPORTED:
        raise DokumentFeil(f"Unsupported format «{kilde.suffix}». Supported: {', '.join(sorted(SUPPORTED))}.")
    sha = sha256_fil(kilde)
    if ocr_mode not in ('off', 'auto', 'force'):
        raise DokumentFeil('ocr_mode must be off, auto or force.')
    eksisterende = next((d for d in lager.dokumenter(prosjekt_id)
        if d['sha256'] == sha and Path(d['lagret_kopi']).suffix.lower() == kilde.suffix.lower()
        and (kilde.suffix.lower() != '.pdf' or
             (d.get('source_metadata', {}).get('ocr', {}).get('mode', 'off') == ocr_mode and
              (ocr_mode == 'off' or d.get('source_metadata', {}).get('ocr', {}).get('languages') == ocr_languages)))), None)
    if eksisterende:
        return lager.dokument(eksisterende['id']), False
    kopi = undermappe("dokumenter", lager.mappe) / f"{sha}{kilde.suffix.lower()}"
    if not kopi.exists():
        copy_file(kilde, kopi)
    source_metadata = {}
    if kilde.suffix.lower() == '.pdf':
        sider, lesbarhet, metode = trekk_ut_tekst(kopi)
        if ocr_mode != 'off':
            from .ocr import apply_pdf
            try:
                sider, ocr = apply_pdf(kopi, sider, mode=ocr_mode, languages=ocr_languages)
            except Exception as exc:
                raise DokumentFeil(f'Local OCR failed: {exc}') from exc
            empty = sum(s['tegn'] < MIN_TEGN_PER_SIDE for s in sider)
            lesbarhet = ULESELIG if empty == len(sider) else DELVIS if empty else LESBAR
            source_metadata = {'format':'pdf', 'scope':'PDF text with local OCR transcription; physical page references. Images are not semantically analysed.',
                               'ocr':ocr, 'structure':{}}
            if ocr['pages']:
                metode += ' + ' + ocr['engine']
    else:
        try:
            sider, source_metadata, metode = extract(kopi)
        except Exception as exc:
            raise DokumentFeil(f'Could not extract {kilde.name}: {exc}') from exc
        if not sider:
            raise DokumentFeil(f'No readable source units in {kilde.name}. The file was not analysed.')
        lesbarhet = LESBAR if all(s['readable'] for s in sider) else DELVIS
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
        source_metadata=source_metadata,
    )
    return dok, True


def sider_uten_tekst(dokument: dict[str, Any]) -> list[int]:
    return [s["nr"] for s in dokument["sider"] if not s.get('readable', s["tegn"] >= MIN_TEGN_PER_SIDE)]
