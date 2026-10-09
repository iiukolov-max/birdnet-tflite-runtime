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
python scripts/fetch_single_runtime_ducc.py
python scripts/build_single_tflite.py
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

The unified build creates the isolated namespace in
tfbuild/single-runtime/runtime/birdnet_tflite_cached. Its native FlexErf uses
Eigen; FlexRFFT uses DUCC aa46a4c21e440b3d416c16eca3c96df19c74f316,
archive SHA256 077cf4bd0bd7eddaa6649a024285fff96e2662c5e6f2fb6ed5c5771f9de093f3.
DUCC FFT/threading uses the BSD-3-Clause option and one FFT thread.
The default qualified build uses fp-contract=fast; the off variant is unqualified.

The package script creates the isolated namespace wheel from the built
runtime directory supplied with --runtime. Rebuilding requires
updating its expected binary SHA after independent validation. Model artifacts
are separate from runtime code; optional off-device conversion is documented
in scripts/convert_model.py, preserving full11560classes. The installer uses
a preconverted verified gzip artifact to avoid large conversion RAM on Pi.

`python scripts/package_bridge.py` packages the canonical import bridge.
It contains only Python/metadata. The app installer links it into the venv
after candidate-model checks and activates the checksum-pinned native profile.
Disabling the V3 cache keeps this same library and loads the original full model.
