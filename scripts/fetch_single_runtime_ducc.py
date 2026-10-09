"""Fetch the FFT dependency pinned by the actual TensorFlow 2.17.1 source."""
import hashlib
from pathlib import Path
import tarfile
import urllib.request

root = Path(__file__).resolve().parents[1] / 'tfbuild/single-runtime'
root.mkdir(exist_ok=True)
commit = 'aa46a4c21e440b3d416c16eca3c96df19c74f316'
target = root / 'ducc.tar.gz'
url = 'https://storage.googleapis.com/mirror.tensorflow.org/gitlab.mpcdf.mpg.de/mtr/ducc/-/archive/' + commit + '/ducc-' + commit + '.tar.gz'
if not target.exists():
    urllib.request.urlretrieve(url, target)
assert hashlib.sha256(target.read_bytes()).hexdigest() == '077cf4bd0bd7eddaa6649a024285fff96e2662c5e6f2fb6ed5c5771f9de093f3'
with tarfile.open(target) as archive:
    selected = [member for member in archive.getmembers() if member.isfile() or member.isdir()]
    for member in selected:
        assert (root / member.name).resolve().is_relative_to(root.resolve())
    archive.extractall(root, members=selected)
print('Pinned DUCC extracted: ' + commit, flush=True)
