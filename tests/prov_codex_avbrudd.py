"""Manuell prøve av stopp og timeout; bruker bare syntetisk input og ChatGPT-innlogging."""
import tempfile
import time
from pathlib import Path
from kildeanalyse.adaptere.codex_cli import CodexCliAdapter
from kildeanalyse.modell import Inputpakke

pakke=Inputpakke('f','k','d','syntetisk','test',[], 'Svar med JSON. Dokumentet er syntetisk.', 'Forklar tallet fem i ti setninger i feltet svar.', {'type':'object','properties':{'svar':{'type':'string'}},'required':['svar']})
with tempfile.TemporaryDirectory(prefix='oe-codex-stopp-') as temp:
    adapter=CodexCliAdapter({'tidsavbrudd_sek':0.5})
    result=adapter.kjor(pakke,'',lambda:False,str(Path(temp)/'timeout'))
    assert result.svar is None and 'Tidsavbrudd' in result.feil and not result.avbrutt
    print('BESTÅTT: tidsavbrudd',flush=True)
    adapter=CodexCliAdapter()
    start=time.monotonic()
    result=adapter.kjor(pakke,'',lambda:time.monotonic()-start>2,str(Path(temp)/'stopp'))
    assert result.svar is None and result.avbrutt
    assert adapter._prosess is None
    print('BESTÅTT: stopp og avsluttet CLI-prosess',flush=True)
