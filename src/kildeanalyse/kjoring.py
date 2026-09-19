"""Kø og gjennomføring: én aktiv arbeider per analyse, ett forsøk om gangen.

Rekkefølge per kjøring: kontroller lesbarhet → bygg inputpakke → lagre input og forsøks-ID
→ motorkall → bevar råsvar → valider → lagre resultat og status samlet. Stopp sjekkes
mellom kjøringer og underveis i motorkallet. Ved omstart blir forsøk fra en død arbeider
«uavklart», aldri automatisk fullført eller sendt på nytt.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from . import VERSJON
from .adaptere import lag_adapter
from .dokument import ULESELIG, sider_uten_tekst
from .konfig import undermappe
from .lager import (
    FS_AVBRUTT, FS_FEILET, FS_FULLFORT, FS_UAVKLART, FS_VALIDERINGSFEIL, KJ_FEILET, KJ_FULLFORT, KJ_PLANLAGT,
    KJ_STOPPET, KJ_UAVKLART, KJ_ULESELIG, KJ_VALIDERINGSFEIL, PLAN_GODKJENT, Lager, naa,
)
from .modell import Motorsvar
from .prompt import bygg_inputpakke
from .validering import valider


class KoFeil(Exception):
    pass


@contextmanager
def arbeiderlaas(mappe: Path):
    """Én arbeider per datamappe, også ved samtidig start fra flere prosesser.

    OS-låsen frigjøres ved krasj. En sjekk fulgt av sett_tilstand alene er ikke atomisk.
    """
    with (mappe / "arbeider.lock").open("a+b") as fil:
        fil.seek(0, os.SEEK_END)
        if fil.tell() == 0:
            fil.write(b"0")
            fil.flush()
        fil.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fil.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fil.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise KoFeil("Datamappen har allerede en aktiv arbeider. Vent, eller be om stopp.") from exc
        try:
            yield
        finally:
            fil.seek(0)
            if os.name == "nt":
                msvcrt.locking(fil.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fil.fileno(), fcntl.LOCK_UN)


def prosess_lever(pid: int | None) -> bool:
    if not pid:
        return False
    if os.name == "nt":
        import ctypes

        k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        h = k32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            kode = ctypes.c_ulong()
            if not k32.GetExitCodeProcess(h, ctypes.byref(kode)):
                return False
            return kode.value == 259  # STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


class Koer:
    def __init__(self, lager: Lager):
        self.lager = lager

    # --- tilstand ------------------------------------------------------------------

    @staticmethod
    def _laas(analyse_id: str) -> str:
        return f"arbeider:{analyse_id}"

    @staticmethod
    def _stopp(analyse_id: str) -> str:
        return f"stopp:{analyse_id}"

    def aktiv_arbeider(self, analyse_id: str) -> dict[str, Any] | None:
        laas = self.lager.tilstand(self._laas(analyse_id))
        if laas and prosess_lever(laas.get("pid")):
            return laas
        return None

    def stopp_forespurt(self, analyse_id: str) -> bool:
        return self.lager.tilstand(self._stopp(analyse_id)) is not None

    def be_om_stopp(self, analyse_id: str) -> dict[str, Any]:
        self.lager.sett_tilstand(self._stopp(analyse_id), {"tid": naa(), "pid": os.getpid()})
        self.lager.logg("stopp_forespurt", analyse_id=analyse_id)
        return {"analyse_id": analyse_id, "aktiv_arbeider": self.aktiv_arbeider(analyse_id),
                "aktive_forsok": [f["id"] for f in self.lager.aktive_forsok(analyse_id)]}

    def rydd_opp(self, analyse_id: str) -> list[str]:
        """Merker forsøk fra døde arbeidere som uavklart og frigir låsen. Returnerer berørte forsøk."""
        beroerte = []
        for f in self.lager.aktive_forsok(analyse_id):
            if not prosess_lever(f.get("arbeider_pid")):
                self.lager.avslutt_forsok(
                    f["id"], status=FS_UAVKLART, kjoring_status=KJ_UAVKLART,
                    feil="Arbeiderprosessen forsvant mens forsøket var aktivt. Utfallet er ukjent; svaret er ikke lagret. "
                         "Bruk «nytt forsøk» for å prøve igjen.",
                )
                self.lager.logg("forsok_uavklart", analyse_id=analyse_id, kjoring_id=f["kjoring_id"], forsok_id=f["id"])
                beroerte.append(f["id"])
        laas = self.lager.tilstand(self._laas(analyse_id))
        if laas and not prosess_lever(laas.get("pid")):
            self.lager.slett_tilstand(self._laas(analyse_id))
        return beroerte

    # --- start -----------------------------------------------------------------------

    def start(self, analyse_id: str, kjoring_ider: list[str] | None = None, maks: int | None = None,
              inkluder_stoppede: bool = True) -> dict[str, Any]:
        with arbeiderlaas(self.lager.mappe):
            return self._start_laaset(analyse_id, kjoring_ider, maks, inkluder_stoppede)

    def _start_laaset(self, analyse_id: str, kjoring_ider: list[str] | None, maks: int | None,
                      inkluder_stoppede: bool) -> dict[str, Any]:
        self.lager.analyse(analyse_id)
        ryddet = self.rydd_opp(analyse_id)
        arbeider = self.aktiv_arbeider(analyse_id)
        if arbeider:
            raise KoFeil(f"Analysen {analyse_id} har allerede en aktiv arbeider (pid {arbeider.get('pid')}, startet {arbeider.get('tid')}). "
                         "Vent, eller be om stopp.")
        planrad = self.lager.gjeldende_planversjon(analyse_id)
        if planrad is None or planrad["status"] != PLAN_GODKJENT:
            raise KoFeil("Analysen har ingen godkjent planversjon. Godkjenn planen før start.")
        plan = planrad["plan"]
        adapter = lag_adapter(plan.motor, {**plan.motorinnstillinger, "kriterier": [k.til_dict() for k in plan.kriterier]})
        stotte = adapter.sjekk_stotte()
        if not stotte.ok:
            self.lager.logg("start_blokkert", analyse_id=analyse_id, motor=plan.motor, meldinger=stotte.meldinger)
            raise KoFeil(f"Motoren «{plan.motor}» kan ikke brukes nå:\n- " + "\n- ".join(stotte.meldinger))
        self.lager.sett_tilstand(self._laas(analyse_id), {"pid": os.getpid(), "tid": naa()})
        self.lager.slett_tilstand(self._stopp(analyse_id))
        tillatte_status = {KJ_PLANLAGT} | ({KJ_STOPPET} if inkluder_stoppede else set())
        kandidater = [k for k in self.lager.kjoringer(analyse_id)
                      if k["status"] in tillatte_status and k["planversjon_id"] == planrad["id"]
                      and (kjoring_ider is None or k["id"] in kjoring_ider)]
        hoppet_over = [k["id"] for k in self.lager.kjoringer(analyse_id)
                       if k["status"] in tillatte_status and k["planversjon_id"] != planrad["id"]
                       and (kjoring_ider is None or k["id"] in kjoring_ider)]
        if maks is not None:
            kandidater = kandidater[:maks]
        rapport: dict[str, Any] = {"analyse_id": analyse_id, "motor": adapter.navn, "simulert": adapter.simulert,
                                   "ryddet_uavklart": ryddet, "hoppet_over_gammel_planversjon": hoppet_over,
                                   "startet": [], "utfall": {}, "stoppet_foer": []}
        self.lager.logg("ko_startet", analyse_id=analyse_id, motor=adapter.navn, antall=len(kandidater))
        try:
            for i, kj in enumerate(kandidater):
                if self.stopp_forespurt(analyse_id):
                    rapport["stoppet_foer"] = [k["id"] for k in kandidater[i:]]
                    self.lager.logg("ko_stoppet", analyse_id=analyse_id, gjenstaar=rapport["stoppet_foer"])
                    break
                rapport["startet"].append(kj["id"])
                rapport["utfall"][kj["id"]] = self._kjor_en(kj, planrad, adapter, stotte.egenskaper)
        finally:
            self.lager.slett_tilstand(self._laas(analyse_id))
            self.lager.logg("ko_avsluttet", analyse_id=analyse_id, utfall=rapport["utfall"])
        return rapport

    # --- én kjøring ------------------------------------------------------------------

    def _kjor_en(self, kj: dict[str, Any], planrad: dict[str, Any], adapter: Any, motoregenskaper: dict[str, Any]) -> str:
        plan = planrad["plan"]
        analyse_id = kj["analyse_id"]
        dok = self.lager.dokument(kj["dokument_id"])
        uten = sider_uten_tekst(dok)
        if dok["lesbarhet"] == ULESELIG or (uten and not plan.tillat_sider_uten_tekst):
            merknad = (f"Dokumentet «{dok['navn']}» har {len(uten)} av {dok['antall_sider']} sider uten tekstlag "
                       f"(fysisk side {', '.join(map(str, uten))}). Ingen vurdering er gjort, og resultatet er ikke «ikke omtalt». "
                       "Skaff en versjon med tekst (for eksempel OCR) og importer den på nytt, eller tillat sider uten tekst i planen.")
            self.lager.oppdater_kjoring(kj["id"], status=KJ_ULESELIG, merknad=merknad)
            self.lager.logg("kjoring_stoppet_uleselig", analyse_id=analyse_id, kjoring_id=kj["id"], sider_uten_tekst=uten)
            return KJ_ULESELIG

        nr = len(self.lager.forsok_for_kjoring(kj["id"])) + 1
        forsok_id = f"{kj['id']}.f{nr}"
        pakke = bygg_inputpakke(plan, dok, forsok_id=forsok_id, kjoring_id=kj["id"])
        mappe = undermappe(f"forsok/{forsok_id}", self.lager.mappe)
        manifest: dict[str, Any] = {
            "app_versjon": VERSJON, "analyse_id": analyse_id, "planversjon_id": planrad["id"], "planversjon": planrad["versjon"],
            "kjoring_id": kj["id"], "forsok_id": forsok_id,
            "dokument": {k: dok[k] for k in ("id", "navn", "sha256", "antall_sider", "lesbarhet", "uttrekk_metode", "lagret_kopi")},
            "sider_sendt": [s.nr for s in pakke.sider], "sider_uten_tekst": uten, "input_hash": pakke.hash(),
            "motor": adapter.navn, "simulert": adapter.simulert, "modell_onsket": plan.modell, "motoregenskaper": motoregenskaper,
            "kjoreparametre": pakke.kjoreparametre,
            "source_metadata": pakke.source_metadata,
            "startet": naa(), "arbeider_pid": os.getpid(),
        }
        (mappe / "input.json").write_text(json.dumps(pakke.til_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        (mappe / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        forsok = self.lager.opprett_forsok(
            kj["id"], motor=adapter.navn, simulert=adapter.simulert, modell_onsket=plan.modell, input_hash=pakke.hash(),
            input_sti=str(mappe), arbeider_pid=os.getpid(), manifest=manifest,
        )
        if forsok["id"] != forsok_id:  # skal ikke skje med én arbeider; bevar sporbarhet hvis det gjør det
            manifest["forsok_id_avvik"] = forsok["id"]
            forsok_id = forsok["id"]
        self.lager.logg("forsok_startet", analyse_id=analyse_id, kjoring_id=kj["id"], forsok_id=forsok_id, motor=adapter.navn)

        try:
            svar = adapter.kjor(pakke, plan.modell, lambda: self.stopp_forespurt(analyse_id), str(mappe))
        except Exception as e:  # noqa: BLE001
            svar = Motorsvar(raasvar="", svar=None, feil=f"Motorfeil: {type(e).__name__}: {e}")
        (mappe / "raasvar.txt").write_text(svar.raasvar or "", encoding="utf-8")

        manifest.update({
            "avsluttet": naa(), "sesjon_id": svar.sesjon_id, "modell_rapportert": svar.modell_rapportert or "ukjent",
            "forbruk": svar.forbruk or {"merknad": "ukjent"}, "hendelser": svar.hendelser, "motorinfo": svar.motorinfo, "feil": svar.feil,
        })
        validering = None
        if svar.avbrutt:
            status, kj_status = FS_AVBRUTT, KJ_STOPPET
        elif svar.svar is None:
            status, kj_status = FS_FEILET, KJ_FEILET
        else:
            validering = valider(plan, dok, svar.svar, [s.nr for s in pakke.sider])
            if uten:
                validering["advarsler"].append({"type": "sider_uten_tekst",
                                                "melding": f"Fysisk side {', '.join(map(str, uten))} har ikke tekstlag og kunne ikke leses."})
            status, kj_status = (FS_FULLFORT, KJ_FULLFORT) if validering["gyldig"] else (FS_VALIDERINGSFEIL, KJ_VALIDERINGSFEIL)
        manifest["status"] = status
        (mappe / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        self.lager.avslutt_forsok(
            forsok_id, status=status, kjoring_status=kj_status, raasvar=svar.raasvar, svar_json=svar.svar,
            validering_json=validering, feil=svar.feil, forbruk_json=svar.forbruk, sesjon_id=svar.sesjon_id,
            modell_rapportert=svar.modell_rapportert, manifest_json=manifest,
        )
        self.lager.logg("forsok_avsluttet", analyse_id=analyse_id, kjoring_id=kj["id"], forsok_id=forsok_id, status=status, feil=svar.feil)
        if svar.motorinfo.get("stopp_ko"):
            self.be_om_stopp(analyse_id)
        return kj_status
