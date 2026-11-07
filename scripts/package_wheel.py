"""Package an independently validated ABI-specific ARM64 binary; no build on Pi."""
import argparse,base64,csv,hashlib,io,zipfile
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--runtime',type=Path,default=REPO/'tfbuild/single-runtime/runtime/birdnet_tflite_cached')
parser.add_argument('--version',default='2.17.1.post2')
parser.add_argument('--python-tag',choices=('cp311','cp313'),default='cp313')
parser.add_argument('--output-dir',type=Path)
parser.add_argument('--expected-so-sha',default='150a5758b8ffdecef42d5030d91954770dd8aa717783ed857cb5ba8566278dcb')
args=parser.parse_args()
python_requires='>=3.11,<3.12' if args.python_tag=='cp311' else '>=3.13,<3.14'
numpy_requires='numpy>=1.24,<3' if args.python_tag=='cp311' else 'numpy>=2,<3'
platform_name='Bookworm ARM64' if args.python_tag=='cp311' else 'Trixie ARM64'
wheel_tag=args.python_tag+'-'+args.python_tag+'-linux_aarch64'
assert hashlib.sha256((args.runtime/'_pywrap_tensorflow_interpreter_wrapper.so').read_bytes()).hexdigest()==args.expected_so_sha
files={}
for path in args.runtime.iterdir():
    if path.suffix=='.py':files['birdnet_tflite_cached/'+path.name]=path.read_text().replace('tflite_runtime','birdnet_tflite_cached').encode()
    elif path.suffix=='.so':files['birdnet_tflite_cached/'+path.name]=path.read_bytes()
files['birdnet_tflite_cached/__init__.py']=("__version__ = '"+args.version+"'\n").encode()
info='birdnet_tflite_runtime-'+args.version+'.dist-info/'
files[info+'METADATA']=('Metadata-Version: 2.1\nName: birdnet-tflite-runtime\nVersion: '+args.version+'\nSummary: Optional full-V3 XNNPACK cache runtime\nLicense: Apache-2.0\nRequires-Python: '+python_requires+'\nRequires-Dist: '+numpy_requires+'\n\nTarget: '+platform_name+' and Pi Zero2W; see release validation report.\n').encode()
files[info+'WHEEL']=('Wheel-Version: 1.0\nGenerator: birdnet-runtime-packager/2\nRoot-Is-Purelib: false\nTag: '+wheel_tag+'\n').encode()
for path in (REPO/'licenses').iterdir():files[info+'licenses/'+path.name]=path.read_bytes()
record=io.StringIO(newline='');writer=csv.writer(record,lineterminator='\n')
for name,data in sorted(files.items()):writer.writerow([name,'sha256='+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode(),len(data)])
writer.writerow([info+'RECORD','','']);files[info+'RECORD']=record.getvalue().encode()
out=args.output_dir or REPO/'dist';out.mkdir(parents=True,exist_ok=True)
wheel=out/('birdnet_tflite_runtime-'+args.version+'-'+wheel_tag+'.whl')
with zipfile.ZipFile(wheel,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
    for name,data in sorted(files.items()):
        entry=zipfile.ZipInfo(name,(2026,10,9,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o644<<16;archive.writestr(entry,data)
print(wheel.name+' '+hashlib.sha256(wheel.read_bytes()).hexdigest())
