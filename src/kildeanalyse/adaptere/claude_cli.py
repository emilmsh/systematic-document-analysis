"""Claude Code CLI som motor: `claude -p` med brukerens eksisterende innlogging.

Hvert forsøk er en ny, isolert sesjon:
  --safe-mode              ingen CLAUDE.md, skills, plugins, hooks, MCP-servere (innlogging beholdes)
  --setting-sources ""     ingen bruker-/prosjekt-/lokale innstillinger
  Filaktiverte planer bruker CLI-ens innebygde verktøy i en fersk arbeidsmappe.
  --strict-mcp-config      ingen MCP-servere utenom eksplisitt oppgitte (ingen oppgis)
  --disable-slash-commands ingen skills
  --no-session-persistence sesjonen lagres ikke
  --system-prompt-file     den fastlagte instruksen (UTF-8-fil, erstatter standardinstruksen)
  --json-schema            strukturert svar
Dokumentet sendes via stdin (UTF-8).
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
from ..reader_files import prepare as prepare_files, check_source
from ..cli_auth import subscription_confirmed, auth_gate, blocked_support, blocked_reply

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


def file_flags():
    """Fresh, neutral session with the CLI's built-in tools available."""
    return [
        '--safe-mode', '--setting-sources', '', '--tools', 'default',
        '--strict-mcp-config', '--disable-slash-commands', '--no-session-persistence',
        '--dangerously-skip-permissions', '--permission-prompts', 'none',
        '--output-format', 'stream-json', '--verbose',
    ]


def result_events(stdout):
    """Accept the legacy JSON result or preserve a complete tool-enabled JSONL stream."""
    try:
        value = json.loads(stdout)
        if isinstance(value, dict):
            return value, []
    except ValueError:
        pass
    events = [json.loads(line) for line in stdout.splitlines() if line.strip()]
    if any(not isinstance(event, dict) for event in events):
        raise ValueError('Invalid CLI event.')
    results = [event for event in events if event.get('type') == 'result']
    if len(results) != 1:
        raise ValueError('Expected exactly one CLI result event.')
    return results[0], events


def cli_failure(result: dict, returncode: int) -> str | None:
    """Keep provider, turn-limit and tool-permission failures distinct in status."""
    denials = result.get('permission_denials') or []
    subtype = result.get('subtype')
    if subtype == 'error_max_turns':
        detail = f' One or more tool calls were denied ({len(denials)}).' if denials else ''
        return f'Claude Code reached its maximum number of tool turns before answering.{detail}'
    if denials:
        names = sorted({str(item.get('tool_name', 'tool')) for item in denials if isinstance(item, dict)})
        return ('Claude Code was denied a tool call by its CLI or managed policy'
                + (f" ({', '.join(names)})" if names else '')
                + '; the response was retained in the raw audit but was not accepted.')
    if result.get('is_error') or returncode != 0:
        message = result.get('result')
        if isinstance(message, str) and message.strip():
            if 'Prompt is too long' in message:
                return 'Claude Code rejected the input as too long. Use a file-enabled plan for this document.'
            return f'Claude Code error: {message[:500]}'
        return f'Claude Code error ({subtype or "unknown"}; exit code {returncode}).'
    return None


def reported_model(result: dict, events: list[dict]) -> tuple[str | None, dict]:
    """Identify the reader from its own messages, not the order of usage keys.

    Usage can include helper models. A single usage entry remains useful for
    legacy JSON output, but neither the requested model nor init configuration
    proves which model answered. Preserve ambiguity instead of guessing.
    """
    def valid(value):
        return isinstance(value, str) and bool(value.strip()) and not value.startswith('<')

    models = []
    for event in events:
        if event.get('type') != 'assistant' or event.get('parent_tool_use_id') is not None:
            continue
        message = event.get('message')
        model = message.get('model') if isinstance(message, dict) else None
        if valid(model) and model not in models:
            models.append(model)
    if models:
        source = 'assistant_messages'
    else:
        usage = result.get('modelUsage')
        models = [model for model in usage if valid(model)] if isinstance(usage, dict) else []
        source = 'modelUsage'
    model = models[0] if len(models) == 1 else None
    return model, {'source': source, 'models': models,
                   'status': 'identified' if model else 'ambiguous' if models else 'unreported'}


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
        from ..cli_paths import find_cli
        return self.innstillinger.get("claude_bin") or find_cli('claude')

    def _env(self) -> dict[str, str]:
        ut = {k: v for k, v in os.environ.items() if k not in FORBUDTE_ENV and not k.upper().endswith('_API_KEY')}
        if self.innstillinger.get("tenkenivaa"):
            for k in ("CLAUDE_CODE_EFFORT_LEVEL", "MAX_THINKING_TOKENS", "CLAUDE_CODE_DISABLE_THINKING",
                      "CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING", "CLAUDE_EFFORT"):
                ut.pop(k, None)
        from ..cli_paths import execution_env
        return execution_env(ut)

    def _kommando(self, args: list[str], tidsavbrudd: float = 30) -> tuple[int, str, str]:
        bin = self._bin()
        if not bin:
            raise AdapterFeil("Fant ikke `claude` på PATH. Installer Claude Code eller sett SDA_CLAUDE_BIN.")
        p = subprocess.run([bin, *args], capture_output=True, timeout=tidsavbrudd, env=self._env(), stdin=subprocess.DEVNULL)
        return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")

    # --- kontrakt -------------------------------------------------------------------

    def sjekk_stotte(self) -> Stotte:
        meldinger: list[str] = []
        ok = True
        self._auth = {}
        try:
            bin = self._bin()
        except OSError:
            return blocked_support('claude')
        if not bin:
            return blocked_support('claude')
        try:
            code, ut, _ = self._kommando(["--version"])
            if code != 0:
                return blocked_support('claude')
            self._cli_versjon = ut.strip() or "ukjent"
        except Exception:  # noqa: BLE001
            return blocked_support('claude')
        try:
            code, ut, feil = self._kommando(["auth", "status"])
            if not subscription_confirmed('claude', code, ut, feil):
                return blocked_support('claude')
            self._auth = json.loads(ut)
        except Exception:  # noqa: BLE001
            return blocked_support('claude')
        meldinger.append(
            "Kvote og eventuell ekstraforbruksordning kan ikke leses fra CLI-en; kostnadstall i svarene er listepris-estimater, "
            "ikke faktisk belastning."
        )
        egenskaper = {
            'auth_gate': auth_gate('claude', True),
            "claude_bin": bin,
            "cli_versjon": self._cli_versjon,
            "innlogging": {k: self._auth.get(k) for k in ("loggedIn", "authMethod", "apiProvider", "subscriptionType", "email", "orgName")},
            "isolasjonsflagg": ['--safe-mode', '--strict-mcp-config', '--no-session-persistence'] if self.innstillinger.get('file_tools') else ISOLASJONSFLAGG,
            "filtyper": ['pdf', 'docx', 'xlsx', 'csv', 'tsv', 'txt', 'md'],
            'file_tools_enabled': bool(self.innstillinger.get('file_tools')),
            "strukturert_svar": True,
            "nettilgang": 'CLI and managed-policy dependent',
            "verktoy": ['default built-in tools'] if self.innstillinger.get('file_tools') else [],
            'file_tools_policy': 'Built-in tools enabled without plugin permission prompts; managed policy still applies. This is not an OS sandbox.',
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
        stotte = self.sjekk_stotte()
        if not stotte.ok:
            return blocked_reply(stotte)
        bin = self._bin()
        if not bin:
            raise AdapterFeil("Fant ikke `claude` på PATH.")
        mappe = Path(arbeidsmappe)
        workspace = prepare_files(pakke, mappe)
        cwd = mappe / "tom_arbeidsmappe"  # tom mappe som cwd: ingen CLAUDE.md, ingen prosjektfiler
        if workspace:
            cwd = Path(workspace['cwd'])
        cwd.mkdir(parents=True, exist_ok=True)
        sysfil = mappe / "systeminstruks.txt"
        sysfil.write_text(pakke.systeminstruks, encoding="utf-8")
        modell = modell or STANDARD_MODELL
        tidsavbrudd = float(self.innstillinger.get("tidsavbrudd_sek") or STANDARD_TIDSAVBRUDD_SEK)
        kommando = [
            bin, "-p", *(file_flags() if workspace else ISOLASJONSFLAGG), "--model", modell,
            "--system-prompt-file", str(sysfil),
            "--json-schema", json.dumps(pakke.svarskjema, ensure_ascii=True),
        ]
        nivaa = self.innstillinger.get("tenkenivaa")
        if nivaa:
            kommando.extend(["--effort", nivaa])
        motorinfo: dict[str, Any] = {
            'auth_gate': auth_gate('claude', True), 'stopp_ko': True,
            "kommando": kommando, "cwd": str(cwd), "cli_versjon": self._cli_versjon, "modell_onsket": modell,
            "innlogging": {k: self._auth.get(k) for k in ("authMethod", "apiProvider", "subscriptionType")},
            "stdin_bytes": len(pakke.brukermelding.encode("utf-8")), "tidsavbrudd_sek": tidsavbrudd,
            "tenkenivaa_onsket": nivaa or "ikke fastsatt (eldre plan)", "tenkenivaa_rapportert": "ukjent",
            'file_workspace': workspace,
        }
        start = time.monotonic()
        proc = subprocess.Popen(
            kommando, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(cwd), env=self._env(),
        )
        self._prosess = proc
        motorinfo['pid'] = proc.pid
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
        source_error = check_source(workspace, pakke.dokument_sha256)
        if source_error:
            return Motorsvar(raasvar=stdout, svar=None, feil=source_error, motorinfo=motorinfo)
        try:
            d, tool_events = result_events(stdout)
        except ValueError:
            return Motorsvar(raasvar=stdout + ("\n--- stderr ---\n" + stderr if stderr.strip() else ""), svar=None,
                             feil=f"CLI-en ga ikke gyldig JSON (returkode {proc.returncode}).", motorinfo=motorinfo)
        modell_rapportert, model_evidence = reported_model(d, tool_events)
        motorinfo['reported_model_evidence'] = model_evidence
        forbruk = {
            "usage": d.get("usage"), "modelUsage": d.get("modelUsage"), "total_cost_usd_listepris": d.get("total_cost_usd"),
            "merknad": "Listepris beregnet av CLI. Faktisk belastning mot abonnementskvoten er ukjent.",
        }
        hendelser = [*tool_events, {
            "type": "cli_resultat", "subtype": d.get("subtype"), "is_error": d.get("is_error"), "num_turns": d.get("num_turns"),
            "duration_ms": d.get("duration_ms"), "permission_denials": d.get("permission_denials"), "stop_reason": d.get("stop_reason"),
        }]
        cli_error = cli_failure(d, proc.returncode)
        if cli_error:
            return Motorsvar(raasvar=stdout, svar=None, sesjon_id=d.get("session_id"), modell_rapportert=modell_rapportert,
                             forbruk=forbruk, hendelser=hendelser, feil=cli_error,
                             motorinfo=motorinfo)
        svar = d.get("structured_output")
        if svar is None and isinstance(d.get("result"), str):
            try:
                svar = json.loads(d["result"])
            except json.JSONDecodeError:
                svar = None
        motorinfo['stopp_ko'] = not isinstance(svar, dict)
        return Motorsvar(
            raasvar=stdout, svar=svar if isinstance(svar, dict) else None, sesjon_id=d.get("session_id"),
            modell_rapportert=modell_rapportert, forbruk=forbruk, hendelser=hendelser,
            feil=None if isinstance(svar, dict) else "Svaret inneholdt ikke et strukturert JSON-objekt.", motorinfo=motorinfo,
        )
