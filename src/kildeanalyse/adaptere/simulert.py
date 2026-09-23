"""Simulert motor: ingen nett- eller modellkall.

Lager deterministiske svar ut fra enkle regler over dokumentteksten, slik at hele flyten
(kø, lagring, validering, kontroll, eksport) kan prøves uten kostnad. Resultatene er alltid
merket simulert og sier ingenting om faglig kvalitet.

Scenarier for testing settes i planens motorinnstillinger:
  {"scenarier": {"<dokumentnavn>": "ugyldig_svar" | "invalid_result" | "krasj" | "timeout" | "langsom"},
   "forsinkelse_sek": 0}
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable

from ..modell import Inputpakke, Motorsvar, Stotte
from .base import Adapter

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

    def _lag_svar(self, pakke, scenario):
        return {'result': 42 if scenario == 'invalid_result' else 'SIMULATED: no model performed this task. Source: ' + pakke.dokument_navn,
                'source_units_read': [s.nr for s in pakke.sider],
                'limitations': ['SIMULATED fixture only; no substantive task result.']}
