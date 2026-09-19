"""Bygg én delbar Windows-ZIP for Claude Code og Codex, uten maskinspesifikke stier."""
import hashlib
from pathlib import Path
import tomllib
import zipfile
from pakk_plugin import ROOT, pakk, pakkefiler


def main():
    version = tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
    out = ROOT/'dist'/f'v{version}'
    source = out/'systematic-document-analysis'
    pakk(source)
    archive = out/'systematic-document-analysis-windows.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for file in pakkefiler(source):
            z.write(file, Path('systematic-document-analysis')/file.relative_to(source))
    with zipfile.ZipFile(archive) as z:
        if z.testzip():
            raise RuntimeError('ZIP-kontrollen feilet')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (out/'SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n', encoding='ascii')
    print(f'Release {version}: {archive} ({archive.stat().st_size:,} bytes)')


if __name__ == '__main__':
    main()
