# BirdNET TFLite runtime

Small build/patch repository for the unified runtime used by
[BirdNET-Pi](https://github.com/iiukolov-max/BirdNET-Pi_v3).

Runtime2.17.1.post2 is tested on Raspberry Pi Zero2W, Trixie ARM64,
CPython3.13 and NumPy2.3.3. It has a separate `birdnet_tflite_cached`
namespace and a small canonical `tflite_runtime` import bridge. Both use one
native library; the installer removes the previous native library after checks.
The native wheel is tagged
`cp313-cp313-linux_aarch64`, not manylinux. Other systems are not qualified.

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

V2/V3 and their geomodels matched all outputs on tested inputs. Legacy V1
has a small documented rounding difference (maximum logits delta 3.8147e-6
on two samples; same top five predictions). The unified build showed similar
V3 speed to the preceding optimized build in a short comparison. These are
synthetic-input checks; electrical energy has not been measured.

Build recipe: BUILD.md. Binary artifacts belong in Releases, not source Git.
