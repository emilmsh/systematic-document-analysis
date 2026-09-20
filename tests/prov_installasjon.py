"""Installer og oppdater begge verter med midlertidige appkonfigurasjoner. Ingen modeller."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix='sda-installasjon-') as temp:
        base=Path(temp)
        env=dict(os.environ,CODEX_HOME=str(base/'codex-home'),CLAUDE_CONFIG_DIR=str(base/'claude-home'),
                 SDA_MAINTENANCE_DIR=str(base/'maintenance'))
        (base/'codex-home').mkdir()
        (base/'claude-home').mkdir()
        for iteration in range(2):
            print(f'Installasjonsrunde {iteration+1}',flush=True)
            subprocess.run([sys.executable,'-X','utf8',str(ROOT/'bin/installer.py'),'begge','--base-dir',str(base/'plugins')],
                           env=env,check=True,timeout=120)
        # Reproduce the screenshot: same marketplace name, different local path.
        conflict = subprocess.run([sys.executable,'-X','utf8',str(ROOT/'bin/installer.py'),'begge',
                                   '--base-dir',str(base/'replacement'),'--non-interactive'],
                                  env=env,capture_output=True,text=True,encoding='utf-8',timeout=120)
        assert conflict.returncode == 1 and 'Switch to this installation' in conflict.stderr
        assert not (base/'replacement').exists()
        for flags in (['--replace-source'], ['--repair']):
            subprocess.run([sys.executable,'-X','utf8',str(ROOT/'bin/installer.py'),'begge',
                            '--base-dir',str(base/'replacement'),'--non-interactive',*flags],env=env,check=True,timeout=120)
        assert (base/'plugins/codex/systematic-document-analysis/pyproject.toml').exists()
        assert list((base/'replacement/codex/backups').glob('*/systematic-document-analysis/pyproject.toml'))
        codex=json.loads(subprocess.check_output(['codex','plugin','list','--marketplace','systematic-document-analysis-local','--json'],env=env,encoding='utf-8'))
        assert any(p['name']=='systematic-document-analysis' and p['enabled'] for p in codex['installed'])
        claude=json.loads(subprocess.check_output(['claude','plugin','list','--json'],env=env,encoding='utf-8'))
        assert any(p['id']=='systematic-document-analysis@systematic-document-analysis-local' and p['enabled'] for p in claude)
        claude_root=Path(next(p['installPath'] for p in claude if p['id']=='systematic-document-analysis@systematic-document-analysis-local'))
        assert (claude_root/'.sda-install.json').exists(), 'Claude cache must preserve the managed-install record'
        print('BESTÅTT: ny installasjon, gjentakelse, kildekonflikt, eksplisitt kildebytte og reparasjon i begge CLI-er; kun midlertidige profiler.',flush=True)


if __name__=='__main__':
    main()
