"""Read-only summaries of persisted reader calls, shared by status and exports.

Historical manifests stay unchanged. Missing telemetry stays unknown; adapter
attempts are not proof of provider execution. Chunk parents are never counted
again as synthesis calls.
"""
from __future__ import annotations

import json
from pathlib import Path


def reported(value):
    if value is None or str(value).casefold().startswith(('ukjent', 'unknown')):
        return None
    return value or None


def call_records(attempt: dict, document_name: str = '') -> list[dict]:
    manifest = json.loads(attempt.get('manifest_json') or '{}')
    info = manifest.get('motorinfo') or {}
    children = info.get('calls')
    # An active/not-yet-dispatched parent has no completed call evidence yet.
    if children is None and not info and not manifest.get('avsluttet'):
        return []
    params = manifest.get('kjoreparametre') or {}
    rows = []
    for index, record in enumerate(children if children is not None else [manifest], 1):
        stage = record.get('stage', 'single')
        subpath = f'calls/{index:04d}-{stage}' if children is not None else ''
        motor = record.get('motorinfo') or {}
        use = (record.get('forbruk') or {}).get('usage') or {}
        root = Path(attempt.get('input_sti') or '.') / subpath
        diagnostic = str(motor.get('stderr') or '').strip()
        warnings = []
        if diagnostic:
            code = 'CLI_MODEL_CACHE' if 'supports_parallel_tool_calls' in diagnostic and 'cache' in diagnostic else 'CLI_STDERR'
            warnings.append({'code': code, 'message': diagnostic[:800], 'truncated': len(diagnostic) > 800})
        model_evidence = motor.get('reported_model_evidence') or {}
        if model_evidence.get('status') == 'ambiguous':
            warnings.append({'code': 'CLI_MODEL_AMBIGUOUS', 'message':
                'Multiple models were reported; no single reader model could be identified. '
                'See reported_model_evidence and the preserved raw reply.', 'truncated': False})
        # Structured fields only; never infer a model/effort from the request.
        rows.append({
            'run_id': attempt.get('kjoring_id'), 'attempt_id': attempt['id'],
            'document_name': document_name, 'call_index': index, 'stage': stage,
            'reader': attempt.get('motor') or manifest.get('motor'),
            'simulated': bool(attempt.get('simulert', manifest.get('simulert', False))),
            'status': ('not_dispatched' if record.get('dispatched') is False else
                       'cancelled' if record.get('avbrutt') else 'failed' if record.get('feil') else
                       record.get('status') or 'reply_received'),
            'session_id': record.get('sesjon_id'), 'request_id': motor.get('request_id'),
            'process_id': motor.get('pid'), 'cli_version': motor.get('cli_versjon'),
            'requested_model': motor.get('modell_onsket') or params.get('modell') or attempt.get('modell_onsket'),
            'reported_model': reported(record.get('modell_rapportert')),
            'requested_effort': motor.get('tenkenivaa_onsket') or params.get('tenkenivaa'),
            'reported_effort': reported(motor.get('tenkenivaa_rapportert')),
            'started_at': record.get('started_at') or (manifest.get('startet') if children is None else None),
            'finished_at': record.get('finished_at') or (manifest.get('avsluttet') if children is None else None),
            'duration_seconds': motor.get('varighet_sek', record.get('duration_seconds')),
            'exit_code': motor.get('returkode'), 'http_status': motor.get('http_status'),
            'input_tokens': use.get('input_tokens', use.get('prompt_tokens')),
            'output_tokens': use.get('output_tokens', use.get('completion_tokens')),
            'cached_input_tokens': use.get('cached_input_tokens', use.get('cache_read_input_tokens',
                (use.get('input_tokens_details') or use.get('prompt_tokens_details') or {}).get('cached_tokens'))),
            'warnings': warnings, 'error': record.get('feil'),
            'artifact_subdirectory': subpath,
            'input_path': str(root / 'input.json'), 'raw_reply_path': str(root / 'raasvar.txt'),
            'manifest_path': str(root / 'manifest.json'),
        })
    return rows


def call_warnings(records: list[dict]) -> list[dict]:
    return [{**{k: row[k] for k in ('run_id', 'attempt_id', 'call_index', 'stage')}, **warning}
            for row in records for warning in row['warnings']]
