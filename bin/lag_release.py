"""Build a clean Windows ZIP for both hosts; never reuse an old staging tree."""
import hashlib
from pathlib import Path
import tempfile
import zipfile
from pakk_plugin import ROOT, pakk, pakkefiler
from installer import validate_package


def main():
    version = validate_package(ROOT)
    out = ROOT/'dist'/f'v{version}'
    out.mkdir(parents=True, exist_ok=True)
    archive = out/'systematic-document-analysis-windows.zip'
    with tempfile.TemporaryDirectory(prefix='.release-', dir=out) as temporary:
        source = Path(temporary)/'systematic-document-analysis'
        pakk(source)
        validate_package(source)
        staged_zip = Path(temporary)/archive.name
        with zipfile.ZipFile(staged_zip, 'w', zipfile.ZIP_DEFLATED) as z:
            for file in pakkefiler(source):
                z.write(file, Path('systematic-document-analysis')/file.relative_to(source))
        with zipfile.ZipFile(staged_zip) as z:
            if z.testzip():
                raise RuntimeError('ZIP validation failed')
        staged_zip.replace(archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (out/'SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n', encoding='ascii')
    print(f'Release {version}: {archive} ({archive.stat().st_size:,} bytes)')


if __name__ == '__main__':
    main()
