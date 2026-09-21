"""OCR onboarding without installing software or accessing real language folders."""
import hashlib
import io
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'bin'))
import setup_ocr


@pytest.fixture
def ocr_install(tmp_path, monkeypatch):
    state = {'installed': False, 'downloads': [], 'winget': [], 'verify': True}
    root = tmp_path/'private/tessdata'
    def status():
        languages = [lang for lang in ('eng', 'nor') if (root/f'{lang}.traineddata').is_file()]
        return {'available': state['installed'] and state['verify'], 'languages': languages}
    def download(url, **kwargs):
        state['downloads'].append(url)
        return io.BytesIO(b'test language data')
    def install(command, **kwargs):
        state['winget'].append(command)
        state['installed'] = True
    monkeypatch.setattr(setup_ocr.ocr, 'setup', status)
    monkeypatch.setattr(setup_ocr.ocr, 'executable', lambda: 'tesseract.exe' if state['installed'] else None)
    monkeypatch.setattr(setup_ocr.ocr, 'language_directory', lambda: root)
    monkeypatch.setattr(setup_ocr.urllib.request, 'urlopen', download)
    monkeypatch.setattr(setup_ocr.subprocess, 'run', install)
    monkeypatch.setattr(setup_ocr, 'LANGUAGES', {lang: hashlib.sha256(b'test language data').hexdigest() for lang in ('eng', 'nor')})
    monkeypatch.delenv('SDA_TESSERACT_BIN', raising=False)
    return state, root


def test_installs_engine_and_both_languages_then_reuses(ocr_install):
    state, root = ocr_install
    assert setup_ocr.install()['available']
    assert len(state['winget']) == 1 and len(state['downloads']) == 2
    assert (root/'eng.traineddata').is_file() and (root/'nor.traineddata').is_file()
    setup_ocr.install()
    assert len(state['winget']) == 1 and len(state['downloads']) == 2


def test_existing_engine_only_adds_languages_in_user_folder(ocr_install):
    state, root = ocr_install
    state['installed'] = True
    setup_ocr.install()
    assert not state['winget'] and len(state['downloads']) == 2


def test_bad_checksum_does_not_install_language_or_claim_success(ocr_install, monkeypatch):
    state, root = ocr_install
    state['installed'] = True
    monkeypatch.setattr(setup_ocr, 'LANGUAGES', {'eng': 'incorrect', 'nor': 'incorrect'})
    with pytest.raises(RuntimeError, match='checksum'):
        setup_ocr.install()
    assert not list(root.glob('*.traineddata'))


def test_verification_failure_is_reported(ocr_install):
    state, _ = ocr_install
    state['verify'] = False
    with pytest.raises(RuntimeError, match='could not be verified'):
        setup_ocr.install()


def test_invalid_explicit_engine_is_not_silently_replaced(ocr_install, monkeypatch):
    state, _ = ocr_install
    monkeypatch.setenv('SDA_TESSERACT_BIN', 'missing.exe')
    with pytest.raises(RuntimeError, match='override'):
        setup_ocr.install()
    assert not state['winget'] and not state['downloads']
