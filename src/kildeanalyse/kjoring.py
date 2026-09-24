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
from .task_contract import validate as valider
from .maintenance import maintenance_lock, update_pending, draining
from .workflow_guard import plan_problem


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

    def blokkering(self, analyse_id: str) -> dict[str, Any] | None:
        return self.lager.tilstand(f'workflow_block:{analyse_id}')

    def blokker(self, analyse_id: str, code: str, reason: str, run_id: str | None = None) -> dict[str, Any]:
        block = {'status': 'paused', 'code': code, 'reason': reason, 'run_id': run_id,
                 'time': naa(), 'automatic_fallback_allowed': False,
                 'next_action': 'Explain the missing prerequisite, preserve existing work, correct it and recheck. '
                                'Resume only on an explicit user request; plan changes require renewed approval.'}
        self.lager.sett_tilstand(f'workflow_block:{analyse_id}', block)
        self.be_om_stopp(analyse_id)
        self.lager.logg('workflow_paused', analyse_id=analyse_id, **block)
        return block

    def sjekk_forutsetninger(self, analyse_id: str, kjoring_ider: list[str] | None = None, maks: int | None = None):
        planrad = self.lager.gjeldende_planversjon(analyse_id)
        versions = self.lager.planversjoner(analyse_id)
        if planrad is None or planrad['status'] != PLAN_GODKJENT or versions[-1]['id'] != planrad['id']:
            reason = 'Den nyeste planversjonen er ikke godkjent. Godkjenn planen før start.'
            self.blokker(analyse_id, 'PLAN_APPROVAL_REQUIRED', reason)
            raise KoFeil(reason)
        plan = planrad['plan']
        problem = plan_problem(plan)
        if problem:
            self.blokker(analyse_id, 'INVALID_CRITERIA', problem)
            raise KoFeil(problem)
        current_ids = {run['id'] for run in self.lager.kjoringer(analyse_id) if run['planversjon_id'] == planrad['id']}
        if not current_ids:
            reason = 'No source runs have been planned for the approved plan. Select the sources and plan runs before starting.'
            self.blokker(analyse_id, 'NO_RUNS_PLANNED', reason)
            raise KoFeil(reason)
        if (kjoring_ider is not None and (not kjoring_ider or not set(kjoring_ider).issubset(current_ids))) or (
                maks is not None and (type(maks) is not int or maks <= 0)):
            reason = 'Run selection must identify runs of the current plan; maximum must be a positive integer.'
            self.blokker(analyse_id, 'INVALID_RUN_SCOPE', reason)
            raise KoFeil(reason)
        try:
            adapter = lag_adapter(plan.motor, plan.motorinnstillinger)
            stotte = adapter.sjekk_stotte()
        except Exception as exc:
            self.blokker(analyse_id, 'READER_UNAVAILABLE', 'Could not verify the selected reader.')
            raise KoFeil('Could not verify the selected reader; analysis paused.') from exc
        if not stotte.ok:
            reason = f'Motoren «{plan.motor}» kan ikke brukes nå:\n- ' + '\n- '.join(stotte.meldinger)
            code = stotte.egenskaper.get('auth_gate', {}).get('code') or 'READER_UNAVAILABLE'
            self.blokker(analyse_id, code, reason)
            raise KoFeil(reason)
        return planrad, adapter, stotte

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
        with maintenance_lock(shared=True), arbeiderlaas(self.lager.mappe):
            return self._start_laaset(analyse_id, kjoring_ider, maks, inkluder_stoppede)

    def _start_laaset(self, analyse_id: str, kjoring_ider: list[str] | None, maks: int | None,
                      inkluder_stoppede: bool) -> dict[str, Any]:
        self.lager.analyse(analyse_id)
        ryddet = self.rydd_opp(analyse_id)
        arbeider = self.aktiv_arbeider(analyse_id)
        if arbeider:
            raise KoFeil(f"Analysen {analyse_id} har allerede en aktiv arbeider (pid {arbeider.get('pid')}, startet {arbeider.get('tid')}). "
                         "Vent, eller be om stopp.")
        planrad, adapter, stotte = self.sjekk_forutsetninger(analyse_id, kjoring_ider, maks)
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
                                   "startet": [], "utfall": {}, "stoppet_foer": [], "run_issues": []}
        self.lager.sett_tilstand(self._laas(analyse_id), {"pid": os.getpid(), "tid": naa()})
        current_run = None
        try:
            self.lager.slett_tilstand(self._stopp(analyse_id))
            self.lager.slett_tilstand(f'workflow_block:{analyse_id}')
            self.lager.logg("ko_startet", analyse_id=analyse_id, motor=adapter.navn, antall=len(kandidater))
            for i, kj in enumerate(kandidater):
                current_run = kj['id']
                if self.stopp_forespurt(analyse_id) or draining() or update_pending():
                    rapport["stoppet_foer"] = [k["id"] for k in kandidater[i:]]
                    self.lager.logg("ko_stoppet", analyse_id=analyse_id, gjenstaar=rapport["stoppet_foer"])
                    break
                rapport["startet"].append(kj["id"])
                try:
                    outcome = self._kjor_en(kj, planrad, lag_adapter(planrad['plan'].motor, planrad['plan'].motorinnstillinger), stotte.egenskaper)
                except Exception as exc:
                    # A source/preparation/audit-file failure belongs to this run.
                    # If the shared store cannot record it, the outer handler stops dispatch.
                    reason = f'{type(exc).__name__}: {exc}'
                    active = [attempt for attempt in self.lager.aktive_forsok(analyse_id)
                              if attempt['kjoring_id'] == kj['id']]
                    outcome = KJ_UAVKLART if active else KJ_FEILET
                    for attempt in active:
                        self.lager.avslutt_forsok(attempt['id'], status=FS_UAVKLART,
                                                 kjoring_status=KJ_UAVKLART, feil=reason)
                    self.lager.oppdater_kjoring(kj['id'], status=outcome, merknad=reason)
                    self.lager.logg('run_error', analyse_id=analyse_id, kjoring_id=kj['id'], reason=reason)
                rapport["utfall"][kj["id"]] = outcome
                if rapport['utfall'][kj['id']] != KJ_FULLFORT:
                    detail = self.lager.kjoring(kj['id']).get('merknad')
                    attempts = self.lager.forsok_for_kjoring(kj['id'])
                    if attempts:
                        detail = attempts[-1].get('feil') or detail
                        validation = json.loads(attempts[-1].get('validering_json') or '{}')
                        if not detail and validation.get('feil'):
                            detail = '; '.join(error['melding'] for error in validation['feil'][:3])
                    code = {KJ_FEILET: 'READER_FAILED', KJ_VALIDERINGSFEIL: 'VALIDATION_FAILED',
                            KJ_ULESELIG: 'SOURCE_UNREADABLE', KJ_STOPPET: 'RUN_INTERRUPTED',
                            KJ_UAVKLART: 'RUN_UNRESOLVED'}.get(rapport['utfall'][kj['id']], 'RUN_INCOMPLETE')
                    rapport['run_issues'].append({'run_id': kj['id'], 'code': code,
                        'reason': detail or 'The run did not pass the required checks. Inspect show_run.'})
        except Exception as exc:
            reason = 'The routine could not complete its preparation or audit trail. ' + str(exc)
            self.blokker(analyse_id, 'WORKFLOW_ERROR', reason, current_run)
            for attempt in self.lager.aktive_forsok(analyse_id):
                self.lager.avslutt_forsok(attempt['id'], status=FS_UAVKLART,
                                         kjoring_status=KJ_UAVKLART, feil=reason)
            raise
        finally:
            self.lager.slett_tilstand(self._laas(analyse_id))
            self.lager.logg("ko_avsluttet", analyse_id=analyse_id, utfall=rapport["utfall"])
        rapport['workflow_block'] = self.blokkering(analyse_id)
        return rapport

    # --- én kjøring ------------------------------------------------------------------

    def _kjor_en(self, kj: dict[str, Any], planrad: dict[str, Any], adapter: Any, motoregenskaper: dict[str, Any]) -> str:
        plan = planrad["plan"]
        analyse_id = kj["analyse_id"]
        dok = self.lager.dokument(kj["dokument_id"])
        from .dokument import sha256_fil
        if sha256_fil(Path(dok['lagret_kopi'])) != dok['sha256']:
            raise KoFeil('The stored source has changed. Reimport it and approve a new plan before analysis.')
        uten = sider_uten_tekst(dok)
        opaque = dok.get('source_metadata', {}).get('format') == 'opaque'
        can_inspect_without_text = (plan.motor in ('claude_cli', 'codex_cli')
                                    and plan.motorinnstillinger.get('file_tools')
                                    and (plan.tillat_sider_uten_tekst or opaque))
        if (uten and not plan.tillat_sider_uten_tekst and not opaque) or (dok["lesbarhet"] == ULESELIG and not can_inspect_without_text):
            if opaque:
                merknad = (f"File «{dok['navn']}» has no automatically extracted content. No finding was made. "
                           "Use a file-capable CLI reader that can inspect the original.")
            else:
                merknad = (f"Dokumentet «{dok['navn']}» har {len(uten)} av {dok['antall_sider']} sider uten tekstlag "
                           f"(fysisk side {', '.join(map(str, uten))}). Ingen vurdering er gjort, og resultatet er ikke «ikke omtalt». "
                           "Skaff en versjon med tekst (for eksempel OCR) og importer den på nytt, "
                           "eller tillat sider uten tekst i planen for en CLI-leser som kan inspisere originalfilen.")
            self.lager.oppdater_kjoring(kj["id"], status=KJ_ULESELIG, merknad=merknad)
            self.lager.logg("kjoring_stoppet_uleselig", analyse_id=analyse_id, kjoring_id=kj["id"], sider_uten_tekst=uten)
            return KJ_ULESELIG

        nr = len(self.lager.forsok_for_kjoring(kj["id"])) + 1
        forsok_id = f"{kj['id']}.f{nr}"
        pakke = bygg_inputpakke(plan, dok, forsok_id=forsok_id, kjoring_id=kj["id"])
        from .execution import preview, execute
        try:
            input_data = preview(plan, dok, pakke)
        except ValueError as exc:
            self.lager.oppdater_kjoring(kj['id'], status=KJ_FEILET, merknad=str(exc))
            return KJ_FEILET
        mappe = undermappe(f"forsok/{forsok_id}", self.lager.mappe)
        manifest: dict[str, Any] = {
            "app_versjon": VERSJON, "plugin_package_sha256": os.environ.get('SDA_PACKAGE_SHA256'),
            "plugin_installed_sha256": os.environ.get('SDA_INSTALLED_SHA256'),
            "analyse_id": analyse_id, "planversjon_id": planrad["id"], "planversjon": planrad["versjon"],
            "kjoring_id": kj["id"], "forsok_id": forsok_id,
            "dokument": {k: dok[k] for k in ("id", "navn", "sha256", "antall_sider", "lesbarhet", "uttrekk_metode", "lagret_kopi")},
            "sider_sendt": [s.nr for s in pakke.sider], "sider_uten_tekst": uten, "input_hash": input_data['input_hash'],
            'processing':input_data['processing'],
            "motor": adapter.navn, "simulert": adapter.simulert, "modell_onsket": plan.modell, "motoregenskaper": motoregenskaper,
            "kjoreparametre": pakke.kjoreparametre,
            "source_metadata": pakke.source_metadata,
            "startet": naa(), "arbeider_pid": os.getpid(),
        }
        (mappe / "input.json").write_text(json.dumps(input_data, ensure_ascii=False, indent=2), encoding="utf-8")
        (mappe / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        forsok = self.lager.opprett_forsok(
            kj["id"], motor=adapter.navn, simulert=adapter.simulert, modell_onsket=plan.modell, input_hash=input_data['input_hash'],
            input_sti=str(mappe), arbeider_pid=os.getpid(), manifest=manifest,
        )
        if forsok["id"] != forsok_id:  # skal ikke skje med én arbeider; bevar sporbarhet hvis det gjør det
            manifest["forsok_id_avvik"] = forsok["id"]
            forsok_id = forsok["id"]
        self.lager.logg("forsok_startet", analyse_id=analyse_id, kjoring_id=kj["id"], forsok_id=forsok_id, motor=adapter.navn)

        try:
            svar = execute(plan, dok, pakke, adapter, lambda: self.stopp_forespurt(analyse_id), mappe)
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
        elif svar.feil or svar.svar is None:
            status, kj_status = FS_FEILET, KJ_FEILET
        else:
            validering = valider(plan, dok, svar.svar, [s.nr for s in pakke.sider])
            if dok.get('source_metadata', {}).get('ocr', {}).get('pages'):
                validering['advarsler'].append({'type':'ocr', 'melding':'Quotes were checked against OCR text. Verify important evidence against original page images.'})
            if uten:
                message = ('Original file has no automatic extraction; the worker must inspect it with file tools.'
                           if opaque else f"Physical PDF page {', '.join(map(str, uten))} has no extracted text; review the worker's limitations and tool record.")
                validering["advarsler"].append({"type": "source_not_extracted", "melding": message})
            status, kj_status = (FS_FULLFORT, KJ_FULLFORT) if validering["gyldig"] else (FS_VALIDERINGSFEIL, KJ_VALIDERINGSFEIL)
        manifest["status"] = status
        (mappe / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        self.lager.avslutt_forsok(
            forsok_id, status=status, kjoring_status=kj_status, raasvar=svar.raasvar,
            svar_json=svar.svar if status in {FS_FULLFORT, FS_VALIDERINGSFEIL} else None,
            validering_json=validering, feil=svar.feil, forbruk_json=svar.forbruk, sesjon_id=svar.sesjon_id,
            modell_rapportert=svar.modell_rapportert, manifest_json=manifest,
        )
        self.lager.logg("forsok_avsluttet", analyse_id=analyse_id, kjoring_id=kj["id"], forsok_id=forsok_id, status=status, feil=svar.feil)
        # Legacy stopp_ko flags also cover ordinary timeouts, quota and validation
        # failures. Only a verified missing shared prerequisite blocks later runs.
        gate = svar.motorinfo.get('auth_gate', {})
        if gate.get('status') == 'blocked':
            self.blokker(analyse_id, gate.get('code') or 'READER_UNAVAILABLE',
                         svar.feil or 'Reader sign-in could not be verified.', kj['id'])
        return kj_status
