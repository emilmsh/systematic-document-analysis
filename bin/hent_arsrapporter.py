"""Last ned fem offentlige årsrapporter til eksempler/arsrapporter-2024/dokumenter."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]/'eksempler'/'arsrapporter-2024'


def hent(source):
    target = ROOT/'dokumenter'/source['fil']
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        data = target.read_bytes()
    else:
        with urlopen(Request(source['url'], headers={'User-Agent':'Systematic-Document-Analysis document download'}), timeout=90) as response:
            data = response.read()
        if not data.startswith(b'%PDF-'):
            raise ValueError(f"Ikke en PDF: {source['url']}")
        target.write_bytes(data)
    result = dict(source, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(),
                  kontrollert=datetime.now(timezone.utc).isoformat())
    try:
        from pypdf import PdfReader
        reader = PdfReader(target)
        texts = [page.extract_text() or '' for page in reader.pages]
        result.update(sider=len(texts), tegn=sum(map(len,texts)),
                      sider_uten_tekst=[i+1 for i,t in enumerate(texts) if not t.strip()])
        print(source['virksomhet'], result['sider'], 'sider;', result['tegn'], 'tegn;',
              'uten tekst:', result['sider_uten_tekst'], flush=True)
    except ImportError:
        print(f"Lastet ned {target.name}; installer pypdf for tekstkontroll.", flush=True)
    return result


if __name__ == '__main__':
    sources = json.loads((ROOT/'kilder.json').read_text(encoding='utf-8'))
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(hent,sources))
    (ROOT/'lesbarhet.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Ferdig: {ROOT / "dokumenter"}')
