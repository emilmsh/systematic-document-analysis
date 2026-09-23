"""Local OCR extraction checks; execution policy is tested in test_execution.py."""
import json
from pathlib import Path
import pytest
from kildeanalyse import tjeneste
from kildeanalyse.lager import Lager
from kildeanalyse import ocr
from kildeanalyse.dokument import importer_dokument
from types import SimpleNamespace
QUOTE = 'This document has enough readable text to test extraction.'

def test_ocr_missing_dependency_and_languages(monkeypatch, tmp_path):
    pages = [{'nr':1,'tekst':'','tegn':0}]
    monkeypatch.setattr(ocr,'setup',lambda:{'available':False,'installation':'Install Tesseract.'})
    with pytest.raises(ValueError,match='unavailable'): ocr.apply_pdf(tmp_path/'x.pdf',pages)
    monkeypatch.setattr(ocr,'setup',lambda:{'available':True,'languages':['eng']})
    with pytest.raises(ValueError,match='nor'): ocr.apply_pdf(tmp_path/'x.pdf',pages)
    assert ocr.apply_pdf(tmp_path/'x.pdf',pages,mode='off')[0] == pages


def test_ocr_render_selection_and_immutable_import(tmp_path, monkeypatch):
    import fitz
    path = tmp_path/'mixed.pdf'
    with fitz.open() as pdf:
        pdf.new_page().insert_text((50,50), QUOTE)
        pdf.new_page()
        pdf.save(path)
    original = path.read_bytes()
    monkeypatch.setattr(ocr,'setup',lambda:{'available':True,'executable':'tesseract','version':'local mock','languages':['eng','nor']})
    rendered = []
    def recognition(command, **kwargs):
        assert Path(command[1]).is_file()
        rendered.append(command)
        return SimpleNamespace(stdout=QUOTE)
    monkeypatch.setattr(ocr.subprocess,'run',recognition)
    store = Lager(tmp_path/'data'); pr = tjeneste.opprett_prosjekt(store,'OCR')
    before,_ = importer_dokument(store,pr['id'],path)
    after,_ = importer_dokument(store,pr['id'],path,ocr_mode='auto')
    assert len(rendered) == 1 and after['source_metadata']['ocr']['pages'] == [2]
    assert before['id'] != after['id'] and before['sha256'] == after['sha256']
    assert store.dokument(before['id'])['lesbarhet'] == 'delvis' and after['lesbarhet'] == 'lesbar'
    assert importer_dokument(store,pr['id'],path,ocr_mode='auto')[1] is False
    forced,_ = importer_dokument(store,pr['id'],path,ocr_mode='force')
    assert forced['source_metadata']['ocr']['pages'] == [1,2] and len(rendered) == 3
    assert path.read_bytes() == original
