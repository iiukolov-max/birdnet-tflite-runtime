"""Package an independently validated ARM64 CPython3.13 binary; no build on Pi."""
import argparse,base64,csv,hashlib,io,zipfile
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--runtime',type=Path,default=REPO/'tfbuild/mmap-cache/runtime/tflite_runtime')
parser.add_argument('--version',default='2.17.1.post1')
parser.add_argument('--expected-so-sha',default='1349cb9d88afe9c3aa35d881500b12d8d92b2eacdf171c670b919c750948ff4c')
args=parser.parse_args()
assert hashlib.sha256((args.runtime/'_pywrap_tensorflow_interpreter_wrapper.so').read_bytes()).hexdigest()==args.expected_so_sha
files={}
for path in args.runtime.iterdir():
    if path.suffix=='.py':files['birdnet_tflite_cached/'+path.name]=path.read_text().replace('tflite_runtime','birdnet_tflite_cached').encode()
    elif path.suffix=='.so':files['birdnet_tflite_cached/'+path.name]=path.read_bytes()
info='birdnet_tflite_runtime-'+args.version+'.dist-info/'
files[info+'METADATA']=('Metadata-Version: 2.1\nName: birdnet-tflite-runtime\nVersion: '+args.version+'\nSummary: Optional full-V3 XNNPACK cache runtime\nLicense: Apache-2.0\nRequires-Python: >=3.13,<3.14\nRequires-Dist: numpy>=2,<3\n\nTested on Trixie ARM64 and Pi Zero2W.\n').encode()
files[info+'WHEEL']=b'Wheel-Version: 1.0\nGenerator: birdnet-runtime-packager/1\nRoot-Is-Purelib: false\nTag: cp313-cp313-linux_aarch64\n'
for path in (REPO/'licenses').iterdir():files[info+'licenses/'+path.name]=path.read_bytes()
record=io.StringIO(newline='');writer=csv.writer(record,lineterminator='\n')
for name,data in sorted(files.items()):writer.writerow([name,'sha256='+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode(),len(data)])
writer.writerow([info+'RECORD','','']);files[info+'RECORD']=record.getvalue().encode()
out=REPO/'dist';out.mkdir(exist_ok=True)
wheel=out/('birdnet_tflite_runtime-'+args.version+'-cp313-cp313-linux_aarch64.whl')
with zipfile.ZipFile(wheel,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
    for name,data in sorted(files.items()):
        entry=zipfile.ZipInfo(name,(2026,10,9,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o644<<16;archive.writestr(entry,data)
print(wheel.name+' '+hashlib.sha256(wheel.read_bytes()).hexdigest())
