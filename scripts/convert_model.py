"""Exact FP16-to-FP32 constant storage experiment; no species or arithmetic removed."""
import hashlib
import json
import os
from pathlib import Path
os.environ['TF_CPP_MIN_LOG_LEVEL']='3'
import flatbuffers
import numpy as np
from tensorflow.lite.python import schema_py_generated as s

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'artifacts/tflite-research-20261009/fp32-storage'
OUT.mkdir(parents=True,exist_ok=True)
source=ROOT/'artifacts/BirdNET+_V3.0-preview3.1_Global_11K_FP16_pruned.tflite'
data=source.read_bytes(); original_hash=hashlib.sha256(data).hexdigest()
assert original_hash=='f4af6290690e0031cd785d4c810167af83467ce1426f4eba249ca994681000db'
model=s.ModelT.InitFromObj(s.Model.GetRootAsModel(data,0))
assert len(model.subgraphs)==1
graph=model.subgraphs[0]
original_shapes=[t.shape.tolist() for t in graph.tensors]
changed=[]; retained=[]; unused_inputs=set()
for index,op in enumerate(graph.operators):
    code=model.operatorCodes[op.opcodeIndex].builtinCode
    if code!=s.BuiltinOperator.DEQUANTIZE:
        retained.append(op); continue
    assert len(op.inputs)==len(op.outputs)==1
    inp=graph.tensors[int(op.inputs[0])]; out=graph.tensors[int(op.outputs[0])]
    buffer=model.buffers[inp.buffer]
    if inp.type!=s.TensorType.FLOAT16 or buffer.data is None or not len(buffer.data):
        retained.append(op); continue
    assert inp.sparsity is None, 'Sparse weights require a separate validated transformation'
    assert out.type==s.TensorType.FLOAT32
    weights=np.frombuffer(buffer.data.tobytes(),dtype='<f2')
    values=weights.astype('<f4')
    assert np.isfinite(values).all()
    assert np.array_equal(values.astype('<f2').view('<u2'),weights.view('<u2'))
    assert int(np.prod(out.shape,dtype=np.int64))==len(values)
    new=s.BufferT(); new.data=np.frombuffer(values.tobytes(),dtype=np.uint8)
    out.buffer=len(model.buffers); model.buffers.append(new)
    unused_inputs.add(int(op.inputs[0]))
    changed.append({'operator':index,'input_tensor':int(op.inputs[0]),'output_tensor':int(op.outputs[0]),'elements':len(values),'fp32_sha256':hashlib.sha256(values.tobytes()).hexdigest()})
graph.operators=retained
used=set(int(i) for i in graph.inputs)|set(int(i) for i in graph.outputs)
for op in retained:
    used.update(int(i) for i in op.inputs if i>=0); used.update(int(i) for i in op.outputs if i>=0)
old_buffers=set()
for index in unused_inputs-used:
    old_buffers.add(graph.tensors[index].buffer)
    graph.tensors[index].buffer=0
referenced={t.buffer for t in graph.tensors}|{m.buffer for m in (model.metadata or [])}
for index in old_buffers-referenced:
    model.buffers[index].data=None
assert changed and [t.shape.tolist() for t in graph.tensors]==original_shapes
assert any(list(graph.tensors[int(i)].shape)==[1,11560] for i in graph.outputs)

class Builder(flatbuffers.Builder):
    def EndVector(self,*args):return super().EndVector()
builder=Builder(0); offset=model.Pack(builder); builder.Finish(offset,file_identifier=b'TFL3')
target=OUT/'BirdNET_V3_full_FP32_weight_storage.tflite'
target.write_bytes(builder.Output())
assert hashlib.sha256(source.read_bytes()).hexdigest()==original_hash
check=s.ModelT.InitFromObj(s.Model.GetRootAsModel(target.read_bytes(),0))
assert [t.shape.tolist() for t in check.subgraphs[0].tensors]==original_shapes
assert len(check.subgraphs[0].operators)==len(retained)
result={'original_sha256':original_hash,'candidate_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'original_bytes':len(data),'candidate_bytes':target.stat().st_size,
        'constant_dequantize_removed':len(changed),'float32_constant_bytes':sum(r['elements']*4 for r in changed),'changed_constants':changed,
        'species_count':11560,'tensor_shapes_preserved':True,'weight_conversion':'Exact bit-preserving FP16 -> FP32 expansion; no quantization, no class/head slicing.',
        'status':'Structural validation passed; ARM inference equivalence and memory/speed effect NOT YET measured.'}
(OUT/'build-manifest.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='changed_constants'},indent=2),flush=True)
