# BirdNET TFLite runtime

Small build/patch repository for the optional full-V3 runtime used by
[BirdNET-Pi](https://github.com/iiukolov-max/BirdNET-Pi_v3).

Runtime2.17.1.post1 is tested on Raspberry Pi Zero2W, Trixie ARM64,
CPython3.13 and NumPy2.3.3. It has a separate `birdnet_tflite_cached`
namespace; the original runtime remains available. The wheel is tagged
`cp313-cp313-linux_aarch64`, not manylinux. Other systems are not qualified.

The only runtime patch exposes the existing upstream XNNPACK mmap weight
cache option. TensorFlow commit is pinned in provenance. Full11560class V3
is retained. The installer creates a new cache on each target and verifies
exact outputs in isolated child processes before activation. Never reuse
the test device's cache as a release asset.

Release assets include the wheel, checksum/compatibility manifest, and a
gzip-compressed full model with FP32 storage of the original FP16 values.
The model is a storage-only derivative, not a newly trained/quantized model.
See MODEL_NOTICE.md and the upstream model terms. Runtime/dependency licenses
are in licenses/ and also included in the wheel.

Speed improves moderately and swap drops substantially on the tested device;
PSS does not decrease. Electrical energy has not been measured.

Build recipe: BUILD.md. Binary artifacts belong in Releases, not source Git.
