import hashlib
import json
from pathlib import Path
import sys

import pytest

from kildeanalyse import credentials, tjeneste
from kildeanalyse.api_oppsett import local_key
from kildeanalyse.lager import Lager
from kildeanalyse.dokument import importer_dokument
from kildeanalyse.adaptere import lag_adapter


def test_existing_key_file_gains_azure_without_rewriting_or_duplicates(monkeypatch):
    path = credentials.prepare_file()
    original = b'# Keep my comments\r\nOPENAI_API_KEY="existing-test-secret"'
    path.write_bytes(original)
    assert credentials.prepare_file() == path
    updated = path.read_bytes()
    assert updated.startswith(original) and updated.count(b'AZURE_AI_API_KEY=') == 1
    credentials.prepare_file()
    assert path.read_bytes() == updated
    monkeypatch.delenv('AZURE_AI_API_KEY', raising=False)
    path.write_text('AZURE_AI_API_KEY=azure-test-secret\n', encoding='utf-8')
    assert local_key('azure_foundry_api') == 'azure-test-secret'
    monkeypatch.setenv('AZURE_AI_API_KEY', 'environment-test-secret')
    assert local_key('azure_foundry_api') == 'environment-test-secret'
    for engine in ('codex_cli', 'claude_cli'):
        assert 'AZURE_AI_API_KEY' not in lag_adapter(engine)._env()


def test_key_file_creation_preservation_precedence_and_no_environment_copy(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    path = credentials.prepare_file()
    assert not local_key('openai_api')
    path.write_text('OPENAI_API_KEY="private-file-key"\nANTHROPIC_API_KEY=\n',encoding='utf-8')
    credentials.prepare_file()
    assert local_key('openai_api') == 'private-file-key'
    for engine in ('claude_cli','codex_cli'):
        assert 'OPENAI_API_KEY' not in lag_adapter(engine)._env()
    assert 'private-file-key' not in json.dumps(lag_adapter('openai_api').sjekk_stotte().egenskaper)
    monkeypatch.setenv('OPENAI_API_KEY','environment-key')
    assert local_key('openai_api') == 'environment-key'


@pytest.mark.parametrize('line', ['UNKNOWN=private-secret','OPENAI_API_KEY=private-secret\nOPENAI_API_KEY=duplicate', 'private-secret'])
def test_bad_settings_never_echo_values(line):
    path=credentials.prepare_file(); path.write_text(line,encoding='utf-8')
    with pytest.raises(ValueError) as exc:
        credentials.file_values()
    assert 'private-secret' not in str(exc.value)


def test_reader_download_checks_integrity_and_finds_private_binary(tmp_path, monkeypatch):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
    import setup_reader
    from kildeanalyse import cli_paths
    from kildeanalyse.cli_paths import find_cli
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path))
    monkeypatch.delenv('SDA_CODEX_BIN',raising=False)
    monkeypatch.setattr(setup_reader.shutil,'which',lambda name:None)
    monkeypatch.setattr(cli_paths,'windows_path_directories',lambda:[])
    monkeypatch.setattr(cli_paths.Path,'home',lambda:tmp_path/'home')
    payload=b'local fake executable'
    monkeypatch.setattr(setup_reader.urllib.request,'urlretrieve',lambda url,path:Path(path).write_bytes(payload))
    with pytest.raises(RuntimeError,match='checksum'):
        setup_reader.install('codex')
    target=tmp_path/'systematic-document-analysis/readers/codex/codex.exe'
    assert not target.exists()
    monkeypatch.setattr(setup_reader,'CODEX_SHA256',hashlib.sha256(payload).hexdigest())
    assert setup_reader.install('codex') == str(target)
    assert find_cli('codex') == str(target)
    monkeypatch.setattr(setup_reader.urllib.request,'urlretrieve',lambda *args:pytest.fail('Existing CLI should be reused'))
    assert setup_reader.install('codex') == str(target)


def test_source_preview_exports_complete_scope_without_changing_source(tmp_path):
    store=Lager(tmp_path/'store'); project=tjeneste.opprett_prosjekt(store,'Preview')
    path=tmp_path/'source.txt'; path.write_text('First line.\nSecond line.\nThird line.\n',encoding='utf-8')
    original=path.read_bytes()
    doc,_=importer_dokument(store,project['id'],path)
    result=tjeneste.inspect_source(store,doc['id'],[1,2],1,True)
    assert result['truncated'] and len(result['units']) == 1
    markdown=Path(result['markdown_path']).read_text(encoding='utf-8')
    assert all(text in markdown for text in ('First line.','Second line.','Third line.',doc['sha256']))
    assert path.read_bytes() == original
    with pytest.raises(tjeneste.TjenesteFeil):
        tjeneste.inspect_source(store,doc['id'],[999])


def test_gallery_all_formats_import_and_real_ocr_when_available(tmp_path):
    from kildeanalyse import ocr
    root=Path(__file__).resolve().parents[1]/'examples'
    store=Lager(tmp_path/'store'); project=tjeneste.opprett_prosjekt(store,'Gallery')
    seen=set()
    for path in root.glob('*/documents/*'):
        if path.name.endswith('-scan.pdf'):
            if not ocr.executable():
                continue
            doc,_=importer_dokument(store,project['id'],path,ocr_mode='auto',ocr_languages='eng')
            assert 'annual external review' in ' '.join(s['tekst'] for s in doc['sider'])
            assert doc['sider'][0]['extraction']['method'] == 'ocr'
        else:
            doc,_=importer_dokument(store,project['id'],path)
        assert doc['sider'] and all(s['tekst'].strip() for s in doc['sider'])
        assert 'fictional' in (path.parents[1]/'README.md').read_text(encoding='utf-8').lower()
        seen.add(path.suffix)
    assert seen == {'.pdf','.docx','.xlsx','.md','.txt','.csv','.tsv'}
