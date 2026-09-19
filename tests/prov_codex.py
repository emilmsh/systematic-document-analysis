"""Manuell abonnementstest med syntetiske dokumenter. Ingen separat API."""
import json
import tempfile
from pathlib import Path
from kildeanalyse import tjeneste
from kildeanalyse.lager import Lager

ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/'tests'/'fixtures'/'syntetisk'

def main():
    with tempfile.TemporaryDirectory(prefix='oe-codex-e2e-') as temp:
        lager=Lager(Path(temp))
        pr=tjeneste.opprett_prosjekt(lager,'Codex syntetisk prøve')
        files=['fjordblikk','nordlys','steinbukk','granitt']
        tjeneste.importer_dokumenter(lager,pr['id'],[str(FIX/(f+'_2025.pdf')) for f in files])
        an=tjeneste.opprett_analyse(lager,pr['id'],'Codex','EKSEMPEL: vurder de syntetiske rapportene',str(FIX/'eksempelkriterier.json'),motor='codex_cli')
        aid=an['analyse']['id']
        tjeneste.godkjenn_plan(lager,aid,'Teknisk test')
        kj=tjeneste.legg_til_kjoringer(lager,aid)['nye']
        result=tjeneste.start(lager,aid)
        print(json.dumps(result,ensure_ascii=False),flush=True)
        forventet=[['ja','5','ja'],['ja','uklart','ja'],['ikke_omtalt','ikke_oppgitt','ikke_omtalt'],['ja','2','ja']]
        sessions=[]
        for k, expected in zip(kj,forventet):
            view=tjeneste.vis_kjoring(lager,k['id'])
            f=view['forsok'][-1]
            assert f['forsok']['status']=='fullført', f['forsok']['feil']
            answers=[f['vurderinger'][i]['svar'] for i in ['K1','K2','K3']]
            print(view['dokument']['navn'],answers,flush=True)
            assert answers==expected
            assert all(v['kontrollstatus']=='ikke kontrollert' for v in f['vurderinger'].values())
            sessions.append(f['forsok']['sesjon_id'])
        assert len(set(sessions))==4 and all(sessions)
        ex=tjeneste.eksporter(lager,aid,True)
        assert ex['kontrollert_av_totalt']=='0/12' and ex['ekte']
        print('BESTÅTT: 4 dokumenter, 12 svar, sitatkontroll, separate sesjoner og eksport. Ingen menneskelig godkjenning av svar.',flush=True)

if __name__=='__main__': main()
