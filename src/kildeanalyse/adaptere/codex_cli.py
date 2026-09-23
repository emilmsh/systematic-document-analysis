"""Codex CLI med ChatGPT-innlogging. Eksperimentell lokal lesemotor.

Ny sesjon, fast instruks og stdin per forsøk. Flagg begrenser automatisk kontekst;
read-only er ikke en generell lesesperre på operativsystemnivå. Se TESTLOGG.md.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from .base import Adapter, AdapterFeil
from ..modell import Motorsvar, Stotte
from ..cli_auth import subscription_confirmed, auth_gate, blocked_support, blocked_reply
from ..reader_files import prepare as prepare_files, check_source

STANDARD_MODELL = 'gpt-5.6-terra'
FORBUDTE_ENV = ('OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_BASE_URL', 'AZURE_OPENAI_API_KEY', 'CODEX_ACCESS_TOKEN')
DEAKTIVERTE_FUNKSJONER = (
    'shell_tool', 'unified_exec', 'apps', 'plugins', 'hooks', 'memories', 'multi_agent',
    'multi_agent_v2', 'browser_use', 'browser_use_external', 'in_app_browser', 'computer_use',
    'image_generation', 'view_image', 'code_mode', 'code_mode_only', 'skill_search',
    'workspace_dependencies', 'goals', 'tool_suggest', 'shell_snapshot',
)
KONFIG = (
    'project_doc_max_bytes=0', 'skills.include_instructions=false', 'skills.bundled.enabled=false',
    'web_search="disabled"', 'forced_login_method="chatgpt"', 'model_provider="openai"',
    'approval_policy="never"',
)


def strengt_skjema(skjema):
    """Adapt the transport schema; the original contract is validated after the run."""
    s = copy.deepcopy(skjema)
    def besok(node):
        if not isinstance(node, dict):
            return
        # Codex's strict output transport rejects uniqueItems. Keep that
        # constraint in the authoritative schema and check it after generation.
        node.pop('uniqueItems', None)
        if node.get('type') == 'object':
            node['additionalProperties'] = False
            node['required'] = list(node.get('properties', {}))
            for child in node.get('properties', {}).values():
                besok(child)
        if 'items' in node:
            besok(node['items'])
        for branch in node.get('anyOf', []):
            besok(branch)
    besok(s)
    return s


def file_tool_policy_error(stderr: str, *, file_tools: bool) -> str | None:
    """A model answer cannot count as a file read when its shell was blocked."""
    if file_tools and 'blocked by policy' in stderr.casefold() and 'exec_command failed' in stderr.casefold():
        return ('Codex CLI could not read the assigned source: its shell command was blocked by the '
                'execution policy. This attempt was not accepted; inspect the CLI environment or use '
                'an approved reader before retrying.')
    return None


def les_hendelser(stdout, returkode, *, file_tools=False):
    hendelser, meldinger, sesjon, forbruk, feil = [], [], None, {}, []
    fullfort = False
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError('hendelsen er ikke et objekt')
        except (ValueError, TypeError):
            feil.append('CLI-strømmen inneholdt ugyldig JSONL.')
            continue
        hendelser.append(event)
        typ = event.get('type')
        if typ == 'thread.started':
            sesjon = event.get('thread_id')
        elif typ == 'turn.completed':
            fullfort = True
            forbruk = {'usage': event.get('usage'), 'merknad': 'ChatGPT-abonnement. Faktisk kvotebelastning og eventuell ekstrabelastning er ukjent.'}
        elif typ in ('error', 'turn.failed'):
            feil.append(str(event.get('message') or event.get('error') or typ))
        item = event.get('item') or {}
        if item.get('type') == 'error':
            feil.append(str(item.get('message', 'Verktøyfeil')))
        forbidden = ('mcp_tool_call', 'web_search') if file_tools else ('command_execution', 'mcp_tool_call', 'web_search', 'file_change')
        if item.get('type') in forbidden:
            feil.append('Uventet verktøyhendelse i lesekjøring: ' + item['type'])
        if typ == 'item.completed' and item.get('type') == 'agent_message':
            meldinger.append(item.get('text', ''))
    if returkode != 0:
        feil.append(f'Codex avsluttet med returkode {returkode}.')
    if not fullfort:
        feil.append('Ingen bekreftet turn.completed fra Codex.')
    svar = None
    if meldinger and not feil:
        try:
            svar = json.loads(meldinger[-1])
            if not isinstance(svar, dict):
                raise ValueError('Ikke et objekt')
        except ValueError:
            feil.append('Sluttsvaret er ikke et JSON-objekt.')
    if svar is None and not feil:
        feil.append('Codex ga ikke et strukturert sluttsvar.')
    return Motorsvar(raasvar=stdout, svar=svar if not feil else None, sesjon_id=sesjon,
                     hendelser=hendelser, forbruk=forbruk, feil=' '.join(feil) if feil else None)


class CodexCliAdapter(Adapter):
    navn = 'codex_cli'
    simulert = False
    beskrivelse = 'Codex CLI med ChatGPT-abonnement. Eksperimentell lesemotor; ny sesjon per forsøk.'

    def __init__(self, innstillinger=None):
        super().__init__(innstillinger)
        self._prosess = None
        self._avbryt = False
        self._versjon = 'ukjent'

    def _bin(self):
        from ..cli_paths import find_cli
        return self.innstillinger.get('codex_bin') or find_cli('codex')

    def _env(self):
        from ..cli_paths import execution_env
        return execution_env({k: v for k, v in os.environ.items() if k not in FORBUDTE_ENV and not k.upper().endswith('_API_KEY')})

    def sjekk_stotte(self):
        try:
            binary = self._bin()
        except OSError:
            return blocked_support('codex')
        if not binary:
            return blocked_support('codex')
        try:
            version = subprocess.run([binary, '--version'], capture_output=True, timeout=20, stdin=subprocess.DEVNULL, env=self._env())
            self._versjon = version.stdout.decode('utf-8', 'replace').strip()
            if version.returncode != 0:
                return blocked_support('codex')
            auth = subprocess.run([binary, 'login', 'status'], capture_output=True, timeout=20, stdin=subprocess.DEVNULL, env=self._env())
            ok = subscription_confirmed('codex', auth.returncode, auth.stdout.decode('utf-8', 'replace'),
                                        auth.stderr.decode('utf-8', 'replace'))
        except (OSError, subprocess.SubprocessError):
            return blocked_support('codex')
        meldinger = ['Lesekjøringer bruker avgrenset kontekst. Full OS-isolasjon er ikke implementert.',
                     'Kvote og eventuell ekstraforbruksordning er ukjent. Ingen automatisk overgang til API.']
        if not ok:
            return blocked_support('codex')
        return Stotte(ok, meldinger, {'auth_gate': auth_gate('codex', True),
                    'cli_versjon': self._versjon, 'innlogging': {'authMethod': 'chatgpt' if ok else 'ukjent'},
                    'filtyper': ['pdf', 'docx', 'xlsx', 'csv', 'tsv', 'txt', 'md'], 'strukturert_svar': True, 'ny_sesjon_per_forsok': True,
                    'file_tools_enabled': bool(self.innstillinger.get('file_tools')),
                    'kontrollnivaa': 'eksperimentell', 'deaktiverte_funksjoner': [feature for feature in DEAKTIVERTE_FUNKSJONER
                        if not self.innstillinger.get('file_tools') or feature not in ('shell_tool', 'unified_exec', 'view_image')],
                    'konfigurasjon': list(KONFIG), 'modell_standard': STANDARD_MODELL})

    def avbryt(self):
        self._avbryt = True
        if self._prosess is not None and self._prosess.poll() is None:
            self._prosess.kill()

    def kjor(self, pakke, modell, stopp, arbeidsmappe):
        self._avbryt = False
        stotte = self.sjekk_stotte()
        if not stotte.ok:
            return blocked_reply(stotte)
        root = Path(arbeidsmappe).resolve()
        workspace = prepare_files(pakke, root)
        cwd = root / 'tom_arbeidsmappe'
        if workspace:
            cwd = Path(workspace['cwd'])
        cwd.mkdir(parents=True, exist_ok=True)
        instruks = root / 'systeminstruks.txt'
        instruks.write_text(pakke.systeminstruks, encoding='utf-8')
        schema = root / 'codex_svarskjema.json'
        schema.write_text(json.dumps(strengt_skjema(pakke.svarskjema), ensure_ascii=False), encoding='utf-8')
        modell = modell or STANDARD_MODELL
        args = [self._bin(), 'exec', '--ignore-user-config', '--ignore-rules', '--ephemeral', '--skip-git-repo-check',
                '--sandbox', 'workspace-write' if workspace else 'read-only', '--json', '--model', modell, '--output-schema', str(schema), '-C', str(cwd)]
        nivaa = self.innstillinger.get('tenkenivaa', 'low')  # eldre planer beholder low
        for config in (*KONFIG, 'model_reasoning_effort=' + json.dumps(nivaa), 'model_instructions_file=' + json.dumps(str(instruks))):
            args += ['-c', config]
        for feature in DEAKTIVERTE_FUNKSJONER:
            if workspace and feature in ('shell_tool', 'unified_exec', 'view_image'):
                continue
            args += ['--disable', feature]
        if workspace:
            for feature in ('shell_tool', 'unified_exec', 'view_image'):
                args += ['--enable', feature]
            args += ['-c', 'sandbox_workspace_write.network_access=false',
                     '-c', 'sandbox_workspace_write.exclude_slash_tmp=true',
                     '-c', 'sandbox_workspace_write.exclude_tmpdir_env_var=true']
        args.append('-')
        start = time.monotonic()
        timeout = float(self.innstillinger.get('tidsavbrudd_sek', 600))
        proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self._env(), cwd=str(cwd))
        self._prosess = proc
        avbrutt, tidsavbrudd = False, False
        data = pakke.brukermelding.encode('utf-8')
        try:
            while True:
                if stopp() or self._avbryt:
                    avbrutt = True
                    proc.kill()
                elif time.monotonic() - start > timeout:
                    tidsavbrudd = True
                    proc.kill()
                try:
                    out, err = proc.communicate(input=data, timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    data = None
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
            self._prosess = None
        stdout = out.decode('utf-8', 'replace')
        result = les_hendelser(stdout, proc.returncode, file_tools=bool(workspace))
        source_error = check_source(workspace, pakke.dokument_sha256)
        if source_error:
            result.svar = None
            result.feil = source_error
        if avbrutt or tidsavbrudd:
            result.svar = None
            result.avbrutt = avbrutt
            result.feil = ('Avbrutt av bruker.' if avbrutt else f'Tidsavbrudd etter {timeout:g} sekunder.') + ' CLI-prosessen er avsluttet; leverandørens behandling kan ha fortsatt.'
        result.motorinfo = {'kommando': args, 'cwd': str(cwd), 'cli_versjon': self._versjon, 'pid': proc.pid,
                            'modell_onsket': modell, 'tenkenivaa_onsket': nivaa, 'tenkenivaa_rapportert': 'ukjent',
                            'modell_rapportert': 'ukjent (ikke eksponert i JSONL)',
                            'returkode': proc.returncode, 'varighet_sek': round(time.monotonic()-start, 2),
                            'stderr': err.decode('utf-8', 'replace')[:3000],
                            'svarskjema_sendt': strengt_skjema(pakke.svarskjema), 'innlogging': 'chatgpt',
                            'file_workspace': workspace}
        policy_error = file_tool_policy_error(err.decode('utf-8', 'replace'), file_tools=bool(workspace))
        if policy_error:
            result.svar = None
            result.feil = policy_error
        result.motorinfo['auth_gate'] = auth_gate('codex', True)
        # Legacy metadata only; the queue now blocks on confirmed missing auth,
        # while ordinary CLI failures remain individual run issues.
        result.motorinfo['stopp_ko'] = result.svar is None or bool(result.feil) or result.avbrutt
        return result
