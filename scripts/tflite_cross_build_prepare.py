"""Prepare a Windows-hosted Linux/AArch64 cross build without compiling on Zero 2 W."""
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request
import zipfile
from build_support import ROOT, api

OUT=ROOT/'artifacts/tflite-research-20261009/build'
OUT.mkdir(parents=True,exist_ok=True)
COMMIT='3c92ac03cab816044f7b18a86eb86aa01a294d95'


def download(url,path):
    from build_support import expected_hash
    if not path.exists():
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'BirdNET-Pi-runtime-research'}),timeout=180) as stream,path.open('wb') as output:
            for block in iter(lambda:stream.read(1048576),b''): output.write(block)
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''): h.update(block)
    assert h.hexdigest()==expected_hash(url), 'Unpinned or corrupt input: '+url
    return {'url':url,'file':str(path),'bytes':path.stat().st_size,'sha256':h.hexdigest()}


def main():
    records=[]
    release=api('repos/mstorsjo/llvm-mingw/releases/tags/20261006')
    candidates=[a for a in release['assets'] if a['name'].endswith('ucrt-x86_64.zip')]
    assert len(candidates)==1
    asset=candidates[0]; archive=OUT/asset['name']
    assert asset['size']<300*1024*1024
    row=download(asset['browser_download_url'],archive)
    if asset.get('digest'): assert asset['digest']=='sha256:'+row['sha256']
    row['release_tag']=release['tag_name']; records.append(row)
    toolchain=OUT/'toolchain'; toolchain.mkdir(exist_ok=True)
    if not (toolchain/'extracted.json').exists():
        with zipfile.ZipFile(archive) as z:
            assert sum(i.file_size for i in z.infolist())<2*1024**3
            for item in z.infolist():
                destination=(toolchain/item.filename).resolve()
                assert destination.is_relative_to(toolchain.resolve())
            z.extractall(toolchain)
        (toolchain/'extracted.json').write_text(json.dumps(row))
    source=OUT/'tensorflow-source.tar.gz'
    row=download('https://codeload.github.com/tensorflow/tensorflow/tar.gz/'+COMMIT,source); records.append(row)
    # Short build path plus extended extraction paths handle upstream Java files
    # beyond the Windows legacy 260-character limit without system changes.
    source_dir=ROOT/'tfbuild/src'; source_dir.mkdir(parents=True,exist_ok=True)
    if not (source_dir/'extracted.json').exists():
        with tarfile.open(source) as tar:
            members=[m for m in tar.getmembers() if m.isfile() or m.isdir()]
            assert sum(m.size for m in members)<2*1024**3
            for item in members:
                item.name='/'.join(Path(item.name).parts[1:])
                if not item.name: continue
                assert (source_dir/item.name).resolve().is_relative_to(source_dir.resolve())
                tar.extract(item,path='\\\\?\\'+str(source_dir.resolve()))
        (source_dir/'extracted.json').write_text(json.dumps(row))
    for package,version in [('cmake','3.31.6'),('ninja','1.11.1.3'),('pybind11','2.13.6')]:
        with urllib.request.urlopen('https://pypi.org/pypi/'+package+'/'+version+'/json',timeout=60) as stream: meta=json.load(stream)
        candidates=[r for r in meta['urls'] if r['filename'].endswith('.whl') and ('win_amd64' in r['filename'] or 'py3-none-any' in r['filename'])]
        assert candidates
        entry=candidates[0]; archive=OUT/entry['filename']; row=download(entry['url'],archive)
        assert row['sha256']==entry['digests']['sha256']; records.append(row)
        target=OUT/package; target.mkdir(exist_ok=True)
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist(): assert (target/item.filename).resolve().is_relative_to(target.resolve())
            z.extractall(target)
    (OUT/'build-inputs.json').write_text(json.dumps({'tensorflow_commit':COMMIT,'downloads':records,'status':'inputs prepared; no compilation or speedup claimed'},indent=2))
    print(json.dumps({'prepared':True,'downloads':records},indent=2),flush=True)


if __name__=='__main__':main()
