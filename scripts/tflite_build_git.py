"""Portable Git for CMake dependency fetching; workspace only."""
import json
import zipfile
from tflite_cross_build_prepare import OUT,download
from build_support import api

release=api('repos/git-for-windows/git/releases/tags/v2.56.0.windows.2')
asset=next(a for a in release['assets'] if a['name'].startswith('MinGit-') and a['name'].endswith('-64-bit.zip') and 'busybox' not in a['name'])
path=OUT/asset['name']; result=download(asset['browser_download_url'],path)
if asset.get('digest'): assert asset['digest']=='sha256:'+result['sha256']
target=OUT/'git'; target.mkdir(exist_ok=True)
with zipfile.ZipFile(path) as archive:
    for name in archive.namelist(): assert (target/name).resolve().is_relative_to(target.resolve())
    archive.extractall(target)
(OUT/'git-manifest.json').write_text(json.dumps({'tag':release['tag_name'],**result},indent=2))
print(json.dumps(result,indent=2),flush=True)
