"""Build the pure-Python canonical import bridge; no second native library."""
import argparse,base64,csv,hashlib,io,zipfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--version',default='2.17.1.post2')
args=parser.parse_args();info='tflite_runtime-'+args.version+'.dist-info/'
files={'tflite_runtime/'+p.name:p.read_bytes() for p in (root/'bridge/tflite_runtime').glob('*.py')}
files['tflite_runtime/__init__.py']=("__version__ = '"+args.version+"'\n").encode()
files[info+'METADATA']=('Metadata-Version: 2.1\nName: tflite-runtime\nVersion: '+args.version+
    '\nRequires-Python: >=3.13,<3.14\nRequires-Dist: numpy>=2,<3\n\n').encode()
files[info+'WHEEL']=b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n'
stream=io.StringIO(newline='');writer=csv.writer(stream,lineterminator='\n')
for name,data in sorted(files.items()):writer.writerow([name,'sha256='+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode(),len(data)])
writer.writerow([info+'RECORD','','']);files[info+'RECORD']=stream.getvalue().encode()
out=root/'dist';out.mkdir(exist_ok=True)
target=out/('tflite_runtime-'+args.version+'-py3-none-any.whl')
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
    for name,data in sorted(files.items()):archive.writestr(name,data)
print(target.name+' '+hashlib.sha256(target.read_bytes()).hexdigest())
