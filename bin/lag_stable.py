"""Point the stable release channel at this release.

The channel is a branch that holds only the release package, so Claude Code and
Codex install exactly what the Windows ZIP contains. Each release adds one commit;
the working tree and the current branch are not touched. Pushing stays manual.
"""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from pakk_plugin import ROOT, pakkefiler
from installer import STABLE_REF, validate_package


def git(root, *args, env=None, stdin=None):
    # Bytes, not text mode: Windows text pipes would turn the index lines' \n into \r\n.
    result = subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, env=env,
                            input=stdin.encode('utf-8') if stdin is not None else None)
    return result.stdout.decode('utf-8').strip()


def current(root, ref):
    result = subprocess.run(['git', '-C', str(root), 'rev-parse', '--verify', '-q', f'{ref}^{{commit}}'],
                            capture_output=True, encoding='utf-8')
    return result.stdout.strip() or None


def build(root=ROOT, *, require_release=True):
    """Commit the package tree onto the stable branch; returns (commit, changed)."""
    root = Path(root)
    version = validate_package(root)
    if require_release:
        if git(root, 'status', '--porcelain', '--untracked-files=no'):
            raise RuntimeError('Commit the release first; the channel must match a tagged commit.')
        if current(root, f'v{version}') != current(root, 'HEAD'):
            raise RuntimeError(f'Tag v{version} must point at HEAD before the channel moves.')
    with tempfile.TemporaryDirectory(prefix='sda-stable-') as temporary:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary)/'index'))
        entries = []
        for path in pakkefiler(root):
            name = path.relative_to(root).as_posix()
            # --path applies the repository's line-ending rules, as a normal commit would.
            blob = git(root, 'hash-object', '-w', '--path', name, str(path))
            entries.append(f'100644 {blob}\t{name}')
        git(root, 'update-index', '--add', '--index-info', env=env, stdin='\n'.join(entries) + '\n')
        tree = git(root, 'write-tree', env=env)
    parent = current(root, f'refs/heads/{STABLE_REF}') or current(root, f'refs/remotes/origin/{STABLE_REF}')
    if parent and git(root, 'rev-parse', f'{parent}^{{tree}}') == tree:
        return parent, False
    commit = git(root, 'commit-tree', tree, *(['-p', parent] if parent else []), '-m', f'Release v{version}')
    git(root, 'update-ref', f'refs/heads/{STABLE_REF}', commit, *([parent] if current(root, f'refs/heads/{STABLE_REF}') else []))
    return commit, True


def main():
    try:
        commit, changed = build()
    except (RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, 'stderr', '') or exc
        print(f'Release channel unchanged: {detail}', file=sys.stderr)
        return 1
    print(f'{STABLE_REF} {"now at" if changed else "already at"} {commit[:12]}. Publish with: git push origin {STABLE_REF}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
