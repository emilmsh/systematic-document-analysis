"""Verify a published older ZIP upgrades to the candidate in isolated host profiles.

No models, real user profiles or actual analysis data. Requires existing GitHub access.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'bin'))
from installer import NAME, SELECTOR, validate_package, version, version_key
from update_plugin import REPOSITORY, ARCHIVE, fetch, download, extract_release
from setup_reader import install as reader


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-zip', type=Path, required=True)
    parser.add_argument('--from-tag', default='v0.8.1')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='sda-release-upgrade-') as folder:
        base = Path(folder)
        release = json.loads(fetch(f'https://api.github.com/repos/{REPOSITORY}/releases/tags/{args.from_tag}'))
        info = {'tag':release['tag_name'],'version':release['tag_name'].removeprefix('v'),
                'assets':{a['name']:a['id'] for a in release['assets'] if a['name'] in (ARCHIVE,'SHA256SUMS.txt')}}
        old = download(info, base/'old-release')
        candidate = extract_release(args.release_zip.read_bytes(),base/'candidate')
        expected = validate_package(candidate)
        env = dict(os.environ, CODEX_HOME=str(base/'codex-home'), CLAUDE_CONFIG_DIR=str(base/'claude-home'),
                   SDA_MAINTENANCE_DIR=str(base/'maintenance'), SDA_DATA=str(base/'analysis'),
                   SDA_SETTINGS_DIR=str(base/'settings'))
        for name in ('codex-home','claude-home','analysis','settings'):
            (base/name).mkdir()
        (base/'analysis/keep.txt').write_text('analysis sentinel',encoding='utf-8')
        (base/'settings/keep.txt').write_text('settings sentinel',encoding='utf-8')
        for iteration, source in enumerate((old,candidate,candidate)):
            # This probe tests registration/upgrade; onboarding is tested separately.
            flags = ['--non-interactive']
            if version_key(version(source)) >= (0, 8, 7):
                flags += ['--reader', 'none', '--skip-ocr']
            if iteration == 1 and version(source) == version(old):
                # Also allow testing a not-yet-versioned layout change locally.
                flags += ['--repair']
            entry = source/'bin/manage.py' if (source/'bin/manage.py').exists() else source/'bin/installer.py'
            subprocess.run([sys.executable,'-X','utf8',str(entry),'both',
                            '--base-dir',str(base/'plugins'),*flags],env=env,check=True,timeout=180)
        codex = json.loads(subprocess.check_output([reader('codex'),'plugin','list','--json'],env=env,encoding='utf-8'))
        claude = json.loads(subprocess.check_output([reader('claude'),'plugin','list','--json'],env=env,encoding='utf-8'))
        assert any(p.get('pluginId')==SELECTOR and p['enabled'] and p['version']==expected for p in codex['installed'])
        assert any(p['id']==SELECTOR and p['enabled'] and p['version']==expected for p in claude)
        for host in ('codex','claude'):
            assert version(base/'plugins'/host/NAME) == expected
            assert any(version(p)==info['version'] for p in (base/'plugins'/host/'backups').glob('*/'+NAME))
        assert (base/'analysis/keep.txt').read_text() == 'analysis sentinel'
        assert (base/'settings/keep.txt').read_text() == 'settings sentinel'
        print(f'PASS: published {info["version"]} -> candidate {expected}; both real host CLIs, repeat install, backups and external data/settings preserved.')


if __name__ == '__main__':
    main()
