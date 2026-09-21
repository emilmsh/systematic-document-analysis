"""Start fra utviklingsmappe eller plugin-kopi; stdout tilhører MCP.

En kopiert editable-venv må ikke velge kode fra det opprinnelige repoet.
Installert runtime klargjøres på nytt ved endret kilde og etter avbrutt installasjon.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import subprocess
import sys
import shutil
import tempfile


def fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for path in [root / "pyproject.toml", *sorted((root / "src" / "kildeanalyse").rglob("*.py"))]:
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def usable(python: Path, source: Path | None = None) -> bool:
    code = "import kildeanalyse, pypdf, pypdfium2, PIL, docx, openpyxl; import kildeanalyse.mcp_server"
    if source is not None:
        code += "; import pathlib, sys; assert pathlib.Path(kildeanalyse.__file__).resolve().is_relative_to(pathlib.Path(sys.argv[1]).resolve())"
    try:
        return subprocess.run(
            [str(python), "-I", "-c", code, str(source or "")],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def prepare(root: Path, data: Path) -> Path:
    local = root / ".venv" / "Scripts" / "python.exe"
    if usable(local, root / "src"):
        return local
    runtime = data / "venv"
    python = runtime / "Scripts" / "python.exe"
    marker = runtime / "kildeanalyse-source.sha256"
    wanted = fingerprint(root)
    if marker.is_file() and marker.read_text(encoding="ascii") == wanted and usable(python):
        return python
    # Fjern bare ferdigmarkøren. Et avbrudd skal aldri ligne et ferdig oppsett.
    marker.unlink(missing_ok=True)
    print(f"[Systematic Document Analysis] Preparing Python environment in {runtime}", file=sys.stderr, flush=True)
    if not python.is_file():
        subprocess.run([sys.executable, "-X", "utf8", "-m", "venv", str(runtime)], check=True, stdout=sys.stderr)
    # Windows app installations can have very long source paths. Build a fresh,
    # short snapshot; never reuse build/ or egg-info left in a plugin source copy.
    with tempfile.TemporaryDirectory(prefix='sda-build-') as temporary:
        source = Path(temporary)
        shutil.copy2(root/'pyproject.toml', source/'pyproject.toml')
        shutil.copytree(root/'src/kildeanalyse', source/'src/kildeanalyse',
                        ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        subprocess.run(
            [str(python), "-X", "utf8", "-m", "pip", "install", "--disable-pip-version-check", "--quiet", str(source)],
            check=True, stdout=sys.stderr,
        )
    if not usable(python):
        raise RuntimeError("The Python environment could not import the MCP server after installation.")
    marker.write_text(wanted, encoding="ascii")
    return python


def main() -> int:
    if sys.version_info < (3, 12):
        print("[Systematic Document Analysis] Python 3.12 or newer is required.", file=sys.stderr)
        return 1
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root/'src'))
    from kildeanalyse.maintenance import maintenance_lock
    from update_plugin import managed_install, startup, package_hash
    data = Path(os.environ.get("CLAUDE_PLUGIN_DATA") or
                str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "systematic-document-analysis" / "plugin-data"))
    try:
        if startup(root):
            return 1  # New skills/tools must be loaded in a new conversation.
        with maintenance_lock(shared=True):
            marker = managed_install(root)
            if marker:
                root = Path(marker['target'])
                if (root.parent/'pending-install.json').exists():
                    raise RuntimeError(f'An interrupted installation needs recovery. Run installer.cmd {marker["host"]} --recover '
                                       'from the release package.')
                installed_hash = package_hash(root)
                os.environ['SDA_INSTALLED_SHA256'] = installed_hash
                if installed_hash == marker.get('installed_sha256'):
                    os.environ['SDA_PACKAGE_SHA256'] = marker['package_sha256']
                else:
                    os.environ.pop('SDA_PACKAGE_SHA256', None)
            python = prepare(root, data)
            return subprocess.call([str(python), "-I", "-X", "utf8", "-m", "kildeanalyse.mcp_server"])
    except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print(f"[Systematic Document Analysis] Startup failed: {exc}. Resolve the error and restart the plugin.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
