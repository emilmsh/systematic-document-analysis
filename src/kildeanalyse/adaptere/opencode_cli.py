"""OpenCode CLI as reader: `opencode run --standalone` with the provider logins stored in OpenCode.

Each attempt is a new, isolated session:
  --standalone                    private server; not the user's background service or its configuration
  XDG_CONFIG_HOME=<attempt>       no global config, plugins, MCP servers, agents or global AGENTS.md
  OPENCODE_DISABLE_PROJECT_CONFIG no project config or AGENTS.md above the workspace
  PWD=<workspace>                 OpenCode takes its working directory, and so its file boundary, from PWD
  agent `sda-reader`              the agreed instruction as the system prompt, plus the response schema
  permissions                     deny by default; file plans may read, search and edit in the run workspace
                                  and run the bundled helper. Other shell commands, skills, subagents,
                                  questions and web access are denied.
The document or workspace note is sent on stdin (UTF-8). OpenCode keeps sessions in its own database
together with the logins, so the session is exported for the audit and then deleted from its history.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from .base import Adapter, AdapterFeil
from ..modell import Motorsvar, Stotte
from ..reader_files import prepare as prepare_files, check_source
from ..cli_paths import OPENCODE_MIN_VERSION as MIN_VERSION, opencode_bin, version_tuple

AGENT = 'sda-reader'
FILTYPER = ['pdf', 'docx', 'xlsx', 'csv', 'tsv', 'txt', 'md']
# Configuration that would bring the user's own OpenCode setup into the reader session.
FORBUDTE_ENV = ('OPENCODE_CONFIG', 'OPENCODE_CONFIG_DIR', 'OPENCODE_CONFIG_CONTENT', 'OPENCODE_CLI_CONFIG_CONTENT')
SVARFORMAT = ('Response format: your final message must contain only one JSON object that is valid under the '
              'JSON Schema below. Do not add prose, Markdown or code fences.\nJSON Schema:\n')


def data_dir():
    base = os.environ.get('XDG_DATA_HOME') or str(Path.home()/'.local'/'share')
    return Path(base)/'opencode'


def helper_commands(workspace):
    """Shell patterns for the bundled workspace helper only; its paths are fixed to the workspace.

    Each pattern starts with the bundled Python, so it cannot match another command that merely
    mentions the helper. OpenCode checks each part of a compound command separately.
    """
    python, helper = Path(workspace['python']), Path(workspace['helper'])
    prefixes = {workspace['bash_prefix'], workspace['powershell_prefix']}
    quotes = ('', '"', "'")
    for py, script in ((python.as_posix(), helper.as_posix()), (str(python), str(helper))):
        for call in ('', '& '):
            prefixes |= {f'{call}{q}{py}{q} -I {r}{script}{r}' for q in quotes for r in quotes}
    return sorted(prefix + ' *' for prefix in prefixes)


def permissions(workspace, attempt, python):
    """Last matching rule wins. Everything not allowed below is denied, never asked."""
    rules = [{'action': '*', 'resource': '*', 'effect': 'deny'}]
    if not workspace:
        return rules
    rules += [{'action': action, 'resource': '*', 'effect': 'allow'} for action in ('read', 'glob', 'grep', 'edit')]
    # A general shell could read any file the user can; its path scanner misses quoted Windows paths.
    rules += [{'action': 'shell', 'resource': command, 'effect': 'allow'} for command in helper_commands(workspace)]
    # The workspace helper and bundled parsers sit beside the workspace; OpenCode stores long tool output itself.
    for directory in (attempt, python, data_dir()/'tool-output'):
        boundary = Path(directory).resolve().as_posix() + '/*'
        rules.append({'action': 'external_directory', 'resource': boundary, 'effect': 'allow'})
        rules.append({'action': 'edit', 'resource': boundary, 'effect': 'deny'})
    return rules


def reader_config(system, workspace, attempt, python):
    return {
        '$schema': 'https://opencode.ai/config.json',
        'snapshots': False,
        'update': 'disable',
        'default_agent': AGENT,
        'agents': {AGENT: {'description': 'Systematic Document Analysis reader for one assigned file',
                           'mode': 'primary', 'system': system}},
        'permissions': permissions(workspace, attempt, python),
    }


def json_answer(text):
    """The final message as a JSON object: the whole message, or its only fenced JSON block."""
    body = (text or '').strip()
    try:
        value, mode = json.loads(body), 'message'
    except ValueError:
        blocks = re.findall(r'```(?:json)?[ \t]*\r?\n?(.*?)```', body, re.S)
        if len(blocks) != 1:
            raise ValueError('no single JSON object') from None
        value = json.loads(blocks[0])
        mode = 'fenced message' if body.startswith('```') and body.endswith('```') else 'only fenced block in the message'
    if not isinstance(value, dict):
        raise ValueError('not an object')
    return value, mode


def les_hendelser(stdout, returkode, *, file_tools=False):
    """Fail closed: one session, no error events, and a final JSON object as the last message."""
    hendelser, feil, sesjoner, texts = [], [], [], []
    tokens, cost, blocked = {}, 0.0, None
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError('not an object')
        except (ValueError, TypeError):
            feil.append('The OpenCode stream contained invalid JSONL.')
            continue
        hendelser.append(event)
        if event.get('sessionID') and event['sessionID'] not in sesjoner:
            sesjoner.append(event['sessionID'])
        part = event.get('part') if isinstance(event.get('part'), dict) else {}
        typ = event.get('type')
        if typ == 'error':
            error = event.get('error') if isinstance(event.get('error'), dict) else {}
            kind = str(error.get('type') or 'error')
            feil.append(f'OpenCode error ({kind}): {str(error.get("message") or "")[:500]}')
            if kind.startswith('provider.'):
                blocked = kind
        elif typ == 'tool_use' and not file_tools:
            feil.append('Unexpected tool use in an inline reading: ' + str(part.get('tool')))
        elif typ == 'step_finish':
            cost += float(part.get('cost') or 0)
            for key, value in (part.get('tokens') or {}).items():
                if isinstance(value, (int, float)):
                    tokens[key] = tokens.get(key, 0) + value
        elif typ == 'text' and isinstance(part.get('text'), str):
            texts.append((part.get('messageID'), part['text']))
    if returkode != 0:
        feil.append(f'OpenCode exited with code {returkode}.')
    if len(sesjoner) > 1:
        feil.append('The OpenCode stream contained more than one session.')
    svar, mode = None, None
    if texts and not feil:
        last = texts[-1][0]
        try:
            svar, mode = json_answer(''.join(text for message, text in texts if message == last))
        except ValueError:
            feil.append('The final message is not a JSON object or a message with one fenced JSON object.')
    if svar is None and not feil:
        feil.append('OpenCode did not return a final answer.')
    forbruk = {'tokens': tokens, 'cost_usd_estimate': round(cost, 6),
               'merknad': 'Estimate reported by OpenCode. Actual billing depends on the provider login '
                          '(subscription or API key) and is unknown.'}
    result = Motorsvar(raasvar=stdout, svar=None if feil else svar, sesjon_id=sesjoner[0] if len(sesjoner) == 1 else None,
                       hendelser=hendelser, forbruk=forbruk, feil=' '.join(feil) if feil else None,
                       motorinfo={'answer_extraction': mode})
    return result, blocked


def auth_gate(verified, blocked=None):
    return {'status': 'blocked' if blocked else 'verified' if verified else 'not_checked',
            'scope': 'per_run', 'code': 'READER_UNAVAILABLE' if blocked else None,
            'reason': blocked, 'reader': 'opencode_cli', 'automatic_fallback_allowed': False,
            'recovery_command': 'opencode auth login'}


class OpencodeCliAdapter(Adapter):
    navn = 'opencode_cli'
    simulert = False
    beskrivelse = ('OpenCode CLI (opencode run) with the providers signed in to OpenCode. Model as provider/model. '
                   'New isolated session per attempt; the session is removed from OpenCode history afterwards. Real model calls.')

    def __init__(self, innstillinger=None):
        super().__init__(innstillinger)
        self._prosess = None
        self._avbryt = False
        self._versjon = 'ukjent'

    def _bin(self):
        return opencode_bin(self.innstillinger.get('opencode_bin'))

    def _env(self, config_home=None, cwd=None):
        from ..cli_paths import execution_env
        env = {k: v for k, v in os.environ.items() if k not in FORBUDTE_ENV and not k.upper().endswith('_API_KEY')}
        if config_home:
            env.update(XDG_CONFIG_HOME=str(config_home), OPENCODE_DISABLE_PROJECT_CONFIG='1')
        if cwd:
            # OpenCode takes its working directory from PWD when set, not from the process directory.
            env['PWD'] = str(cwd)
        return execution_env(env)

    def sjekk_stotte(self):
        binary = self._bin()
        missing = Stotte(False, ['OpenCode 2 was not found. Install OpenCode (https://opencode.ai), sign in with '
                                 '`opencode auth login`, or set SDA_OPENCODE_BIN.'], {'auth_gate': auth_gate(False)})
        try:
            version = subprocess.run([binary, '--version'], capture_output=True, timeout=20,
                                     stdin=subprocess.DEVNULL, env=self._env())
        except (OSError, subprocess.SubprocessError):
            return missing
        self._versjon = version.stdout.decode('utf-8', 'replace').strip() or 'ukjent'
        found = version_tuple(self._versjon)
        if version.returncode != 0 or not found:
            return missing
        if found < MIN_VERSION:
            return Stotte(False, [f'OpenCode {self._versjon} is too old. Run `opencode upgrade` to use OpenCode 2.'],
                          {'auth_gate': auth_gate(False), 'cli_versjon': self._versjon})
        meldinger = ['The provider login is checked when each run starts: the queue pauses if OpenCode cannot reach the '
                     'selected provider/model. There is no automatic switch to another provider or reader.',
                     'Billing follows the OpenCode provider login (subscription or API key). Cost figures are OpenCode estimates.',
                     'Separate context per file. Full operating-system isolation is not implemented.']
        return Stotte(True, meldinger, {
            'auth_gate': auth_gate(False), 'opencode_bin': binary, 'cli_versjon': self._versjon,
            'filtyper': FILTYPER, 'strukturert_svar': 'instructed JSON object, validated after the run',
            'ny_sesjon_per_forsok': True, 'session_history': 'deleted after each attempt',
            'file_tools_enabled': bool(self.innstillinger.get('file_tools')),
            'file_tools_policy': ('Read, search and edit within the run workspace without prompts; the shell only for the '
                                  'bundled workspace helper (text, render, OCR). Other shell commands, other folders, skills, '
                                  'subagents, questions and web access are denied. This is not an OS sandbox.'),
            'nettilgang': 'denied', 'modell_format': 'provider/model, for example anthropic/claude-sonnet-5',
            'isolasjon': ['--standalone', 'XDG_CONFIG_HOME per attempt', 'OPENCODE_DISABLE_PROJECT_CONFIG=1',
                          'provider API keys removed from the environment'],
        })

    def avbryt(self):
        self._avbryt = True
        self._stopp_prosess()

    def _stopp_prosess(self):
        proc = self._prosess
        if proc is None or proc.poll() is not None:
            return
        if os.name == 'nt':
            # Tool commands run as children of the standalone server.
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)], capture_output=True, timeout=30)
        if proc.poll() is None:
            proc.kill()

    def _session(self, binary, env, sesjon, cwd):
        """Record the reported model, then remove the session with the document from OpenCode's history."""
        info = {'id': sesjon}
        try:
            exported = subprocess.run([binary, 'session', 'export', sesjon, '--standalone'], capture_output=True,
                                      timeout=120, stdin=subprocess.DEVNULL, env=env, cwd=cwd)
            data = json.loads(exported.stdout.decode('utf-8', 'replace'))['info']
            info.update(model=data.get('model'), agent=data.get('agent'), cost=data.get('cost'), tokens=data.get('tokens'))
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as exc:
            info['export_error'] = type(exc).__name__
        try:
            deleted = subprocess.run([binary, 'session', 'delete', sesjon, '--standalone'], capture_output=True,
                                     timeout=120, stdin=subprocess.DEVNULL, env=env, cwd=cwd)
            info['deleted'] = deleted.returncode == 0
            if deleted.returncode:
                info['delete_error'] = deleted.stderr.decode('utf-8', 'replace')[:500]
        except (OSError, subprocess.SubprocessError) as exc:
            info['deleted'] = False
            info['delete_error'] = type(exc).__name__
        return info

    def kjor(self, pakke, modell, stopp, arbeidsmappe):
        self._avbryt = False
        stotte = self.sjekk_stotte()
        if not stotte.ok:
            return Motorsvar('', None, feil='; '.join(stotte.meldinger), motorinfo=stotte.egenskaper)
        if not modell or '/' not in modell:
            raise AdapterFeil('OpenCode needs an explicit model as provider/model.')
        binary = self._bin()
        root = Path(arbeidsmappe).resolve()
        workspace = prepare_files(pakke, root)
        cwd = Path(workspace['cwd']) if workspace else root/'tom_arbeidsmappe'
        cwd.mkdir(parents=True, exist_ok=True)
        system = pakke.systeminstruks + '\n\n' + SVARFORMAT + json.dumps(pakke.svarskjema, ensure_ascii=False)
        config_home = root/'opencode-config'
        (config_home/'opencode').mkdir(parents=True)
        config = reader_config(system, workspace, root, Path(sys.executable).parent)
        (config_home/'opencode'/'opencode.json').write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
        nivaa = self.innstillinger.get('tenkenivaa', 'standard')
        target = modell if nivaa in (None, 'standard') else f'{modell}#{nivaa}'
        args = [binary, 'run', '--standalone', '--format', 'json', '--agent', AGENT, '--model', target]
        env = self._env(config_home, cwd)
        timeout = float(self.innstillinger.get('tidsavbrudd_sek', 600))
        start = time.monotonic()
        proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=str(cwd))
        self._prosess = proc
        avbrutt, tidsavbrudd = False, False
        data = pakke.brukermelding.encode('utf-8')
        try:
            while True:
                if stopp() or self._avbryt:
                    avbrutt = True
                    self._stopp_prosess()
                elif time.monotonic() - start > timeout:
                    tidsavbrudd = True
                    self._stopp_prosess()
                try:
                    out, err = proc.communicate(input=data, timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    data = None
        finally:
            if proc.poll() is None:
                self._stopp_prosess()
                proc.communicate()
            self._prosess = None
        stdout = out.decode('utf-8', 'replace')
        result, blocked = les_hendelser(stdout, proc.returncode, file_tools=bool(workspace))
        session = self._session(binary, env, result.sesjon_id, str(cwd)) if result.sesjon_id else None
        model = (session or {}).get('model') or {}
        if model.get('providerID') and model.get('id'):
            result.modell_rapportert = f"{model['providerID']}/{model['id']}"
        if isinstance((session or {}).get('tokens'), dict):
            # The stream omits usage for single-step answers; the session record has the totals.
            result.forbruk.update(tokens=session['tokens'], cost_usd_estimate=session.get('cost'), source='session export')
        source_error = check_source(workspace, pakke.dokument_sha256)
        if source_error:
            result.svar = None
            result.feil = source_error
        if avbrutt or tidsavbrudd:
            result.svar = None
            result.avbrutt = avbrutt
            result.feil = (('Avbrutt av bruker.' if avbrutt else f'Tidsavbrudd etter {timeout:g} sekunder.')
                           + ' OpenCode-prosessen er avsluttet; leverandørens behandling kan ha fortsatt.')
        result.motorinfo = {
            **result.motorinfo, 'kommando': args, 'cwd': str(cwd), 'cli_versjon': self._versjon, 'pid': proc.pid,
            'modell_onsket': modell, 'tenkenivaa_onsket': nivaa, 'tenkenivaa_rapportert': model.get('variant', 'ukjent'),
            'returkode': proc.returncode, 'varighet_sek': round(time.monotonic() - start, 2),
            'stderr': err.decode('utf-8', 'replace')[:3000], 'systeminstruks_sendt': system,
            'opencode_config': config, 'opencode_session': session, 'file_workspace': workspace,
            'auth_gate': auth_gate(not blocked and result.svar is not None, blocked),
        }
        result.motorinfo['stopp_ko'] = result.svar is None or bool(result.feil) or result.avbrutt
        return result
