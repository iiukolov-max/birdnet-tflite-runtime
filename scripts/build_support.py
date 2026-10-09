import json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def api(path):
    with urllib.request.urlopen(urllib.request.Request('https://api.github.com/'+path,headers={'User-Agent':'birdnet-runtime-build'}),timeout=90) as stream:return json.load(stream)
def expected_hash(url):
    lock=json.loads((ROOT/'provenance/download-lock.json').read_text())
    if url in lock:return lock[url]
    hashes={value for key,value in lock.items() if key.rsplit('/',1)[-1]==url.rsplit('/',1)[-1]}
    if len(hashes)!=1:raise ValueError('Unpinned download URL: '+url)
    return hashes.pop()
