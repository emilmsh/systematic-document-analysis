"""Install and verify local Windows OCR, including English and Norwegian."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request


sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from kildeanalyse import ocr

LANGUAGES = {
    'eng': '7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2',
    'nor': '0451eb4f8049ae78196806bf878a389a2f40f1386fe038568cf4441226ba6ef2',
}


def install():
    """Reuse working OCR; install missing pieces without editing PATH or Program Files."""
    status = ocr.setup()
    if status['available'] and set(LANGUAGES) <= set(status.get('languages', [])):
        print('Local OCR verified: Tesseract with English and Norwegian.', flush=True)
        return status
    if not ocr.executable():
        if os.environ.get('SDA_TESSERACT_BIN'):
            raise RuntimeError('SDA_TESSERACT_BIN points to a missing executable. Correct this override and retry.')
        if os.name != 'nt':
            raise RuntimeError('Automatic OCR installation currently supports Windows only.')
        winget = shutil.which('winget') or str(Path(os.environ['LOCALAPPDATA'])/'Microsoft/WindowsApps/winget.exe')
        subprocess.run([winget,'install','--id','UB-Mannheim.TesseractOCR','--exact','--silent',
            '--accept-package-agreements','--accept-source-agreements','--disable-interactivity'],check=True)
    if not ocr.executable():
        raise RuntimeError('Tesseract was not found after installation. Run installer.cmd ocr to retry; keep the installation error.')
    root = ocr.language_directory()
    root.mkdir(parents=True, exist_ok=True)
    for language, expected in LANGUAGES.items():
        target = root/f'{language}.traineddata'
        if target.is_file():
            continue
        url = f'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/{language}.traineddata'
        with urllib.request.urlopen(url,timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError(f'{language} OCR language checksum mismatch; file was not installed.')
        temporary = target.with_suffix('.download')
        temporary.write_bytes(data)
        temporary.replace(target)
    status = ocr.setup()
    if not status['available'] or not set(LANGUAGES) <= set(status.get('languages', [])):
        raise RuntimeError('OCR installation completed but Tesseract with eng+nor could not be verified. Run installer.cmd ocr to retry.')
    print('Local OCR installed and verified: Tesseract with English and Norwegian.', flush=True)
    return status


def main():
    try:
        install()
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f'OCR setup incomplete: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
