"""Installer og oppdater lokale kopier (--local-copy) i begge verter med midlertidige appkonfigurasjoner. Ingen modeller.

Avslutningsvis simuleres en avbrutt installasjon (forrige kopi flyttet til backup,
ufullstendig kopi på plass, plugin avregistrert, journal igjen) som gjenopprettes
med `installer.py --recover` gjennom de ekte verts-CLI-ene.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import uuid

NAME = 'systematic-document-analysis'
SELECTOR = f'{NAME}@{NAME}'

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
            subprocess.run([sys.executable,'-X','utf8',str(ROOT/'bin/installer.py'),'begge','--local-copy','--base-dir',str(base/'plugins'),
                            '--non-interactive','--reader','none','--skip-ocr'],
                           env=env,check=True,timeout=120)
        # Reproduce the screenshot: same marketplace name, different local path.
        conflict = subprocess.run([sys.executable,'-X','utf8',str(ROOT/'bin/installer.py'),'begge','--local-copy',
                                   '--base-dir',str(base/'replacement'),'--non-interactive'],
                                  env=env,capture_output=True,text=True,encoding='utf-8',timeout=120)
        assert conflict.returncode == 1 and 'Switch to this installation' in conflict.stderr
        assert not (base/'replacement').exists()
        for flags in (['--replace-source'], ['--repair']):
            subprocess.run([sys.executable,'-X','utf8',str(ROOT/'bin/installer.py'),'begge','--local-copy',
                            '--base-dir',str(base/'replacement'),'--non-interactive','--reader','none','--skip-ocr',*flags],env=env,check=True,timeout=120)
        assert (base/'plugins/codex/systematic-document-analysis/pyproject.toml').exists()
        assert list((base/'replacement/codex/backups').glob('*/systematic-document-analysis/pyproject.toml'))
        codex=json.loads(subprocess.check_output(['codex','plugin','list','--marketplace','systematic-document-analysis','--json'],env=env,encoding='utf-8'))
        assert any(p['name']=='systematic-document-analysis' and p['enabled'] for p in codex['installed'])
        claude=json.loads(subprocess.check_output(['claude','plugin','list','--json'],env=env,encoding='utf-8'))
        assert any(p['id']==SELECTOR and p['enabled'] for p in claude)
        claude_root=Path(next(p['installPath'] for p in claude if p['id']==SELECTOR))
        assert (claude_root/'.sda-install.json').exists(), 'Claude cache must preserve the managed-install record'
        print('BESTÅTT: ny installasjon, gjentakelse, kildekonflikt, eksplisitt kildebytte og reparasjon i begge CLI-er; kun midlertidige profiler.',flush=True)
        interrupted_install_recovery(base/'replacement', env)


def interrupted_install_recovery(base, env):
    """Forced interruption after the new copy was placed and the plugin was removed."""
    removal = {'codex':['codex','plugin','remove',SELECTOR],
               'claude':['claude','plugin','uninstall',SELECTOR,'--scope','user','--keep-data']}
    for host in ('codex','claude'):
        target = base/host/NAME
        previous = tomllib.loads((target/'pyproject.toml').read_text(encoding='utf-8'))['project']['version']
        backup = target.parent/'backups'/uuid.uuid4().hex/NAME
        backup.parent.mkdir(parents=True)
        target.rename(backup)
        shutil.copytree(backup, target)
        (target/'INCOMPLETE.txt').write_text('interrupted copy', encoding='utf-8')
        subprocess.run(removal[host], env=env, check=True, timeout=120)
        (target.parent/'pending-install.json').write_text(json.dumps({
            'target':str(target), 'backup':str(backup), 'old_source':str(target), 'host':host,
            'previous_version':previous, 'target_existed':True, 'plugin_registered':True,
            'incoming_version':'99.0.0', 'incoming_sha256':'0'*64}), encoding='utf-8')
    blocked = subprocess.run([sys.executable,'-X','utf8',str(ROOT/'bin/installer.py'),'begge','--local-copy',
                              '--base-dir',str(base),'--non-interactive'],
                             env=env,capture_output=True,text=True,encoding='utf-8',timeout=120)
    assert blocked.returncode == 1 and blocked.stderr.count('--recover') == 2, blocked.stderr
    subprocess.run([sys.executable,'-X','utf8',str(ROOT/'bin/installer.py'),'begge','--local-copy',
                    '--base-dir',str(base),'--non-interactive','--recover'],env=env,check=True,timeout=240)
    for host in ('codex','claude'):
        target = base/host/NAME
        assert not (target.parent/'pending-install.json').exists()
        assert not (target/'INCOMPLETE.txt').exists()
        failed = list(target.parent.glob('failed-install-*/INCOMPLETE.txt'))
        assert len(failed) == 1, failed
        receipt = json.loads(next(target.parent.glob('recovery-*.json')).read_text(encoding='utf-8'))
        assert receipt['result'] == 'recovered previous installation'
    codex=json.loads(subprocess.check_output(['codex','plugin','list','--marketplace',NAME,'--json'],env=env,encoding='utf-8'))
    assert any(p['name']==NAME and p['enabled'] for p in codex['installed'])
    claude=json.loads(subprocess.check_output(['claude','plugin','list','--json'],env=env,encoding='utf-8'))
    entry = next(p for p in claude if p['id']==SELECTOR)
    assert entry['enabled'] and (Path(entry['installPath'])/'.sda-install.json').exists()
    assert not (Path(entry['installPath'])/'INCOMPLETE.txt').exists(), 'Claude cache must match the restored copy'
    print('BESTÅTT: avbrutt installasjon blokkerte ny installasjon og ble gjenopprettet med --recover i begge CLI-er; '
          'ufullstendig kopi beholdt som failed-install, kvittering skrevet.',flush=True)


if __name__=='__main__':
    main()
