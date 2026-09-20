"""Install local Windows OCR and Norwegian language data. No documents are uploaded."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request


def main():
    roots = [Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'Programs/Tesseract-OCR',
             Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Tesseract-OCR']
    found = shutil.which('tesseract') or os.environ.get('SDA_TESSERACT_BIN')
    if found:
        roots.insert(0, Path(found).parent)
    root = next((p for p in roots if (p/'tesseract.exe').is_file()),None)
    if root is None:
        winget = shutil.which('winget') or str(Path(os.environ['LOCALAPPDATA'])/'Microsoft/WindowsApps/winget.exe')
        subprocess.run([winget,'install','--id','UB-Mannheim.TesseractOCR','--exact','--silent',
            '--accept-package-agreements','--accept-source-agreements','--disable-interactivity'],check=True)
        root = next((p for p in roots if (p/'tesseract.exe').is_file()),None)
    if root is None:
        raise RuntimeError('Tesseract was not found after installation. Set SDA_TESSERACT_BIN and rerun.')
    target = root/'tessdata/nor.traineddata'
    if not target.exists():
        # Pinned upstream language data; verify before writing beside the OCR engine.
        url = 'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/nor.traineddata'
        with urllib.request.urlopen(url,timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != '0451eb4f8049ae78196806bf878a389a2f40f1386fe038568cf4441226ba6ef2':
            raise RuntimeError('Norwegian language data checksum mismatch; nothing written.')
        target.write_bytes(data)
    subprocess.run([str(root/'tesseract.exe'),'--list-langs'],check=True)
    print('Local OCR installed. Restart the host app and use show_setup to check availability.')


if __name__ == '__main__':
    main()
