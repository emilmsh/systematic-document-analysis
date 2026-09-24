"""File-capable readers with fresh per-document context; no model calls."""
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys

import pytest

from kildeanalyse import reader_files
from kildeanalyse.modell import Inputpakke, Side, Stotte
from kildeanalyse.parametre import normaliser
from kildeanalyse.adaptere.claude_cli import ClaudeCliAdapter, cli_failure, result_events
from kildeanalyse.adaptere.codex_cli import CodexCliAdapter, les_hendelser

FIX = Path(__file__).parent/'fixtures/syntetisk/fjordblikk_2025.pdf'


@pytest.fixture
def package():
    return Inputpakke('f', 'k', 'd', FIX.name, hashlib.sha256(FIX.read_bytes()).hexdigest(),
                      [Side(1, 'Assigned text.', 14)], 'instructions', 'source text',
                      {'type': 'object', 'properties': {}}, kjoreparametre={'file_tools': True},
                      local_source_path=str(FIX))


def test_fresh_workspace_contains_only_this_source_and_explicit_inputs(package, tmp_path):
    work = reader_files.prepare(package, tmp_path/'call')
    root = Path(work['cwd'])
    assert set(p.name for p in root.iterdir()) == {
        'source.pdf', 'source-units.json', 'source-index.txt', 'source-chunks', 'SOURCE_GUIDE.md'}
    assert (root/'source.pdf').read_bytes() == FIX.read_bytes()
    assert len(work['initial_files']) == 5
    assert 'Assigned text.' in (root/'source-chunks/units-000001-000001.txt').read_text(encoding='utf-8')
    assert not reader_files.check_source(work, package.dokument_sha256)
    with pytest.raises(FileExistsError):
        reader_files.prepare(package, tmp_path/'call')
    (root/'source.pdf').write_bytes(b'changed')
    assert reader_files.check_source(work, package.dokument_sha256)


def test_synthesis_has_no_original_and_source_identity_is_hashed(package, tmp_path):
    synthesis = replace(package, sider=[])
    work = reader_files.prepare(synthesis, tmp_path/'synthesis')
    assert work['source'] is None
    assert not (Path(work['cwd'])/'source.pdf').exists()
    assert synthesis.hash() != package.hash()
    assert replace(package, dokument_sha256='other source').hash() != package.hash()
    assert 'local_source_path' not in package.til_dict()


def test_large_source_uses_searchable_chunks_with_stable_unit_locations(package, tmp_path):
    units = [Side(i, f'Unique passage {i}: first line\n' + ('word ' * 700), 3500,
                  {'location': f'PDF page {i}'}) for i in range(1, 15)]
    work = reader_files.prepare(replace(package, sider=units), tmp_path/'large')
    root = Path(work['cwd'])
    chunks = work['source_chunks']
    assert len(chunks) > 1
    assert all(item['bytes'] <= reader_files.CHUNK_TARGET_BYTES for item in chunks)
    assert sum((root/item['file']).read_text(encoding='utf-8').count('===== SOURCE UNIT ')
               for item in chunks) == len(units)
    assert 'Unique passage 14:' in (root/chunks[-1]['file']).read_text(encoding='utf-8')
    assert b'first line\nword' in (root/chunks[0]['file']).read_bytes()
    assert b'first line\r\nword' not in (root/chunks[0]['file']).read_bytes()
    assert 'source-chunks/' in (root/'SOURCE_GUIDE.md').read_text(encoding='utf-8')
    guide = (root/'SOURCE_GUIDE.md').read_text(encoding='utf-8')
    assert 'Codex CLI may use its available workspace file and shell tools' in guide
    assert 'Claude Code: use native Glob, Grep and Read' in guide
    assert all(item['file'] in work['initial_files'] for item in chunks)


def test_source_tampering_detected_before_reader_starts(package, tmp_path):
    with pytest.raises(ValueError, match='hash changed'):
        reader_files.prepare(replace(package, dokument_sha256='wrong'), tmp_path)


def test_new_cli_plans_enable_files_old_packages_remain_text_only(package, tmp_path):
    for name in ('claude_cli', 'codex_cli'):
        assert normaliser(name, '')[1]['file_tools'] is True
        assert normaliser(name, '', {'file_tools': False})[1]['file_tools'] is False
        with pytest.raises(ValueError, match='file_tools'):
            normaliser(name, '', {'file_tools': 'yes'})
    assert reader_files.prepare(replace(package, kjoreparametre={}), tmp_path) is None
    assert not list(tmp_path.iterdir())


def test_bundled_parser_and_pdf_renderer_run_with_explicit_python(package, tmp_path):
    work = reader_files.prepare(package, tmp_path/'call with spaces')
    command = [work['python'], '-I', work['helper']]
    options = {'cwd': work['cwd'], 'capture_output': True, 'text': True, 'encoding': 'utf-8', 'timeout': 30}
    parsed = subprocess.run(command + ['text', 'source.pdf'], **options)
    assert parsed.returncode == 0, parsed.stderr
    assert json.loads(parsed.stdout)['result'][0]['unit_id'] == 1
    rendered = subprocess.run(command + ['render', 'source.pdf', '1'], **options)
    assert rendered.returncode == 0, rendered.stderr
    assert (Path(work['cwd'])/'page-1.png').read_bytes().startswith(b'\x89PNG')
    escaped = subprocess.run(command + ['text', '../file-workspace.json'], **options)
    assert escaped.returncode == 1
    audit = (Path(work['cwd'])/'file-operations.jsonl').read_text(encoding='utf-8').splitlines()
    assert len(audit) == 3 and json.loads(audit[-1])['error']


@pytest.mark.parametrize('extension', ['.docx', '.xlsx', '.csv', '.tsv', '.txt', '.md'])
def test_shared_parser_supports_standard_formats(extension):
    path = next((Path(__file__).resolve().parents[1]/'examples').glob(f'*/documents/*{extension}'))
    assert reader_files.text_file(path)['units']


@pytest.mark.parametrize('extension', ['.docx', '.xlsx', '.csv', '.tsv', '.txt', '.md'])
def test_native_reading_chunks_preserve_all_extracted_units(extension, tmp_path):
    from kildeanalyse.source_formats import extract
    path = next((Path(__file__).resolve().parents[1]/'examples').glob(f'*/documents/*{extension}'))
    extracted, _, _ = extract(path)
    units = [Side(row['nr'], row['tekst'], row['tegn'], row['source']) for row in extracted]
    package = Inputpakke('f', 'k', 'd', path.name, hashlib.sha256(path.read_bytes()).hexdigest(),
                         units, 'instructions', 'source text', {'type': 'object', 'properties': {}},
                         kjoreparametre={'file_tools': True}, local_source_path=str(path))
    work = reader_files.prepare(package, tmp_path/extension[1:])
    root = Path(work['cwd'])
    text = ''.join((root/item['file']).read_text(encoding='utf-8') for item in work['source_chunks'])
    assert all(f'===== SOURCE UNIT {unit.nr}: {unit.source["location"]} =====\n{unit.tekst}\n' in text
               for unit in units)


def test_ocr_tool_uses_selected_page_and_workspace_temp(package, tmp_path, monkeypatch, capsys):
    from kildeanalyse import ocr
    work = reader_files.prepare(package, tmp_path/'call')
    def apply(path, pages, **kwargs):
        assert path == Path(work['cwd'])/'source.pdf'
        assert pages[0]['nr'] == 2 and kwargs['temp_dir'] == Path(work['cwd'])
        assert kwargs['languages'] == 'eng+nor' and kwargs['mode'] == 'force'
        return [{'nr': 2, 'tekst': 'OCR text'}], {'pages': [2]}
    monkeypatch.setattr(ocr, 'apply_pdf', apply)
    monkeypatch.setattr(sys, 'argv', ['helper', 'ocr', 'source.pdf', '2'])
    reader_files.main(work['cwd'])
    assert json.loads(capsys.readouterr().out)['result']['pages'][0]['tekst'] == 'OCR text'


def test_real_installed_ocr_through_reader_helper(package, tmp_path):
    from kildeanalyse import ocr
    status = ocr.setup()
    if not status['available'] or not {'eng', 'nor'} <= set(status.get('languages', [])):
        pytest.skip('Real local Tesseract with eng+nor is not installed')
    scan = next((Path(__file__).resolve().parents[1]/'examples').glob('*/documents/*-scan.pdf'))
    package = replace(package, local_source_path=str(scan), dokument_sha256=hashlib.sha256(scan.read_bytes()).hexdigest())
    work = reader_files.prepare(package, tmp_path/'ocr-call')
    result = subprocess.run([work['python'], '-I', work['helper'], 'ocr', 'source.pdf', '1'],
                            cwd=work['cwd'], capture_output=True, text=True, encoding='utf-8', timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    text = json.loads(result.stdout)['result']['pages'][0]['tekst']
    assert 'annual external review' in text.lower()
    assert not reader_files.check_source(work, package.dokument_sha256)


@pytest.mark.parametrize('adapter', [ClaudeCliAdapter, CodexCliAdapter])
def test_cli_file_tools_preserve_context_isolation_and_audit(package, tmp_path, monkeypatch, adapter):
    commands = []
    if adapter is ClaudeCliAdapter:
        events = [{'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'Read', 'input': {'file_path': 'source.pdf'}}]}},
                  {'type': 'result', 'structured_output': {'vurderinger': []}, 'is_error': False}]
    else:
        events = [{'type': 'item.completed', 'item': {'type': 'command_execution', 'command': 'read source.pdf'}},
                  {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': '{"vurderinger": []}'}},
                  {'type': 'turn.completed'}]
    raw = '\n'.join(json.dumps(event) for event in events).encode()
    class Process:
        returncode = 0
        pid = 12345
        def __init__(self, command, **kwargs):
            commands.append((command, kwargs))
            self.stdin, self.stdout, self.stderr = io.BytesIO(), io.BytesIO(raw), io.BytesIO()
        def communicate(self, **kwargs): return raw, b''
        def poll(self): return 0
        def wait(self): return 0
    monkeypatch.setattr(subprocess, 'Popen', Process)
    reader = adapter({'file_tools': True})
    monkeypatch.setattr(reader, '_bin', lambda: 'fake-cli')
    monkeypatch.setattr(reader, 'sjekk_stotte', lambda: Stotte(True))
    result = reader.kjor(package, 'chosen-model', lambda: False, str(tmp_path))
    assert result.svar == {'vurderinger': []}, result.feil
    assert result.hendelser and result.raasvar
    command, options = commands[0]
    assert '--resume' not in command and '--continue' not in command
    if adapter is ClaudeCliAdapter:
        assert all(flag in command for flag in ('--safe-mode', '--restricted', '--strict-mcp-config', '--no-session-persistence'))
        assert command[command.index('--tools')+1] == 'Read,Write,Edit,Glob,Grep,Bash,PowerShell'
        assert 'Bash' not in command[command.index('--allowedTools')+1:command.index('--disallowedTools')]
        assert command[command.index('--max-turns')+1] == '60'
        assert options['cwd'] == str(tmp_path/'workfiles')
    else:
        assert all(flag in command for flag in ('--ignore-user-config', '--ignore-rules', '--ephemeral'))
        assert command[command.index('--sandbox')+1] == 'workspace-write'
        assert 'web_search="disabled"' in command and 'sandbox_workspace_write.network_access=false' in command
        for feature in ('plugins', 'memories', 'apps'):
            assert command[command.index(feature)-1] == '--disable'
        assert command[command.index('view_image')-1] == '--enable'
    assert result.motorinfo['file_workspace']['initial_files']


def test_unexpected_network_events_still_rejected_with_file_tools():
    raw = '\n'.join(json.dumps(event) for event in [
        {'type': 'item.completed', 'item': {'type': 'web_search'}}, {'type': 'turn.completed'}])
    assert les_hendelser(raw, 0, file_tools=True).feil
    with pytest.raises(ValueError):
        result_events('{"type":"assistant"}\n{"type":"system"}')


def test_claude_errors_identify_turn_limit_permission_and_input_size():
    assert 'maximum number of tool turns' in cli_failure(
        {'subtype': 'error_max_turns', 'is_error': True,
         'permission_denials': [{'tool_name': 'PowerShell'}]}, 1)
    assert 'PowerShell' in cli_failure(
        {'subtype': 'success', 'is_error': False,
         'permission_denials': [{'tool_name': 'PowerShell'}], 'structured_output': {'value': 1}}, 0)
    assert 'too long' in cli_failure({'is_error': True, 'result': 'Prompt is too long'}, 1)
    assert '2.1.280' in cli_failure(
        {'is_error': True, 'result': 'Claude Code 2.1.274 does not support this model; version 2.1.280 is required.'}, 1)
    assert cli_failure({'is_error': False, 'permission_denials': []}, 0) is None


def test_exports_preserve_workfiles_and_can_omit_original(package, tmp_path):
    work = reader_files.prepare(package, tmp_path/'call')
    reader_files.copy_artifacts(tmp_path/'call', tmp_path/'export', include_sources=False)
    assert (tmp_path/'export/workfiles/SOURCE_GUIDE.md').is_file()
    assert not (tmp_path/'export/workfiles/source.pdf').exists()
    assert (tmp_path/'export/file-workspace.json').is_file()
