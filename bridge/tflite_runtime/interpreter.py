"""Canonical import of the single qualified native library; no weight cache here."""
import hashlib
import importlib
import json
from pathlib import Path
import sys
profile=json.loads(Path('/etc/birdnet/v3-runtime.json').read_text())
if not profile.get('unified_runtime'):
    raise ImportError('Unified BirdNET runtime profile is missing')
directory=Path(profile['runtime_dir'])
binary=directory/'birdnet_tflite_cached/_pywrap_tensorflow_interpreter_wrapper.so'
if hashlib.sha256(binary.read_bytes()).hexdigest()!=profile['runtime_sha256']:
    raise ImportError('Unified BirdNET native library checksum mismatch')
sys.path.insert(0,str(directory))
try:
    module=importlib.import_module('birdnet_tflite_cached.interpreter')
finally:
    sys.path.remove(str(directory))
sys.modules[__name__]=module
