# BirdNET TFLite runtime

Small build/patch repository for the unified runtime used by
[BirdNET-Pi](https://github.com/iiukolov-max/BirdNET-Pi_v3).

Runtime2.17.1.post3 provides two ARM64 builds for Raspberry Pi Zero2W:

| Raspberry Pi OS userspace | Python | NumPy checked | Wheel tag |
| --- | --- | --- | --- |
| Bookworm / glibc 2.36 | 3.11 | 1.26.4 and 2.3.3 | cp311-cp311-linux_aarch64 |
| Trixie / glibc 2.41 | 3.13 | 2.3.3 | cp313-cp313-linux_aarch64 |

Download the wheels, shared model, per-OS manifests, matrix and checksums from
[Releases](https://github.com/iiukolov-max/birdnet-tflite-runtime/releases/tag/v2.17.1.post3).
[BirdNET-Pi Preview10](https://github.com/iiukolov-max/BirdNET-Pi_v3/releases/tag/v3-preview.10)
selects the matching package automatically. Preview9 remains pinned to post2.
These are not 32-bit builds, and Python3.12 is not covered.

Bookworm is checked in isolated Debian Bookworm userspace on real Zero2W ARM64
hardware whose host OS is Trixie. This verifies the Python/glibc ABI and model
outputs, not a fresh Bookworm SD-card installation or its audio stack. See
`provenance/dual-os-validation.json` and the release validation attachment.
The Trixie native binary is unchanged from validated post2.
Bookworm V3 checks compare its original FP16 model against cold/reloaded
FP32-storage caches exactly. Bookworm NumPy1/2 outputs must also match exactly.
Cross-OS rounding is reported with absolute/relative error and acoustic top-five
checks; it is not described as bit-exact. See the attached validation contract.

The package has a separate `birdnet_tflite_cached`
namespace and a small canonical `tflite_runtime` import bridge. Both use one
native library; the installer removes the previous native library after checks.
The native wheel is tagged
`cp311-cp311-linux_aarch64` or `cp313-cp313-linux_aarch64`, not manylinux.
Other systems are not qualified. Bookworm does not need a system glibc or
Python upgrade. Use the application's virtual environment and installer;
the canonical bridge expects the installed checksum-pinned runtime profile.

The runtime exposes the existing upstream XNNPACK mmap weight cache option
and implements native FlexErf/FlexRFFT for geomodels and legacy V1.
TensorFlow and DUCC commits are pinned in provenance. Full11560class V3
is retained. The installer creates a new cache on each target and verifies
exact outputs in isolated child processes before activation. Never reuse
the test device's cache as a release asset.

Release assets include the wheel, checksum/compatibility manifest, and a
gzip-compressed full model with FP32 storage of the original FP16 values.
The model is a storage-only derivative, not a newly trained/quantized model.
See MODEL_NOTICE.md and the upstream model terms. Runtime/dependency licenses
are in licenses/ and also included in the wheel.

Earlier Trixie V2/V3 checks were exact; legacy V1 had a small documented
rounding difference. The current report lists each model's cross-OS error and
same-OS exact checks. The unified build showed similar
V3 speed to the preceding optimized build in a short comparison. These are
synthetic-input checks; electrical energy has not been measured.

Build recipe: BUILD.md. Binary artifacts belong in Releases, not source Git.
