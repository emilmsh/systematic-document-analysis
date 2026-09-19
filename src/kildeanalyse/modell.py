"""Datamodell: kriterier, plan, inputpakke og motorsvar.

Begreper (se UTVIKLINGSSTRATEGI.md del 5): et prosjekt rommer analyser; en analyse har en
versjonert arbeidsplan; en kjøring utfører planens instruks på én inputpakke (her: ett
dokument) og kan ha flere forsøk.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

HELTALL = "<heltall>"
_HELTALL_RE = re.compile(r"-?\d+")


def _er_heltall(svar: str) -> bool:
    return _HELTALL_RE.fullmatch(svar.strip()) is not None


@dataclass
class Kriterium:
    id: str
    navn: str
    sporsmal: str
    tillatte_svar: list[str]
    krever_belegg_ved: list[str] = field(default_factory=list)
    regel: str = ""
    # Bare for simulert motor: ord som brukes til å finne en setning i dokumentet.
    sokeord: list[str] = field(default_factory=list)

    @classmethod
    def fra_dict(cls, d: dict[str, Any]) -> "Kriterium":
        return cls(
            id=str(d["id"]),
            navn=str(d.get("navn", d["id"])),
            sporsmal=str(d.get("spørsmål") or d.get("sporsmal") or ""),
            tillatte_svar=[str(s) for s in d["tillatte_svar"]],
            krever_belegg_ved=[str(s) for s in d.get("krever_belegg_ved", [])],
            regel=str(d.get("regel", "")),
            sokeord=[str(s) for s in d.get("sokeord", [])],
        )

    def til_dict(self) -> dict[str, Any]:
        return asdict(self)

    def svar_er_tillatt(self, svar: str) -> bool:
        if svar in self.tillatte_svar:
            return True
        return HELTALL in self.tillatte_svar and _er_heltall(svar)

    def krever_belegg(self, svar: str) -> bool:
        if svar in self.krever_belegg_ved:
            return True
        return HELTALL in self.krever_belegg_ved and _er_heltall(svar)

    def svar_uten_beleggkrav(self) -> list[str]:
        return [s for s in self.tillatte_svar if s != HELTALL and not self.krever_belegg(s)]


@dataclass
class Plan:
    """Innholdet i én planversjon. Lagres som JSON i planversjon.plan_json."""

    formaal: str
    kriterier: list[Kriterium]
    kriteriesett_navn: str = ""
    kriteriesett_versjon: str = ""
    kriteriesett_merknad: str = ""
    analyseenhet: str = "ett dokument per kjøring"
    leseregel_ikke_omtalt: str = ""
    tillat_sider_uten_tekst: bool = False
    motor: str = "simulert"
    modell: str = ""
    motorinnstillinger: dict[str, Any] = field(default_factory=dict)
    tilleggsinstruks: str = ""
    sprak: str = "nb"

    @classmethod
    def fra_kriteriefil(
        cls,
        kriteriefil: dict[str, Any],
        *,
        formaal: str,
        motor: str = "simulert",
        modell: str = "",
        motorinnstillinger: dict[str, Any] | None = None,
        tilleggsinstruks: str = "",
        tillat_sider_uten_tekst: bool = False,
        sprak: str = "nb",
    ) -> "Plan":
        return cls(
            formaal=formaal,
            kriterier=[Kriterium.fra_dict(k) for k in kriteriefil["kriterier"]],
            kriteriesett_navn=str(kriteriefil.get("navn", "")),
            kriteriesett_versjon=str(kriteriefil.get("versjon", "")),
            kriteriesett_merknad=str(kriteriefil.get("_merknad", "")),
            analyseenhet=str(kriteriefil.get("analyseenhet", "one document per run" if sprak == "en" else "ett dokument per kjøring")),
            leseregel_ikke_omtalt=str(kriteriefil.get("leseregel_ikke_omtalt", "")),
            tillat_sider_uten_tekst=tillat_sider_uten_tekst,
            motor=motor,
            modell=modell,
            motorinnstillinger=dict(motorinnstillinger or {}),
            tilleggsinstruks=tilleggsinstruks,
            sprak=sprak,
        )

    @classmethod
    def fra_dict(cls, d: dict[str, Any]) -> "Plan":
        d = dict(d)
        d["kriterier"] = [Kriterium.fra_dict(k) for k in d["kriterier"]]
        return cls(**d)

    def til_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["kriterier"] = [k.til_dict() for k in self.kriterier]
        return d

    def kriterium(self, kriterium_id: str) -> Kriterium | None:
        for k in self.kriterier:
            if k.id == kriterium_id:
                return k
        return None


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

    def hash(self) -> str:
        innhold = json.dumps(
            {"systeminstruks": self.systeminstruks, "brukermelding": self.brukermelding, "svarskjema": self.svarskjema,
             **({"kjoreparametre": self.kjoreparametre} if self.kjoreparametre else {}),
             **({"api_foresporsel": self.api_foresporsel} if self.api_foresporsel else {})},
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(innhold.encode("utf-8")).hexdigest()

    def til_dict(self) -> dict[str, Any]:
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
