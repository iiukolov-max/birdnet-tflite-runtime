"""One model per process, shared by Trixie and isolated Bookworm userspaces."""
import argparse,importlib,os,sys
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--runtime',required=True);parser.add_argument('--model',required=True);parser.add_argument('--output',required=True);parser.add_argument('--input');parser.add_argument('--samples');parser.add_argument('--cache');args=parser.parse_args()
os.environ.pop('BIRDNET_RESEARCH_XNNPACK_CACHE',None)
if args.cache:os.environ['BIRDNET_RESEARCH_XNNPACK_CACHE']=args.cache
sys.path.insert(0,args.runtime)
from birdnet_tflite_cached.interpreter import Interpreter
import numpy as np
model=Interpreter(model_path=args.model,num_threads=2)
if args.input or '11K' in Path(args.model).name or 'full_FP32' in Path(args.model).name:model.resize_tensor_input(model.get_input_details()[0]['index'],[1,96000])
model.allocate_tensors();inputs=model.get_input_details();outputs=model.get_output_details()
delegates=sum(op['op_name']=='DELEGATE' for op in model._get_ops_details())
if ('11K' in Path(args.model).name or 'full_FP32' in Path(args.model).name) and not delegates:raise RuntimeError('XNNPACK delegate is inactive; check /sys and /proc CPU detection')
if args.samples:
    with np.load(args.samples) as stored:samples=[[stored[str(i)][j] for i in range(len(inputs))] for j in range(stored['0'].shape[0])]
elif args.input:
    samples=[[x.reshape(1,96000)] for x in np.load(args.input,allow_pickle=False)]
else:
    geo=len(inputs)==1 and list(inputs[0]['shape'])==[1,3]
    rng=np.random.default_rng(20261009)
    samples=([[np.array([[lat,lon,week]],dtype=np.float32)] for lat,lon in [(55.75,37.62),(0,0),(-33.87,151.21)] for week in range(-1,54)] if geo else [[rng.normal(0,.02,tuple(d['shape'])).astype(d['dtype']) for d in inputs] for _ in range(2)])
if not args.samples:
    np.savez(str(Path(args.output).with_suffix('.inputs.npz')),**{str(i):np.stack([row[i] for row in samples]) for i in range(len(inputs))})
result={str(d['index']):[] for d in outputs}
for sample in samples:
    for d,x in zip(inputs,sample):model.set_tensor(d['index'],x)
    model.invoke()
    for d in outputs:
        x=model.get_tensor(d['index'])
        if not np.isfinite(x).all():raise ValueError('Non-finite output')
        result[str(d['index'])].append(x)
np.savez(args.output,**{k:np.stack(v) for k,v in result.items()})
if args.cache:
    if not Path(args.cache).is_file() or not Path(args.cache).stat().st_size:raise RuntimeError('Weight cache file was not created')
    print('CACHE_BYTES',Path(args.cache).stat().st_size,flush=True)
print('DELEGATE_PARTITIONS',delegates,flush=True)
print('PASS',Path(args.model).name,'numpy',np.__version__,'values',sum(x.size for values in result.values() for x in values),flush=True)
