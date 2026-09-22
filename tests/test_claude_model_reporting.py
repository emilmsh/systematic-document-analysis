"""Reader identity must not be inferred from helper-model usage or settings."""
import io
import json
import subprocess

import pytest

from kildeanalyse.adaptere.claude_cli import ClaudeCliAdapter, reported_model, result_events
from kildeanalyse.modell import Inputpakke, Stotte
from kildeanalyse.call_evidence import call_records


def assistant(model, parent=None):
    return {'type': 'assistant', 'parent_tool_use_id': parent, 'message': {'model': model}}


@pytest.mark.parametrize('usage_models', [
    ['claude-haiku-4-5-20251001', 'claude-sonnet-5'],
    ['claude-sonnet-5', 'claude-haiku-4-5-20251001'],
])
def test_reader_messages_override_helper_usage_order(usage_models):
    result = {'modelUsage': {model: {} for model in usage_models}}
    events = [assistant('claude-sonnet-5'), assistant('claude-sonnet-5'),
              assistant('claude-haiku-4-5-20251001', parent='helper-call')]
    model, evidence = reported_model(result, events)
    assert model == 'claude-sonnet-5'
    assert evidence == {'source': 'assistant_messages', 'models': ['claude-sonnet-5'], 'status': 'identified'}


@pytest.mark.parametrize('events', [
    [assistant('sonnet'), assistant('opus')],
    [assistant('opus'), assistant('sonnet')],
])
def test_multiple_reader_models_are_ambiguous_even_with_single_usage_entry(events):
    model, evidence = reported_model({'modelUsage': {'sonnet': {}}}, events)
    assert model is None
    assert evidence['status'] == 'ambiguous'
    assert set(evidence['models']) == {'sonnet', 'opus'}


@pytest.mark.parametrize('usage, expected', [
    ({'claude-sonnet-5': {}}, 'claude-sonnet-5'),
    ({'haiku': {}, 'sonnet': {}}, None),
    ({}, None), (None, None), (['sonnet'], None),
])
def test_legacy_result_requires_unambiguous_usage(usage, expected):
    result, events = result_events(json.dumps({'type': 'result', 'modelUsage': usage}))
    assert reported_model(result, events)[0] == expected


def test_configuration_and_invalid_or_synthetic_messages_do_not_identify_reader():
    events = [{'type': 'system', 'subtype': 'init', 'model': 'requested-model'},
              assistant(None), assistant(''), assistant('  '), assistant('<synthetic>'),
              {'type': 'assistant', 'message': None},
              assistant('helper', parent='child')]
    assert reported_model({}, events) == (None, {
        'source': 'modelUsage', 'models': [], 'status': 'unreported'})


def test_ambiguous_model_is_visible_without_failing_the_call():
    model, evidence = reported_model({'modelUsage': {'haiku': {}, 'sonnet': {}}}, [])
    manifest = {'status': 'fullført', 'modell_rapportert': model,
                'motorinfo': {'reported_model_evidence': evidence}}
    record = call_records({'id': 'f1', 'manifest_json': json.dumps(manifest)})[0]
    assert record['reported_model'] is None
    assert record['status'] == 'fullført'
    assert record['error'] is None
    assert record['warnings'][0]['code'] == 'CLI_MODEL_AMBIGUOUS'


def test_adapter_preserves_raw_usage_and_reports_actual_reader(tmp_path, monkeypatch):
    """Reduced reproduction of kj5/kj6: Haiku usage first, Sonnet reader events."""
    usage = {'claude-haiku-4-5-20251001': {'outputTokens': 13},
             'claude-sonnet-5': {'outputTokens': 1193}}
    payload = {'vurderinger': [], 'sider_lest': []}
    events = [{'type': 'system', 'subtype': 'init', 'model': 'claude-sonnet-5'},
              assistant('claude-sonnet-5'),
              {'type': 'result', 'modelUsage': usage, 'structured_output': payload, 'is_error': False}]
    raw = '\n'.join(json.dumps(event) for event in events)

    class Process:
        returncode = 0
        pid = 12345

        def __init__(self, command, **kwargs):
            assert command[command.index('--model') + 1] == 'sonnet'
            assert command[command.index('--effort') + 1] == 'high'
            self.stdin = io.BytesIO()
            self.stdout = io.BytesIO(raw.encode())
            self.stderr = io.BytesIO()

        def poll(self): return 0
        def wait(self): return 0

    monkeypatch.setattr(subprocess, 'Popen', Process)
    reader = ClaudeCliAdapter({'tenkenivaa': 'high'})
    monkeypatch.setattr(reader, '_bin', lambda: 'fake-cli')
    monkeypatch.setattr(reader, 'sjekk_stotte', lambda: Stotte(True))
    package = Inputpakke('f', 'k', 'd', 'source.txt', 'hash', [], 'instructions', 'source text', {})
    reply = reader.kjor(package, 'sonnet', lambda: False, str(tmp_path))
    assert reply.feil is None
    assert reply.svar == payload
    assert reply.modell_rapportert == 'claude-sonnet-5'
    assert reply.forbruk['modelUsage'] == usage
    assert reply.raasvar == raw
    assert reply.hendelser[:len(events)] == events
    assert reply.motorinfo['reported_model_evidence']['source'] == 'assistant_messages'
    assert reply.motorinfo['tenkenivaa_rapportert'] == 'ukjent'
