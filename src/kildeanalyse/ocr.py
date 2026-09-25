"""Local PDF OCR. Originals and existing extraction versions are never overwritten."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


def executable():
    explicit = os.environ.get('SDA_TESSERACT_BIN')
    if explicit:
        return explicit if Path(explicit).is_file() else None
    from .cli_paths import find_cli
    found = find_cli('tesseract')
    if found != 'tesseract' and Path(found).is_file():
        return found
    candidates = [Path(os.environ.get('ProgramFiles', 'C:/Program Files'))/'Tesseract-OCR/tesseract.exe',
                  Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData/Local'))/'Programs/Tesseract-OCR/tesseract.exe']
    return next((str(p) for p in candidates if p.is_file()), None)


def language_directory():
    """Installer-owned language files live in a user-writable directory."""
    return Path(os.environ.get('LOCALAPPDATA', Path.home()/'AppData/Local'))/'systematic-document-analysis/ocr/tessdata'


def language_arguments():
    root = language_directory()
    return ['--tessdata-dir', str(root)] if all((root/f'{language}.traineddata').is_file() for language in ('eng', 'nor')) else []


def setup():
    exe = executable()
    result = {'available': False, 'engine': 'Tesseract', 'executable': exe,
              'installation': 'Run installer.cmd to install and verify OCR, or installer.cmd ocr to repair OCR only. See docs/DOCUMENT_PROCESSING.md.'}
    if exe:
        try:
            result['version'] = subprocess.check_output([exe, '--version'], timeout=10, encoding='utf-8', errors='replace').splitlines()[0]
            langs = subprocess.check_output([exe, *language_arguments(), '--list-langs'], timeout=10, encoding='utf-8', errors='replace')
            result['languages'] = [s.strip() for s in langs.splitlines() if re.fullmatch(r'[A-Za-z_0-9/]+', s.strip())]
            result['available'] = True
        except (OSError, subprocess.SubprocessError) as exc:
            result['error'] = str(exc)
    return result


def apply_pdf(path, pages, *, mode='auto', languages='eng+nor', temp_dir=None):
    """auto OCRs sparse pages; force OCRs every page (including mixed text/images)."""
    if mode not in ('off', 'auto', 'force'):
        raise ValueError('ocr_mode must be off, auto or force.')
    if not re.fullmatch(r'[a-z_]+(?:\+[a-z_]+)*', languages):
        raise ValueError('ocr_languages must be language codes, for example eng+nor.')
    targets = [p for p in pages if mode == 'force' or (mode == 'auto' and p['tegn'] < 25)]
    info = {'mode': mode, 'languages': languages, 'pages': [], 'warnings': []}
    if not targets:
        return pages, info
    config = setup()
    if not config['available']:
        raise ValueError('OCR required but Tesseract is unavailable. ' + config['installation'] + ' Use ocr_mode=off to import without OCR.')
    missing = set(languages.split('+')) - set(config.get('languages', []))
    if missing:
        raise ValueError('Missing Tesseract language data: ' + ', '.join(sorted(missing)))
    import pypdfium2 as pdfium
    info.update(engine=config['version'], dpi=300)
    # OCR output is a derived transcription, not a verified quotation of page imagery.
    info['warnings'].append('OCR text may contain errors. Verify important quotations against the original page image. Auto mode can miss images on pages with an existing text layer; use force when needed.')
    result = [dict(p) for p in pages]
    by_number = {p['nr']: p for p in result}
    with pdfium.PdfDocument(str(path)) as pdf, tempfile.TemporaryDirectory(prefix='sda-ocr-', dir=temp_dir) as temp:
        for original in targets:
            nr = original['nr']
            page = pdf[nr-1]
            bitmap = None
            try:
                width, height = page.get_size()
                if width * height * (300/72)**2 > 40_000_000:
                    raise ValueError(f'PDF page {nr} is too large to render safely at 300 DPI.')
                bitmap = page.render(scale=300/72)
                image = bitmap.to_pil()
                image_path = Path(temp)/'page.png'
                image.save(image_path)
                image.close()
            finally:
                if bitmap is not None:
                    bitmap.close()
                page.close()
            output = subprocess.run([config['executable'], str(image_path), 'stdout', *language_arguments(), '-l', languages,
                                     '--dpi', '300', '--psm', '3'], capture_output=True, timeout=120,
                                    encoding='utf-8', errors='strict', check=True).stdout
            by_number[nr].update(tekst=output, tegn=len(re.sub(r'\s+', '', output)),
                                extraction={'method':'ocr', 'engine':config['version'], 'languages':languages, 'dpi':300})
            info['pages'].append(nr)
    return result, info
