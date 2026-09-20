"""Simulert motor: ingen nett- eller modellkall.

Lager deterministiske svar ut fra enkle regler over dokumentteksten, slik at hele flyten
(kø, lagring, validering, kontroll, eksport) kan prøves uten kostnad. Resultatene er alltid
merket simulert og sier ingenting om faglig kvalitet.

Scenarier for testing settes i planens motorinnstillinger:
  {"scenarier": {"<dokumentnavn>": "ugyldig_svar" | "feil_side" | "oppdiktet_sitat" | "krasj" | "timeout" | "langsom"},
   "forsinkelse_sek": 0}
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Callable

from ..modell import HELTALL, Inputpakke, Motorsvar, Stotte
from .base import Adapter

TALLORD = {
    "null": 0, "én": 1, "en": 1, "ett": 1, "to": 2, "tre": 3, "fire": 4, "fem": 5, "seks": 6, "sju": 7, "syv": 7,
    "åtte": 8, "ni": 9, "ti": 10, "elleve": 11, "tolv": 12,
}


def _setninger(tekst: str) -> list[str]:
    flat = re.sub(r"\s+", " ", tekst).strip()
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", flat) if s.strip()]


def _finn_setning(sider: list, sokeord: list[str]) -> tuple[int, str, str] | None:
    """Første setning som inneholder et søkeord. Returnerer (fysisk side, setning, treffordet)."""
    for side in sider:
        for setning in _setninger(side.tekst):
            lav = setning.casefold()
            for o in sokeord:
                if o.casefold() in lav:
                    return side.nr, setning, o
    return None


def _er_aarstall(tall: str) -> bool:
    return len(tall) == 4 and tall[:2] in ("18", "19", "20", "21")


def _finn_tall(setning: str, treff: str = "") -> str | None:
    """Tallet (siffer eller tallord) nærmest foran søkeordet; ellers første tall etter. Årstall hoppes over."""
    ord_liste = [(m.start(), m.group(0)) for m in re.finditer(r"[A-Za-zÆØÅæøåé]+|\d+", setning)]

    def verdi(o: str) -> str | None:
        if o.isdigit():
            return None if _er_aarstall(o) else o
        return str(TALLORD[o.casefold()]) if o.casefold() in TALLORD else None

    treffpos = setning.casefold().find(treff.casefold()) if treff else -1
    if treffpos >= 0:
        foran = [verdi(o) for pos, o in ord_liste if pos < treffpos]
        for v in reversed(foran):
            if v is not None:
                return v
    for pos, o in ord_liste:
        if treffpos >= 0 and pos < treffpos:
            continue
        v = verdi(o)
        if v is not None:
            return v
    return None


class SimulertAdapter(Adapter):
    navn = "simulert"
    simulert = True
    beskrivelse = "Simulert motor uten nett- eller modellkall. Bare for testing av flyten."

    def __init__(self, innstillinger: dict[str, Any] | None = None):
        super().__init__(innstillinger)
        self._avbryt = False

    def sjekk_stotte(self) -> Stotte:
        return Stotte(
            ok=True,
            meldinger=["Simulert motor: gjør ingen nett- eller modellkall. Resultater merkes SIMULERT."],
            egenskaper={"filtyper": ["pdf"], "strukturert_svar": True, "nettilgang": False, "verktoy": []},
        )

    def avbryt(self) -> None:
        self._avbryt = True

    def kjor(self, pakke: Inputpakke, modell: str, stopp: Callable[[], bool], arbeidsmappe: str) -> Motorsvar:
        self._avbryt = False
        scenario = (self.innstillinger.get("scenarier") or {}).get(pakke.dokument_navn)
        forsinkelse = float(self.innstillinger.get("forsinkelse_sek") or 0)
        if scenario == "langsom":
            forsinkelse = max(forsinkelse, 30.0)
        # Vent i små steg slik at stopp kan oppdages.
        slutt = time.monotonic() + forsinkelse
        while time.monotonic() < slutt:
            if stopp() or self._avbryt:
                return Motorsvar(raasvar="", svar=None, avbrutt=True, feil="Avbrutt etter stopp fra bruker.",
                                 motorinfo={"simulert": True, "scenario": scenario})
            time.sleep(0.1)
        if scenario == "krasj":
            raise RuntimeError("Simulert motorfeil (scenario «krasj»).")
        if scenario == "timeout":
            return Motorsvar(raasvar="", svar=None, feil="Simulert tidsavbrudd etter 0 sekunder (scenario «timeout»).",
                             motorinfo={"simulert": True, "scenario": scenario})
        if scenario == "ugyldig_svar":
            raa = "Dette er ikke JSON. Simulert ugyldig svar."
            return Motorsvar(raasvar=raa, svar=None, feil="Svaret var ikke gyldig JSON.", modell_rapportert="simulert",
                             motorinfo={"simulert": True, "scenario": scenario})

        svar = self._lag_svar(pakke, scenario)
        raa = json.dumps(svar, ensure_ascii=False, indent=2)
        return Motorsvar(
            raasvar=raa, svar=svar, sesjon_id=f"simulert-{pakke.forsok_id}", modell_rapportert="simulert",
            forbruk={"merknad": "simulert, ingen belastning"}, hendelser=[{"type": "simulert_svar", "scenario": scenario}],
            motorinfo={"simulert": True, "scenario": scenario, "modell_onsket": modell},
        )

    def _lag_svar(self, pakke: Inputpakke, scenario: str | None) -> dict[str, Any]:
        if 'findings' in pakke.svarskjema['properties']:
            findings = []
            for criterion in self.innstillinger.get('kriterier', []):
                match = _finn_setning(pakke.sider, criterion.get('sokeord', []))
                findings.append({'kriterium_id':criterion['id'], 'kommentar':'SIMULATED extraction.',
                    'belegg':[{'side':match[0],'sitat':match[1]}] if match else []})
            return {'findings':findings,'sider_lest':[s.nr for s in pakke.sider],'merknader':[]}
        if 'STAGE: SYNTHESIS.' in pakke.systeminstruks:
            findings = json.loads(pakke.brukermelding)['chunks']
            answers = []
            for criterion in self.innstillinger.get('kriterier', []):
                evidence = [b for c in findings for f in c['findings'] if f['kriterium_id'] == criterion['id'] for b in f['belegg']]
                labels = criterion['tillatte_svar']
                label = next((s for s in labels if s in criterion.get('krever_belegg_ved', [])),labels[0]) if evidence else next((s for s in labels if s not in criterion.get('krever_belegg_ved', [])),labels[0])
                answers.append({'kriterium_id':criterion['id'],'svar':label,'belegg':evidence,'kommentar':'SIMULATED synthesis; no model used.'})
            return {'vurderinger':answers,'sider_lest':[],'merknader':['SIMULATED: no model used.']}
        # Kriteriene ligger ikke i pakken som objekter; vi tolker systeminstruksens kriterielinjer via skjemaets enum
        # og sokeord i innstillingene. For enkelhet leser vi kriteriene fra innstillingene («kriterier») når de er gitt,
        # ellers fra svarskjemaets enum uten sokeord.
        kriterier = self.innstillinger.get("kriterier") or []
        ider = pakke.svarskjema["properties"]["vurderinger"]["items"]["properties"]["kriterium_id"]["enum"]
        vurderinger = []
        for kid in ider:
            krit = next((k for k in kriterier if k.get("id") == kid), {})
            tillatte = krit.get("tillatte_svar", [])
            sokeord = krit.get("sokeord") or []
            krever = krit.get("krever_belegg_ved", [])
            funn = _finn_setning(pakke.sider, sokeord) if sokeord else None
            belegg: list[dict[str, Any]] = []
            if funn:
                side, setning, treff = funn
                if HELTALL in tillatte:
                    tall = _finn_tall(setning, treff)
                    svaret = tall if tall is not None else ("ikke_oppgitt" if "ikke_oppgitt" in tillatte else "uklart")
                else:
                    svaret = next((s for s in tillatte if s in krever), tillatte[0] if tillatte else "ja")
                if svaret in krever or (HELTALL in krever and svaret.isdigit()):
                    belegg = [{"side": side, "sitat": setning}]
            else:
                uten_krav = [s for s in tillatte if s != HELTALL and s not in krever]
                svaret = uten_krav[0] if uten_krav else (tillatte[0] if tillatte else "ikke_omtalt")
            if scenario == "feil_side" and belegg:
                belegg = [{"side": (b["side"] % len(pakke.sider)) + 1, "sitat": b["sitat"]} for b in belegg]
            if scenario == "oppdiktet_sitat" and belegg:
                belegg = [{"side": b["side"], "sitat": "Dette sitatet finnes ikke i dokumentet (simulert)."} for b in belegg]
            vurderinger.append({"kriterium_id": kid, "svar": svaret, "belegg": belegg,
                                "kommentar": "SIMULERT svar fra regelbasert testmotor."})
        return {
            "vurderinger": vurderinger,
            "sider_lest": [s.nr for s in pakke.sider],
            "merknader": ["SIMULERT: ingen modell er brukt."],
        }
