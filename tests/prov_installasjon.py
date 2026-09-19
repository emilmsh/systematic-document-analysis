"""Installer og oppdater begge verter med midlertidige appkonfigurasjoner. Ingen modeller."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix='oe-installasjon-') as temp:
        base=Path(temp)
        env=dict(os.environ,CODEX_HOME=str(base/'codex-home'),CLAUDE_CONFIG_DIR=str(base/'claude-home'))
        (base/'codex-home').mkdir()
        (base/'claude-home').mkdir()
        for iteration in range(2):
            print(f'Installasjonsrunde {iteration+1}',flush=True)
            subprocess.run([sys.executable,'-X','utf8',str(ROOT/'bin/installer.py'),'begge','--base-dir',str(base/'plugins')],
                           env=env,check=True,timeout=120)
        codex=json.loads(subprocess.check_output(['codex','plugin','list','--marketplace','systematic-document-analysis-local','--json'],env=env,encoding='utf-8'))
        assert any(p['name']=='systematic-document-analysis' and p['enabled'] for p in codex['installed'])
        claude=json.loads(subprocess.check_output(['claude','plugin','list','--json'],env=env,encoding='utf-8'))
        assert any(p['id']=='systematic-document-analysis@systematic-document-analysis-local' and p['enabled'] for p in claude)
        print('BESTÅTT: ny installasjon og gjentatt oppdatering i begge CLI-er, med separate midlertidige appkonfigurasjoner.',flush=True)


if __name__=='__main__':
    main()
