"""Prøv installert Codex-plugin med en ekte Codex-vert og simulert lesemotor."""
import json, os, sqlite3, subprocess, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/'tests'/'fixtures'/'syntetisk'
with tempfile.TemporaryDirectory(prefix='sda-codex-vert-') as temp:
    env=dict(os.environ,SDA_DATA=temp)
    args=['codex','exec','--ephemeral','--skip-git-repo-check','--json',
          '-c','plugins."systematic-document-analysis@systematic-document-analysis".enabled=true','-c','model_reasoning_effort="low"',
          '-c','forced_login_method="chatgpt"','-c','skills.bundled.enabled=false',
          '--disable','shell_tool','--disable','browser_use','--disable','memories',
          '--model','gpt-5.6-terra','-C',temp,'-']
    prompt=f'''Dette er en autorisert teknisk integrasjonstest med syntetiske dokumenter. Bruk bare MCP-verktøyene fra systematic-document-analysis-pluginen. Ingen underagenter.
Opprett prosjekt 'Codex vert prøve', importer {FIX / 'fjordblikk_2025.pdf'}, {FIX / 'nordlys_2025.pdf'} og {FIX / 'steinbukk_2025.pdf'}.
Opprett analyse med motor simulert og kriteriefil {FIX / 'eksempelkriterier.json'}. Vis planen, legg til kjøringer og vis én inputpakke. Godkjenn teknisk testplan med ansvarlig 'Automatisk teknisk test' (dette er ikke menneskelig kontroll av svar). Start kjøringene, følg status til ferdig, vis én kjøring og eksporter med kilder. Ikke registrer menneskelig kontroll. Ikke bruk claude_cli eller codex_cli som lesemotor. Returner antall fullførte kjøringer og eksportmappe. Hvis pluginverktøyene mangler, si fra og stopp.'''
    result=subprocess.run(args,input=prompt.encode('utf-8'),stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,timeout=240)
    print('EXIT',result.returncode,flush=True)
    events=[json.loads(line) for line in result.stdout.decode('utf-8','replace').splitlines() if line.strip()]
    completed=[e.get('item',{}) for e in events if e.get('type')=='item.completed']
    print('Pluginverktøy:',[i.get('tool') for i in completed if i.get('server')=='document_analysis'],flush=True)
    print('Sluttsvar:',[i.get('text') for i in completed if i.get('type')=='agent_message'][-1:],flush=True)
    print('stderr er bevart i prosessresultatet; vises ved feil.' if result.returncode==0 else result.stderr.decode('utf-8','replace')[-2500:],flush=True)
    db=Path(temp)/'kildeanalyse.sqlite'
    assert db.is_file(), 'Pluginen opprettet ikke databasen'
    with sqlite3.connect(db) as con:
        rows=con.execute('SELECT status FROM kjoring').fetchall()
        assert rows==[('fullført',)]*3, rows
        assert con.execute('SELECT count(*) FROM kontroll').fetchone()[0]==0
    con.close()
    assert list((Path(temp)/'eksport').glob('*/resultater.csv'))
    print('BESTÅTT: installert Codex-plugin, 3 simulerte kjøringer og eksport via MCP.',flush=True)
