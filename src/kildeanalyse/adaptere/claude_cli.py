"""Claude Code CLI som motor: `claude -p` med brukerens eksisterende innlogging.

Hvert forsøk er en ny, isolert sesjon:
  --safe-mode              ingen CLAUDE.md, skills, plugins, hooks, MCP-servere (innlogging beholdes)
  --setting-sources ""     ingen bruker-/prosjekt-/lokale innstillinger
  --tools ""               ingen innebygde verktøy (ingen fil-, nett- eller kommandotilgang)
  --strict-mcp-config      ingen MCP-servere utenom eksplisitt oppgitte (ingen oppgis)
  --disable-slash-commands ingen skills
  --no-session-persistence sesjonen lagres ikke
  --system-prompt-file     den fastlagte instruksen (UTF-8-fil, erstatter standardinstruksen)
  --json-schema            strukturert svar
Dokumentet sendes via stdin (UTF-8). Observert oppførsel er dokumentert i tests/TESTLOGG.md.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable

from ..modell import Inputpakke, Motorsvar, Stotte
from .base import Adapter, AdapterFeil

FORBUDTE_ENV = (
    "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_PROFILE",
    "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY",
)
ISOLASJONSFLAGG = [
    "--safe-mode", "--setting-sources", "", "--tools", "", "--strict-mcp-config", "--disable-slash-commands",
    "--no-session-persistence", "--output-format", "json", "--max-turns", "3",
]
STANDARD_MODELL = "sonnet"
STANDARD_TIDSAVBRUDD_SEK = 600


class ClaudeCliAdapter(Adapter):
    navn = "claude_cli"
    simulert = False
    beskrivelse = "Claude Code CLI (claude -p) med eksisterende innlogging. Ny isolert sesjon per forsøk. Ekte modellkall."

    def __init__(self, innstillinger: dict[str, Any] | None = None):
        super().__init__(innstillinger)
        self._prosess: subprocess.Popen | None = None
        self._avbryt = False
        self._auth: dict[str, Any] = {}
        self._cli_versjon: str = "ukjent"

    # --- hjelpere -------------------------------------------------------------------

    def _bin(self) -> str | None:
        return self.innstillinger.get("claude_bin") or os.environ.get("OE_KILDEANALYSE_CLAUDE_BIN") or shutil.which("claude")

    def _env(self) -> dict[str, str]:
        ut = {k: v for k, v in os.environ.items() if k not in FORBUDTE_ENV and not k.upper().endswith('_API_KEY')}
        if self.innstillinger.get("tenkenivaa"):
            for k in ("CLAUDE_CODE_EFFORT_LEVEL", "MAX_THINKING_TOKENS", "CLAUDE_CODE_DISABLE_THINKING",
                      "CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING", "CLAUDE_EFFORT"):
                ut.pop(k, None)
        return ut

    def _kommando(self, args: list[str], tidsavbrudd: float = 30) -> tuple[int, str, str]:
        bin = self._bin()
        if not bin:
            raise AdapterFeil("Fant ikke `claude` på PATH. Installer Claude Code eller sett OE_KILDEANALYSE_CLAUDE_BIN.")
        p = subprocess.run([bin, *args], capture_output=True, timeout=tidsavbrudd, env=self._env(), stdin=subprocess.DEVNULL)
        return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")

    # --- kontrakt -------------------------------------------------------------------

    def sjekk_stotte(self) -> Stotte:
        meldinger: list[str] = []
        ok = True
        bin = self._bin()
        if not bin:
            return Stotte(False, ["Fant ikke `claude` på PATH. Installer Claude Code eller sett OE_KILDEANALYSE_CLAUDE_BIN."])
        try:
            _, ut, _ = self._kommando(["--version"])
            self._cli_versjon = ut.strip() or "ukjent"
        except Exception as e:  # noqa: BLE001
            return Stotte(False, [f"Kunne ikke kjøre `claude --version`: {e}"])
        try:
            _, ut, feil = self._kommando(["auth", "status"])
            self._auth = json.loads(ut) if ut.strip().startswith("{") else {"raatekst": ut.strip(), "stderr": feil.strip()}
        except Exception as e:  # noqa: BLE001
            self._auth = {"feil": str(e)}
        if not self._auth.get("loggedIn"):
            ok = False
            meldinger.append("Claude Code er ikke innlogget i dette miljøet. Kjør `claude` i en terminal og logg inn med Teams-brukeren.")
        else:
            if self._auth.get("authMethod") != "claude.ai":
                ok = False
                meldinger.append(f"Innloggingsmåten er «{self._auth.get('authMethod')}», ikke claude.ai-abonnement. Start blokkeres.")
            if self._auth.get("apiProvider") != "firstParty":
                ok = False
                meldinger.append(f"API-leverandøren er «{self._auth.get('apiProvider')}», ikke firstParty. Start blokkeres.")
        meldinger.append(
            "Kvote og eventuell ekstraforbruksordning kan ikke leses fra CLI-en; kostnadstall i svarene er listepris-estimater, "
            "ikke faktisk belastning."
        )
        egenskaper = {
            "claude_bin": bin,
            "cli_versjon": self._cli_versjon,
            "innlogging": {k: self._auth.get(k) for k in ("loggedIn", "authMethod", "apiProvider", "subscriptionType", "email", "orgName")},
            "isolasjonsflagg": ISOLASJONSFLAGG,
            "filtyper": ["pdf (tekst sendes som ren tekst)"],
            "strukturert_svar": True,
            "nettilgang": False,
            "verktoy": [],
            "ny_sesjon_per_forsok": True,
        }
        return Stotte(ok, meldinger, egenskaper)

    def avbryt(self) -> None:
        self._avbryt = True
        p = self._prosess
        if p is not None and p.poll() is None:
            try:
                p.kill()
            except Exception:  # noqa: BLE001
                pass

    def kjor(self, pakke: Inputpakke, modell: str, stopp: Callable[[], bool], arbeidsmappe: str) -> Motorsvar:
        self._avbryt = False
        bin = self._bin()
        if not bin:
            raise AdapterFeil("Fant ikke `claude` på PATH.")
        mappe = Path(arbeidsmappe)
        cwd = mappe / "tom_arbeidsmappe"  # tom mappe som cwd: ingen CLAUDE.md, ingen prosjektfiler
        cwd.mkdir(parents=True, exist_ok=True)
        sysfil = mappe / "systeminstruks.txt"
        sysfil.write_text(pakke.systeminstruks, encoding="utf-8")
        modell = modell or STANDARD_MODELL
        tidsavbrudd = float(self.innstillinger.get("tidsavbrudd_sek") or STANDARD_TIDSAVBRUDD_SEK)
        kommando = [
            bin, "-p", *ISOLASJONSFLAGG, "--model", modell,
            "--system-prompt-file", str(sysfil),
            "--json-schema", json.dumps(pakke.svarskjema, ensure_ascii=True),
        ]
        nivaa = self.innstillinger.get("tenkenivaa")
        if nivaa:
            kommando.extend(["--effort", nivaa])
        motorinfo: dict[str, Any] = {
            "kommando": kommando, "cwd": str(cwd), "cli_versjon": self._cli_versjon, "modell_onsket": modell,
            "innlogging": {k: self._auth.get(k) for k in ("authMethod", "apiProvider", "subscriptionType")},
            "stdin_bytes": len(pakke.brukermelding.encode("utf-8")), "tidsavbrudd_sek": tidsavbrudd,
            "tenkenivaa_onsket": nivaa or "ikke fastsatt (eldre plan)", "tenkenivaa_rapportert": "ukjent",
        }
        start = time.monotonic()
        proc = subprocess.Popen(
            kommando, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(cwd), env=self._env(),
        )
        self._prosess = proc
        ut: dict[str, bytes] = {"stdout": b"", "stderr": b""}

        def les(navn: str) -> None:
            strom = getattr(proc, navn)
            ut[navn] = strom.read()

        def skriv() -> None:
            try:
                proc.stdin.write(pakke.brukermelding.encode("utf-8"))
                proc.stdin.close()
            except Exception:  # noqa: BLE001
                pass

        traader = [threading.Thread(target=les, args=("stdout",), daemon=True),
                   threading.Thread(target=les, args=("stderr",), daemon=True),
                   threading.Thread(target=skriv, daemon=True)]
        for t in traader:
            t.start()
        avbrutt = False
        feil: str | None = None
        while proc.poll() is None:
            if stopp() or self._avbryt:
                proc.kill()
                avbrutt = True
                break
            if time.monotonic() - start > tidsavbrudd:
                proc.kill()
                feil = f"Tidsavbrudd: ingen svar fra CLI etter {int(tidsavbrudd)} sekunder. Prosessen ble avsluttet."
                break
            time.sleep(0.25)
        proc.wait()
        for t in traader:
            t.join(timeout=5)
        self._prosess = None
        stdout = ut["stdout"].decode("utf-8", "replace")
        stderr = ut["stderr"].decode("utf-8", "replace")
        motorinfo["varighet_sek"] = round(time.monotonic() - start, 1)
        motorinfo["returkode"] = proc.returncode
        if stderr.strip():
            motorinfo["stderr"] = stderr.strip()[:2000]
        if avbrutt:
            return Motorsvar(raasvar=stdout, svar=None, avbrutt=True, feil="Avbrutt etter stopp fra bruker. CLI-prosessen ble avsluttet;"
                             " leverandørens behandling kan ha fortsatt.", motorinfo=motorinfo)
        if feil:
            return Motorsvar(raasvar=stdout, svar=None, feil=feil, motorinfo=motorinfo)
        try:
            d = json.loads(stdout)
        except json.JSONDecodeError:
            return Motorsvar(raasvar=stdout + ("\n--- stderr ---\n" + stderr if stderr.strip() else ""), svar=None,
                             feil=f"CLI-en ga ikke gyldig JSON (returkode {proc.returncode}).", motorinfo=motorinfo)
        modell_rapportert = next(iter((d.get("modelUsage") or {}).keys()), None)
        forbruk = {
            "usage": d.get("usage"), "modelUsage": d.get("modelUsage"), "total_cost_usd_listepris": d.get("total_cost_usd"),
            "merknad": "Listepris beregnet av CLI. Faktisk belastning mot abonnementskvoten er ukjent.",
        }
        hendelser = [{
            "type": "cli_resultat", "subtype": d.get("subtype"), "is_error": d.get("is_error"), "num_turns": d.get("num_turns"),
            "duration_ms": d.get("duration_ms"), "permission_denials": d.get("permission_denials"), "stop_reason": d.get("stop_reason"),
        }]
        if d.get("is_error"):
            return Motorsvar(raasvar=stdout, svar=None, sesjon_id=d.get("session_id"), modell_rapportert=modell_rapportert,
                             forbruk=forbruk, hendelser=hendelser, feil=f"CLI-en rapporterte feil: {str(d.get('result'))[:500]}",
                             motorinfo=motorinfo)
        svar = d.get("structured_output")
        if svar is None and isinstance(d.get("result"), str):
            try:
                svar = json.loads(d["result"])
            except json.JSONDecodeError:
                svar = None
        return Motorsvar(
            raasvar=stdout, svar=svar if isinstance(svar, dict) else None, sesjon_id=d.get("session_id"),
            modell_rapportert=modell_rapportert, forbruk=forbruk, hendelser=hendelser,
            feil=None if isinstance(svar, dict) else "Svaret inneholdt ikke et strukturert JSON-objekt.", motorinfo=motorinfo,
        )
