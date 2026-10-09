# Building the runtime

The release binary was built on a Windows x64 host for Trixie AArch64.
Do not compile on the Zero2W. Python3.10+, network access and a short checkout
path are needed. The recipe downloads SHA256-pinned build inputs only.

```powershell
python scripts/tflite_cross_build_prepare.py
python scripts/tflite_build_git.py
python scripts/tflite_cross_sysroot.py
python scripts/tflite_cross_compile.py control
python scripts/tflite_cache_build.py
```

Dependency commits are fixed by the pinned TensorFlow commit; their actual
resolved commits are in provenance/source-provenance.json. Compare them
before packaging. Historical provenance/control-build.json records the exact
compiler flags, Clang version and original binary input. `${WORKSPACE}` denotes
the checkout root. Windows paths/sysroot materialization are intentional.

This is the recorded cross-build recipe, not a claim that different hosts
produce bit-identical binaries. Every new binary needs ABI and exact-output
validation on the target and a new release manifest/cache. Never replace an
existing version's asset with a different binary.

The package script creates the isolated namespace wheel from the built
tfbuild/mmap-cache/runtime/tflite_runtime directory. Rebuilding requires
updating its expected binary SHA after independent validation. Model artifacts
are separate from runtime code; optional off-device conversion is documented
in scripts/convert_model.py, preserving full11560classes. The installer uses
a preconverted verified gzip artifact to avoid large conversion RAM on Pi.
