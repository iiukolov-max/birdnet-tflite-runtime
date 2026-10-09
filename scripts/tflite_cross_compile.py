"""Reproducible conservative ARM64 control build on Windows, isolated from Pi."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from build_support import ROOT

BUILD=ROOT/'tfbuild'
INPUTS=ROOT/'artifacts/tflite-research-20261009/build'
CLANG=next((INPUTS/'toolchain').rglob('clang.exe'))
CLANGXX=CLANG.with_name('clang++.exe')
CMAKE=next((INPUTS/'cmake').rglob('cmake.exe'))
NINJA=next((INPUTS/'ninja').rglob('ninja.exe'))
SYSROOT=BUILD/'sysroot'
PYBIND=INPUTS/'pybind11/pybind11/include'
NUMPY=SYSROOT/'numpy/numpy/_core/include'
VARIANT=sys.argv[1] if len(sys.argv)>1 else 'control'
assert VARIANT in ('control','a53')
OUT=BUILD/VARIANT; OUT.mkdir(exist_ok=True)
GIT=INPUTS/'git/cmd/git.exe'
ENV=dict(os.environ,PATH=str(CLANG.parent)+os.pathsep+str(NINJA.parent)+os.pathsep+str(GIT.parent)+os.pathsep+os.environ['PATH'])


def command(args,name):
    path=OUT/(name+'.log')
    print(json.dumps({'phase':name,'started':datetime.datetime.now().astimezone().isoformat(),'log':str(path)}),flush=True)
    with path.open('w',encoding='utf-8') as stream:
        result=subprocess.run([str(a) for a in args],stdout=stream,stderr=subprocess.STDOUT,env=ENV)
    print(json.dumps({'phase':name,'returncode':result.returncode}),flush=True)
    if result.returncode:
        print(path.read_text(encoding='utf-8',errors='replace')[-6000:],flush=True)
        raise SystemExit(result.returncode)


def main():
    flags='-march=armv8-a' if VARIANT=='control' else '-mcpu=cortex-a53'
    command([CLANGXX,'--target=aarch64-linux-gnu','--sysroot='+str(SYSROOT),'-fuse-ld=lld',flags,BUILD/'probe.cpp','-o',OUT/'probe'], 'abi-probe')
    data=(OUT/'probe').read_bytes(); assert data[:4]==b'\x7fELF' and data[18:20]==b'\xb7\x00'
    includes=[SYSROOT/'usr/include/python3.13',SYSROOT/'usr/include/aarch64-linux-gnu/python3.13',PYBIND,NUMPY]
    assert all(p.is_dir() for p in includes)
    cflags=flags+' '+' '.join('-I'+p.as_posix() for p in includes)
    configuration=[CMAKE,'-S',BUILD/'src/tensorflow/lite','-B',OUT,'-G','Ninja',
        '-DCMAKE_MAKE_PROGRAM='+NINJA.as_posix(),'-DCMAKE_C_COMPILER='+CLANG.as_posix(),'-DCMAKE_CXX_COMPILER='+CLANGXX.as_posix(),
        '-DCMAKE_C_COMPILER_TARGET=aarch64-linux-gnu','-DCMAKE_CXX_COMPILER_TARGET=aarch64-linux-gnu','-DCMAKE_SYSTEM_NAME=Linux','-DCMAKE_SYSTEM_PROCESSOR=aarch64',
        '-DCMAKE_ASM_COMPILER='+CLANG.as_posix(),'-DCMAKE_ASM_FLAGS=--target=aarch64-linux-gnu '+flags,
        '-DCMAKE_SYSROOT='+SYSROOT.as_posix(),'-DCMAKE_C_FLAGS='+cflags,'-DCMAKE_CXX_FLAGS='+cflags,'-DCMAKE_EXE_LINKER_FLAGS=-fuse-ld=lld','-DCMAKE_SHARED_LINKER_FLAGS=-fuse-ld=lld',
        '-DCMAKE_BUILD_TYPE=Release','-DTFLITE_ENABLE_XNNPACK=ON','-DTFLITE_ENABLE_GPU=OFF','-DTFLITE_ENABLE_NNAPI=OFF','-DXNNPACK_ENABLE_ARM_I8MM=OFF',
        '-DTFLITE_KERNEL_TEST=OFF','-DFETCHCONTENT_QUIET=OFF','-DGIT_EXECUTABLE='+GIT.as_posix()]
    if VARIANT=='a53':
        configuration.append('-DCMAKE_INTERPROCEDURAL_OPTIMIZATION=ON')
        # Reuse verified source checkouts, with separate object directories.
        for name in ('abseil-cpp','cpuinfo','eigen','farmhash','fft2d','flatbuffers','gemmlowp','ml_dtypes','protobuf','ruy','xnnpack'):
            source=BUILD/'control'/name
            assert source.is_dir(),source
            configuration.append('-DFETCHCONTENT_SOURCE_DIR_'+name.upper()+'='+source.as_posix())
        for key,name in [('FP16','FP16-source'),('FXDIV','FXdiv-source'),('PSIMD','psimd-source'),('PTHREADPOOL','pthreadpool-source')]:
            configuration.append('-D'+key+'_SOURCE_DIR='+(BUILD/'control'/name).as_posix())
        configuration.append('-DFETCHCONTENT_FULLY_DISCONNECTED=ON')
    command(configuration,'configure')
    command([CMAKE,'--build',OUT,'--parallel','4','--target','_pywrap_tensorflow_interpreter_wrapper'],'compile')
    so=OUT/'_pywrap_tensorflow_interpreter_wrapper.so'; assert so.exists()
    runtime=OUT/'runtime/tflite_runtime'; runtime.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(so,runtime/so.name)
    for name,path in [('interpreter.py','python/interpreter.py'),('metrics_interface.py','python/metrics/metrics_interface.py'),('metrics_portable.py','python/metrics/metrics_portable.py')]:
        shutil.copyfile(BUILD/'src/tensorflow/lite'/path,runtime/name)
    (runtime/'__init__.py').write_text("__version__ = '2.17.1+birdnet."+VARIANT+"'\n")
    manifest={'variant':VARIANT,'tensorflow_commit':'3c92ac03cab816044f7b18a86eb86aa01a294d95','compiler':subprocess.check_output([str(CLANG),'--version'],text=True).splitlines()[0],
        'configuration':[str(a) for a in configuration],'so_bytes':so.stat().st_size,'so_sha256':hashlib.sha256(so.read_bytes()).hexdigest(),
        'status':'Build completed; target import/inference/quality and performance not yet verified. Not installed in production.'}
    (OUT/'build-manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,indent=2),flush=True)


if __name__=='__main__':main()
