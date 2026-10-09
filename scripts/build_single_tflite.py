"""Isolated compatibility experiment; restore upstream source after compilation."""
import hashlib
import json
import os
import shutil
import subprocess
from tflite_cross_compile import BUILD, CMAKE, ENV

out = BUILD / 'single-runtime'
contract = os.environ.get('BIRDNET_FFT_FP_CONTRACT', 'fast')
assert contract in ('fast', 'off')
ducc = out / 'ducc-aa46a4c21e440b3d416c16eca3c96df19c74f316/src'
src = BUILD / 'src/tensorflow/lite'
files = [src / 'CMakeLists.txt', src / 'core/kernels/register.cc', src / 'tflite_with_xnnpack_optional.cc']
before = {p: p.read_bytes() for p in files}
kernel = out / 'birdnet_flex_ops.cc'
shutil.copyfile(BUILD.parent / 'scripts/birdnet_flex_ops.cc', kernel)
try:
    reg = before[files[1]].decode()
    reg = reg.replace('TfLiteRegistration* Register_NUMERIC_VERIFY();', 'TfLiteRegistration* Register_BIRDNET_FLEX_ERF();\nTfLiteRegistration* Register_BIRDNET_FLEX_RFFT();\nTfLiteRegistration* Register_NUMERIC_VERIFY();')
    reg = reg.replace('BuiltinOpResolver::BuiltinOpResolver() {', 'BuiltinOpResolver::BuiltinOpResolver() {\n  AddCustom("FlexErf", custom::Register_BIRDNET_FLEX_ERF());\n  AddCustom("FlexRFFT", custom::Register_BIRDNET_FLEX_RFFT());')
    files[1].write_text(reg)
    cache = before[files[2]].replace(b'#include <memory>', b'#include <memory>\n#include <cstdlib>')
    needle = b'  auto opts = TfLiteXNNPackDelegateOptionsDefault();'
    assert cache.count(needle) == 1
    cache = cache.replace(needle, needle + b'\n  if (const char* path = std::getenv("BIRDNET_RESEARCH_XNNPACK_CACHE")) { if (path[0] == \'/\') opts.experimental_weight_cache_file_path = path; }')
    files[2].write_bytes(cache)
    extras = [kernel, ducc / 'ducc0/infra/threading.cc']
    cmake = before[files[0]].decode() + '\n'
    quoted = ' '.join('"' + p.as_posix() + '"' for p in extras)
    cmake += 'target_sources(tensorflow-lite PRIVATE ' + quoted + ')\n'
    cmake += 'target_include_directories(tensorflow-lite PRIVATE "' + ducc.as_posix() + '")\n'
    cmake += 'set_source_files_properties(' + quoted + ' PROPERTIES COMPILE_FLAGS "-frtti -fexceptions -ffp-contract=' + contract + ' -DDUCC0_NO_LOWLEVEL_THREADING=1")\n'
    files[0].write_text(cmake)
    with (out / 'compile.log').open('w') as log:
        run = subprocess.run([str(CMAKE), '--build', str(BUILD / 'control'), '--parallel', '4', '--target', '_pywrap_tensorflow_interpreter_wrapper'], env=ENV, stdout=log, stderr=subprocess.STDOUT)
    if run.returncode:
        print((out / 'compile.log').read_text(errors='replace')[-6000:])
        raise SystemExit(run.returncode)
    package = out / 'runtime/birdnet_tflite_cached'
    package.mkdir(parents=True, exist_ok=True)
    original = BUILD / 'mmap-cache/runtime/tflite_runtime'
    for path in original.glob('*.py'):
        (package / path.name).write_text(path.read_text().replace('tflite_runtime', 'birdnet_tflite_cached'))
    binary = package / '_pywrap_tensorflow_interpreter_wrapper.so'
    shutil.copyfile(BUILD / 'control/_pywrap_tensorflow_interpreter_wrapper.so', binary)
    manifest = {'variant': 'mmap-cache+FlexErf+FlexRFFT', 'fft_fp_contract': contract, 'bytes': binary.stat().st_size,
                'sha256': hashlib.sha256(binary.read_bytes()).hexdigest(), 'status': 'compiled; unqualified'}
    (out / 'build-manifest.json').write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest), flush=True)
finally:
    for path, data in before.items():
        path.write_bytes(data)
