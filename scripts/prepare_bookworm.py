"""Materialize a Bookworm ARM64 build/test sysroot without running packages."""
import argparse, hashlib, io, json, lzma, shutil, tarfile, urllib.request, zipfile
from pathlib import Path

PACKAGES = ('libc6 libc6-dev linux-libc-dev libgcc-12-dev libgcc-s1 libstdc++6 '
            'libstdc++-12-dev libpython3.11-dev python3.11-minimal libpython3.11-minimal '
            'libpython3.11-stdlib python3.11 libexpat1 zlib1g libssl3 libbz2-1.0 liblzma5 '
            'libffi8 libreadline8 libncursesw6 libtinfo6 libuuid1 libgdbm6 libgdbm-compat4 '
            'libsqlite3-0 libcrypt1 libnsl2 libtirpc3 libtirpc-common libgssapi-krb5-2 '
            'libkrb5-3 libk5crypto3 libkrb5support0 libkeyutils1 libcom-err2').split()

def fetch(url, path, sha=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or (sha and hashlib.sha256(path.read_bytes()).hexdigest()!=sha):
        print('DOWNLOAD',path.name,flush=True)
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'birdnet-runtime-builder'}),timeout=120) as src, path.open('wb') as dst:
            shutil.copyfileobj(src,dst)
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if sha and digest!=sha:raise ValueError('Checksum mismatch: '+path.name)
    return digest

def deb_data(path):
    data=path.read_bytes()
    if data[:8]!=b'!<arch>\n':raise ValueError('Invalid deb')
    pos=8
    while pos+60<=len(data):
        head=data[pos:pos+60];pos+=60;size=int(head[48:58]);payload=data[pos:pos+size];pos+=size+(size%2)
        if head[:16].decode().strip().startswith('data.tar'):return payload
    raise ValueError('Missing data.tar')

def extract(path, root, links):
    with tarfile.open(fileobj=io.BytesIO(deb_data(path))) as archive:
        for item in archive:
            name=item.name.removeprefix('./');dest=(root/name).resolve()
            if not dest.is_relative_to(root.resolve()):raise ValueError('Unsafe archive path')
            if item.issym() or item.islnk():
                source=(root/item.linkname.lstrip('/')).resolve() if item.linkname.startswith('/') or item.islnk() else (dest.parent/item.linkname).resolve()
                if not source.is_relative_to(root.resolve()):raise ValueError('Unsafe symlink')
                links.append((dest,source))
            elif item.isdir():dest.mkdir(parents=True,exist_ok=True)
            elif item.isfile():
                dest.parent.mkdir(parents=True,exist_ok=True)
                with archive.extractfile(item) as inp,dest.open('wb') as out:shutil.copyfileobj(inp,out)
                dest.chmod(item.mode)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--work-dir',type=Path,required=True);args=parser.parse_args()
    work=args.work_dir.resolve();root=work/'sysroot';root.mkdir(parents=True,exist_ok=True)
    cache=work/'downloads';cache.mkdir(exist_ok=True);lock=work/'bookworm-inputs.json'
    pinned=Path(__file__).resolve().parents[1]/'provenance/bookworm-inputs.json'
    if not lock.exists() and pinned.exists():shutil.copyfile(pinned,lock)
    if lock.exists():records=json.loads(lock.read_text())
    else:
        index=cache/'Packages.xz';index_url='https://deb.debian.org/debian/dists/bookworm/main/binary-arm64/Packages.xz'
        index_sha=fetch(index_url,index);text=lzma.decompress(index.read_bytes()).decode();found={}
        for paragraph in text.split('\n\n'):
            fields={line.split(': ',1)[0]:line.split(': ',1)[1] for line in paragraph.splitlines() if ': ' in line and not line.startswith(' ')}
            if fields.get('Package') in PACKAGES:found[fields['Package']]=fields
        if set(PACKAGES)-found.keys():raise ValueError('Missing packages '+str(set(PACKAGES)-found.keys()))
        records={'index':{'url':index_url,'sha256':index_sha},'packages':[
            {'name':name,'version':found[name]['Version'],'url':'https://deb.debian.org/debian/'+found[name]['Filename'],'sha256':found[name]['SHA256']}
            for name in PACKAGES]}
        with urllib.request.urlopen('https://pypi.org/pypi/numpy/2.3.3/json',timeout=60) as inp:meta=json.load(inp)
        row=next(x for x in meta['urls'] if 'cp311-cp311-manylinux' in x['filename'] and 'aarch64' in x['filename'])
        records['numpy']={'name':row['filename'],'url':row['url'],'sha256':row['digests']['sha256'],'version':'2.3.3'}
        lock.write_text(json.dumps(records,indent=2)+'\n')
    links=[]
    for row in records['packages']:
        path=cache/row['url'].rsplit('/',1)[-1];fetch(row['url'],path,row['sha256']);extract(path,root,links)
    unresolved=[]
    for _ in range(12):
        remaining=[]
        for dst,src in links:
            if not src.exists():remaining.append((dst,src));continue
            dst.parent.mkdir(parents=True,exist_ok=True)
            if src.is_dir():shutil.copytree(src,dst,dirs_exist_ok=True)
            else:shutil.copyfile(src,dst)
        links=remaining
        if not links:break
    for path in [root/'usr/lib/aarch64-linux-gnu',root/'lib/aarch64-linux-gnu']:
        path.mkdir(parents=True,exist_ok=True)
    # The runtime loader resolves both merged-/usr and legacy library locations.
    shutil.copytree(root/'usr/lib/aarch64-linux-gnu',root/'lib/aarch64-linux-gnu',dirs_exist_ok=True)
    loader=root/'lib/aarch64-linux-gnu/ld-linux-aarch64.so.1'
    if loader.exists():shutil.copyfile(loader,root/'lib/ld-linux-aarch64.so.1')
    row=records['numpy'];wheel=cache/row['name'];fetch(row['url'],wheel,row['sha256'])
    with zipfile.ZipFile(wheel) as archive:archive.extractall(root/'numpy')
    (work/'sysroot-result.json').write_text(json.dumps({'packages':len(records['packages']),'unresolved_links':[(str(a.relative_to(root)),str(b.relative_to(root))) for a,b in links]},indent=2))
    print('READY',root,flush=True)

if __name__=='__main__':main()
