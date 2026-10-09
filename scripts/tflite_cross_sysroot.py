"""Download checksum-pinned Debian/Raspberry Pi ABI headers and libraries on Windows."""
import io
import json
from pathlib import Path
import shutil
import tarfile
import urllib.error
import urllib.request
import zipfile
from tflite_cross_build_prepare import download,ROOT,OUT

TARGET=ROOT/'tfbuild/sysroot'
TARGET.mkdir(parents=True,exist_ok=True)
PACKAGES=OUT/'packages'; PACKAGES.mkdir(exist_ok=True)


def data_member(path):
    data=path.read_bytes(); assert data[:8]==b'!<arch>\n'; offset=8
    while offset+60<=len(data):
        header=data[offset:offset+60]; offset+=60
        name=header[:16].decode().strip().rstrip('/')
        size=int(header[48:58]); content=data[offset:offset+size]; offset+=size+(size%2)
        if name.startswith('data.tar'): return content
    raise RuntimeError('No data archive in '+str(path))


def main():
    packages=json.loads((ROOT/'provenance/sysroot-packages.json').read_text())
    records=[]; links=[]
    for row in packages:
        path=PACKAGES/Path(row['Filename']).name
        repositories=['https://archive.raspberrypi.com/debian/','https://deb.debian.org/debian/','https://security.debian.org/debian-security/','http://archive.raspberrypi.com/debian/']
        failures=[]
        for repository in repositories:
            try: result=download(repository+row['Filename'],path); break
            except urllib.error.HTTPError as error:
                failures.append({'url':repository+row['Filename'],'code':error.code})
                if error.code not in (404,403): raise
            except urllib.error.URLError as error:
                failures.append({'url':repository+row['Filename'],'error':str(error)})
        else: raise RuntimeError('Package not currently available: '+row['Package']+' '+json.dumps(failures))
        assert result['sha256']==row['SHA256']; records.append({**row,**result})
        with tarfile.open(fileobj=io.BytesIO(data_member(path))) as archive:
            for item in archive.getmembers():
                relative=item.name.lstrip('./')
                destination=(TARGET/relative).resolve()
                assert destination.is_relative_to(TARGET.resolve())
                if item.issym() or item.islnk():
                    source=(TARGET/item.linkname.lstrip('/')).resolve() if item.linkname.startswith('/') or item.islnk() else (destination.parent/item.linkname).resolve()
                    assert source.is_relative_to(TARGET.resolve())
                    links.append((destination,source)); continue
                if item.isdir(): destination.mkdir(parents=True,exist_ok=True)
                elif item.isfile():
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    with destination.open('wb') as output,archive.extractfile(item) as stream: shutil.copyfileobj(stream,output)
    # Materialize Linux symlinks inside the sysroot; Windows symlink privileges
    # and machine-wide configuration changes are unnecessary.
    for _ in range(10):
        remaining=[]
        for destination,source in links:
            if not source.exists(): remaining.append((destination,source)); continue
            destination.parent.mkdir(parents=True,exist_ok=True)
            if source.is_dir(): shutil.copytree(source,destination,dirs_exist_ok=True)
            else: shutil.copyfile(source,destination)
        links=remaining
        if not links: break
    if (TARGET/'usr/lib/aarch64-linux-gnu').exists():
        shutil.copytree(TARGET/'usr/lib/aarch64-linux-gnu',TARGET/'lib/aarch64-linux-gnu',dirs_exist_ok=True)
    if (TARGET/'usr/lib/ld-linux-aarch64.so.1').exists():
        shutil.copyfile(TARGET/'usr/lib/ld-linux-aarch64.so.1',TARGET/'lib/ld-linux-aarch64.so.1')
    with urllib.request.urlopen('https://pypi.org/pypi/numpy/2.3.3/json',timeout=60) as stream: meta=json.load(stream)
    row=next(r for r in meta['urls'] if 'cp313-cp313-' in r['filename'] and 'aarch64' in r['filename'] and 'manylinux' in r['filename'])
    path=PACKAGES/row['filename']; downloaded=download(row['url'],path); assert downloaded['sha256']==row['digests']['sha256']; records.append(downloaded)
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.startswith('numpy/_core/include/'):
                target=(TARGET/'numpy'/name).resolve(); assert target.is_relative_to((TARGET/'numpy').resolve())
                if name.endswith('/'): target.mkdir(parents=True,exist_ok=True)
                else: target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(archive.read(name))
    (OUT/'sysroot-manifest.json').write_text(json.dumps({'packages':records,'unresolved_links':[(str(a),str(b)) for a,b in links],'numpy_header_version':'2.3.3','scope':'Build-only sysroot; no Debian maintainer scripts executed or packages installed on Pi.'},indent=2))
    print(json.dumps({'sysroot':str(TARGET),'packages':len(records),'unresolved_links':len(links)},indent=2),flush=True)


if __name__=='__main__':main()
