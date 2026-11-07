"""Cross-build the unified cp311 runtime with the recorded Windows toolchain."""
import argparse, hashlib, json, os, shutil, subprocess, time
from pathlib import Path

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--jobs',type=int,default=4);args=parser.parse_args()
    root=args.workspace.resolve();build=root/'tfbuild';out=build/'bookworm';sysroot=out/'sysroot';objects=out/'objects';objects.mkdir(exist_ok=True)
    inputs=root/'artifacts/tflite-research-20261009/build'
    clang=next((inputs/'toolchain').rglob('clang.exe'));clangxx=clang.with_name('clang++.exe')
    cmake=next((inputs/'cmake').rglob('cmake.exe'));ninja=next((inputs/'ninja').rglob('ninja.exe'));git=inputs/'git/cmd/git.exe'
    env=dict(os.environ,PATH=os.pathsep.join([str(clang.parent),str(ninja.parent),str(git.parent),os.environ['PATH']]))
    source=build/'src/tensorflow/lite';ducc=build/'single-runtime/ducc-aa46a4c21e440b3d416c16eca3c96df19c74f316/src'
    kernel=out/'birdnet_flex_ops.cc';shutil.copyfile(Path(__file__).parent/'birdnet_flex_ops.cc',kernel)
    paths=[source/'CMakeLists.txt',source/'core/kernels/register.cc',source/'tflite_with_xnnpack_optional.cc']
    before={p:p.read_bytes() for p in paths}
    if 'Register_BIRDNET_FLEX_ERF' in before[paths[1]].decode():raise RuntimeError('Source already patched; inspect concurrent build')
    def run(command,name):
        print('START',name,time.strftime('%Y-%m-%d %H:%M:%S'),flush=True)
        with (out/(name+'.log')).open('w') as f:p=subprocess.run([str(x) for x in command],env=env,stdout=f,stderr=subprocess.STDOUT)
        print('END',name,p.returncode,flush=True)
        if p.returncode:
            print((out/(name+'.log')).read_text(errors='replace')[-6500:],flush=True);raise SystemExit(p.returncode)
    try:
        reg=before[paths[1]].decode().replace('TfLiteRegistration* Register_NUMERIC_VERIFY();','TfLiteRegistration* Register_BIRDNET_FLEX_ERF();\nTfLiteRegistration* Register_BIRDNET_FLEX_RFFT();\nTfLiteRegistration* Register_NUMERIC_VERIFY();')
        reg=reg.replace('BuiltinOpResolver::BuiltinOpResolver() {','BuiltinOpResolver::BuiltinOpResolver() {\n  AddCustom("FlexErf", custom::Register_BIRDNET_FLEX_ERF());\n  AddCustom("FlexRFFT", custom::Register_BIRDNET_FLEX_RFFT());')
        paths[1].write_text(reg)
        cache=before[paths[2]].decode().replace('#include <memory>','#include <memory>\n#include <cstdlib>')
        needle='  auto opts = TfLiteXNNPackDelegateOptionsDefault();';assert cache.count(needle)==1
        cache=cache.replace(needle,needle+'\n  if (const char* path = std::getenv("BIRDNET_RESEARCH_XNNPACK_CACHE")) { if (path[0] == \'/\') opts.experimental_weight_cache_file_path = path; }')
        paths[2].write_text(cache)
        extras=' '.join('"'+p.as_posix()+'"' for p in [kernel,ducc/'ducc0/infra/threading.cc'])
        paths[0].write_text(before[paths[0]].decode()+'\ntarget_sources(tensorflow-lite PRIVATE '+extras+')\ntarget_include_directories(tensorflow-lite PRIVATE "'+ducc.as_posix()+'")\nset_source_files_properties('+extras+' PROPERTIES COMPILE_FLAGS "-frtti -fexceptions -ffp-contract=fast -DDUCC0_NO_LOWLEVEL_THREADING=1")\n')
        includes=[sysroot/'usr/include/python3.11',sysroot/'usr/include/aarch64-linux-gnu/python3.11',inputs/'pybind11/pybind11/include',sysroot/'numpy/numpy/_core/include']
        assert all(p.is_dir() for p in includes),includes
        flags='-march=armv8-a '+' '.join('-I'+p.as_posix() for p in includes)
        configuration=[cmake,'-S',source,'-B',objects,'-G','Ninja','-DCMAKE_MAKE_PROGRAM='+ninja.as_posix(),'-DCMAKE_C_COMPILER='+clang.as_posix(),'-DCMAKE_CXX_COMPILER='+clangxx.as_posix(),'-DCMAKE_C_COMPILER_TARGET=aarch64-linux-gnu','-DCMAKE_CXX_COMPILER_TARGET=aarch64-linux-gnu','-DCMAKE_SYSTEM_NAME=Linux','-DCMAKE_SYSTEM_PROCESSOR=aarch64','-DCMAKE_ASM_COMPILER='+clang.as_posix(),'-DCMAKE_ASM_FLAGS=--target=aarch64-linux-gnu -march=armv8-a','-DCMAKE_SYSROOT='+sysroot.as_posix(),'-DCMAKE_C_FLAGS='+flags,'-DCMAKE_CXX_FLAGS='+flags,'-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld','-DCMAKE_SHARED_LINKER_FLAGS=-fuse-ld=lld','-DCMAKE_BUILD_TYPE=Release','-DTFLITE_ENABLE_XNNPACK=ON','-DTFLITE_ENABLE_GPU=OFF','-DTFLITE_ENABLE_NNAPI=OFF','-DXNNPACK_ENABLE_ARM_I8MM=OFF','-DTFLITE_KERNEL_TEST=OFF','-DFETCHCONTENT_FULLY_DISCONNECTED=ON','-DGIT_EXECUTABLE='+git.as_posix()]
        for name in ('abseil-cpp','cpuinfo','eigen','farmhash','fft2d','flatbuffers','gemmlowp','ml_dtypes','protobuf','ruy','xnnpack'):
            p=build/'control'/name;assert p.is_dir();configuration.append('-DFETCHCONTENT_SOURCE_DIR_'+name.upper()+'='+p.as_posix())
        for key,name in [('FP16','FP16-source'),('FXDIV','FXdiv-source'),('PSIMD','psimd-source'),('PTHREADPOOL','pthreadpool-source')]:configuration.append('-D'+key+'_SOURCE_DIR='+(build/'control'/name).as_posix())
        run(configuration,'configure');run([cmake,'--build',objects,'--parallel',str(args.jobs),'--target','_pywrap_tensorflow_interpreter_wrapper'],'compile')
        package=out/'runtime/birdnet_tflite_cached';package.mkdir(parents=True,exist_ok=True)
        for p in (build/'single-runtime/runtime/birdnet_tflite_cached').glob('*.py'):shutil.copyfile(p,package/p.name)
        binary=package/'_pywrap_tensorflow_interpreter_wrapper.so';shutil.copyfile(objects/binary.name,binary)
        manifest={'platform':'bookworm-arm64-cp311','tensorflow_commit':'3c92ac03cab816044f7b18a86eb86aa01a294d95','compiler':subprocess.check_output([str(clang),'--version'],text=True).splitlines()[0],'configuration':[str(x) for x in configuration],'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'bytes':binary.stat().st_size,'status':'compiled; validation pending'}
        (out/'build-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps(manifest),flush=True)
    finally:
        for p,data in before.items():p.write_bytes(data)

if __name__=='__main__':main()
