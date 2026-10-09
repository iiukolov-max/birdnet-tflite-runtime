"""Expose upstream mmap weight cache through an opt-in research environment."""
import hashlib
import json
import shutil
import subprocess
from tflite_cross_compile import BUILD,CMAKE,ENV

source=BUILD/'src/tensorflow/lite/tflite_with_xnnpack_optional.cc'
original=source.read_bytes()
needle=b'  auto opts = TfLiteXNNPackDelegateOptionsDefault();'
assert original.count(needle)==1
candidate=original.replace(b'#include <memory>',b'#include <memory>\n#include <cstdlib>').replace(needle,needle+b'''
  // Research only: unset by default. Each model/runtime has its own cache file.
  if (const char* path = std::getenv("BIRDNET_RESEARCH_XNNPACK_CACHE")) {
    if (path[0] == '/') opts.experimental_weight_cache_file_path = path;
  }
''')
OUT=BUILD/'mmap-cache'; OUT.mkdir(exist_ok=True)
try:
    source.write_bytes(candidate)
    with (OUT/'compile.log').open('w') as stream:
        result=subprocess.run([str(CMAKE),'--build',str(BUILD/'control'),'--parallel','4','--target','_pywrap_tensorflow_interpreter_wrapper'],stdout=stream,stderr=subprocess.STDOUT,env=ENV)
    assert result.returncode==0,(OUT/'compile.log').read_text()[-3000:]
    runtime=OUT/'runtime'; shutil.copytree(BUILD/'control/runtime',runtime,dirs_exist_ok=True)
    so=runtime/'tflite_runtime/_pywrap_tensorflow_interpreter_wrapper.so'
    shutil.copyfile(BUILD/'control/_pywrap_tensorflow_interpreter_wrapper.so',so)
    (runtime/'tflite_runtime/__init__.py').write_text("__version__ = '2.17.1+birdnet.mmapcache'\n")
    (OUT/'source-before.cc').write_bytes(original)
    (OUT/'source-after.cc').write_bytes(candidate)
    manifest={'variant':'mmap-cache','control_so_sha256':json.loads((BUILD/'control/build-manifest.json').read_text())['so_sha256'],
        'so_sha256':hashlib.sha256(so.read_bytes()).hexdigest(),'so_bytes':so.stat().st_size,
        'change':'Opt-in existing upstream XNNPACK experimental mmap weight cache; original FP16/model arithmetic unchanged. Cache must be unique per model/runtime.',
        'status':'Compiled only; ARM correctness and speed/memory unverified; not installed in production.'}
    assert manifest['so_sha256']!=manifest['control_so_sha256'],'Patch not linked into binary'
    (OUT/'build-manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,indent=2),flush=True)
finally:
    source.write_bytes(original)
