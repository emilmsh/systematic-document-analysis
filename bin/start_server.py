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


def fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for path in [root / "pyproject.toml", *sorted((root / "src" / "kildeanalyse").rglob("*.py"))]:
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def usable(python: Path, source: Path | None = None) -> bool:
    code = "import kildeanalyse, pypdf; from mcp.server.mcpserver import MCPServer"
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
    print(f"[kildeanalyse] Klargjorer Python-miljo i {runtime}", file=sys.stderr, flush=True)
    if not python.is_file():
        subprocess.run([sys.executable, "-X", "utf8", "-m", "venv", str(runtime)], check=True, stdout=sys.stderr)
    subprocess.run(
        [str(python), "-X", "utf8", "-m", "pip", "install", "--disable-pip-version-check", "--quiet", str(root)],
        check=True, stdout=sys.stderr,
    )
    if not usable(python):
        raise RuntimeError("Python-miljoet kunne ikke importere MCP-serveren etter installasjon.")
    marker.write_text(wanted, encoding="ascii")
    return python


def main() -> int:
    if sys.version_info < (3, 12):
        print("[kildeanalyse] Python 3.12 eller nyere kreves.", file=sys.stderr)
        return 1
    root = Path(__file__).resolve().parent.parent
    data = Path(os.environ.get("CLAUDE_PLUGIN_DATA") or
                str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "oe-kildeanalyse" / "plugin-data"))
    try:
        python = prepare(root, data)
        return subprocess.call([str(python), "-I", "-X", "utf8", "-m", "kildeanalyse.mcp_server"])
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"[kildeanalyse] Oppstart feilet: {exc}. Rett feilen og start pluginen pa nytt.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
