"""Datamodell: oppgaveplan, inputpakke og motorsvar.

Begreper: et prosjekt rommer analyser; en analyse har en
versjonert arbeidsplan; en kjøring utfører planens instruks på én inputpakke (her: ett
dokument) og kan ha flere forsøk.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

@dataclass
class Plan:
    """One versioned task and its execution settings."""
    formaal: str
    task_instructions: str = ''
    output_schema: dict[str, Any] | None = None
    quote_checks: list[dict[str, Any]] = field(default_factory=list)
    tillat_sider_uten_tekst: bool = False
    motor: str = 'simulert'
    modell: str = ''
    motorinnstillinger: dict[str, Any] = field(default_factory=dict)
    tilleggsinstruks: str = ''
    sprak: str = 'nb'

    @classmethod
    def fra_dict(cls, data):
        return cls(**data)

    def til_dict(self):
        return asdict(self)


@dataclass
class Side:
    nr: int  # fysisk side fra 1
    tekst: str
    tegn: int
    source: dict[str, Any] = field(default_factory=dict)


@dataclass
class Inputpakke:
    """Nøyaktig det som sendes til motoren for ett forsøk."""

    forsok_id: str
    kjoring_id: str
    dokument_id: str
    dokument_navn: str
    dokument_sha256: str
    sider: list[Side]
    systeminstruks: str
    brukermelding: str
    svarskjema: dict[str, Any]
    kjoreparametre: dict[str, Any] = field(default_factory=dict)
    api_foresporsel: dict[str, Any] | None = None
    source_metadata: dict[str, Any] = field(default_factory=dict)
    local_source_path: str | None = field(default=None, repr=False)

    def hash(self) -> str:
        from .reader_files import access
        innhold = json.dumps(
            {"systeminstruks": self.systeminstruks, "brukermelding": self.brukermelding, "svarskjema": self.svarskjema,
             **({"kjoreparametre": self.kjoreparametre} if self.kjoreparametre else {}),
             **({"api_foresporsel": self.api_foresporsel} if self.api_foresporsel else {}),
             **({'file_access': access(self)} if access(self) else {})},
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(innhold.encode("utf-8")).hexdigest()

    def til_dict(self) -> dict[str, Any]:
        from .reader_files import access
        return {
            "forsok_id": self.forsok_id,
            "kjoring_id": self.kjoring_id,
            "dokument_id": self.dokument_id,
            "dokument_navn": self.dokument_navn,
            "dokument_sha256": self.dokument_sha256,
            "sider_sendt": [s.nr for s in self.sider],
            "source_units": [{'unit_id':s.nr, **(s.source or {'kind':'pdf_page', 'page':s.nr, 'location':f'PDF page {s.nr}'})} for s in self.sider],
            "source_metadata": self.source_metadata,
            "systeminstruks": self.systeminstruks,
            "brukermelding": self.brukermelding,
            "svarskjema": self.svarskjema,
            "kjoreparametre": self.kjoreparametre,
            **({"api_foresporsel": self.api_foresporsel} if self.api_foresporsel else {}),
            "input_hash": self.hash(),
            **({'file_access': access(self)} if access(self) else {}),
        }


@dataclass
class Stotte:
    ok: bool
    meldinger: list[str] = field(default_factory=list)
    egenskaper: dict[str, Any] = field(default_factory=dict)


@dataclass
class Motorsvar:
    raasvar: str
    svar: dict[str, Any] | None
    sesjon_id: str | None = None
    modell_rapportert: str | None = None
    forbruk: dict[str, Any] | None = None
    hendelser: list[dict[str, Any]] = field(default_factory=list)
    feil: str | None = None
    motorinfo: dict[str, Any] = field(default_factory=dict)
    avbrutt: bool = False
