// Copyright 2026 BirdNET-Pi fork contributors. Apache-2.0.
// Compact, explicitly typed compatibility kernels using upstream Eigen/DUCC math.
#include <algorithm>
#include <complex>
#include <limits>
#include <vector>
#include "tensorflow/lite/core/c/common.h"
#include "tensorflow/lite/kernels/kernel_util.h"
#include "unsupported/Eigen/CXX11/Tensor"
#include "ducc0/fft/fftnd_impl.h"

namespace tflite { namespace ops { namespace custom {
namespace {
TfLiteStatus ErfPrepare(TfLiteContext* c, TfLiteNode* n) {
  TF_LITE_ENSURE_EQ(c, n->inputs->size, 1);
  TF_LITE_ENSURE_EQ(c, n->outputs->size, 1);
  auto* in = GetInput(c, n, 0); auto* out = GetOutput(c, n, 0);
  TF_LITE_ENSURE_TYPES_EQ(c, in->type, kTfLiteFloat32);
  TF_LITE_ENSURE_TYPES_EQ(c, out->type, kTfLiteFloat32);
  return c->ResizeTensor(c, out, TfLiteIntArrayCopy(in->dims));
}
TfLiteStatus ErfEval(TfLiteContext* c, TfLiteNode* n) {
  auto* in = GetInput(c, n, 0); auto* out = GetOutput(c, n, 0);
  Eigen::Index count = in->bytes / sizeof(float);
  Eigen::TensorMap<Eigen::Tensor<const float, 1, Eigen::RowMajor>> input(in->data.f, count);
  Eigen::TensorMap<Eigen::Tensor<float, 1, Eigen::RowMajor>> output(out->data.f, count);
  output = input.erf();
  return kTfLiteOk;
}
TfLiteStatus RfftPrepare(TfLiteContext* c, TfLiteNode* n) {
  TF_LITE_ENSURE_EQ(c, n->inputs->size, 2);
  TF_LITE_ENSURE_EQ(c, n->outputs->size, 1);
  auto* in = GetInput(c, n, 0); auto* length = GetInput(c, n, 1); auto* out = GetOutput(c, n, 0);
  TF_LITE_ENSURE_TYPES_EQ(c, in->type, kTfLiteFloat32);
  TF_LITE_ENSURE_TYPES_EQ(c, length->type, kTfLiteInt32);
  TF_LITE_ENSURE_TYPES_EQ(c, out->type, kTfLiteComplex64);
  TF_LITE_ENSURE(c, in->dims->size >= 1 && length->bytes == sizeof(int32_t));
  TF_LITE_ENSURE(c, in->dims->data[in->dims->size - 1] >= 0);
  TF_LITE_ENSURE(c, IsConstantTensor(length));
  TF_LITE_ENSURE(c, length->data.i32[0] > 0);
  auto* dims = TfLiteIntArrayCopy(in->dims);
  dims->data[dims->size - 1] = length->data.i32[0] / 2 + 1;
  return c->ResizeTensor(c, out, dims);
}
TfLiteStatus RfftEval(TfLiteContext* c, TfLiteNode* n) {
  auto* in = GetInput(c, n, 0); auto* out = GetOutput(c, n, 0);
  size_t length = GetInput(c, n, 1)->data.i32[0];
  size_t old_length = in->dims->data[in->dims->size - 1];
  size_t batch = 1;
  for (int i = 0; i < in->dims->size - 1; ++i) {
    TF_LITE_ENSURE(c, in->dims->data[i] >= 0);
    size_t dim = in->dims->data[i];
    TF_LITE_ENSURE(c, dim == 0 || batch <= std::numeric_limits<size_t>::max() / dim);
    batch *= dim;
  }
  if (!batch) return kTfLiteOk;
  TF_LITE_ENSURE(c, batch <= std::numeric_limits<size_t>::max() / length / sizeof(float));
  try {
    std::vector<float> padded;
    const float* data = in->data.f;
    if (old_length != length) {
      padded.assign(batch * length, 0.0f);
      if (old_length)
        for (size_t row = 0; row < batch; ++row)
          std::copy_n(data + row * old_length, std::min(length, old_length), padded.data() + row * length);
      data = padded.data();
    }
    ducc0::cfmav<float> input(data, {batch, length});
    ducc0::vfmav<std::complex<float>> output(reinterpret_cast<std::complex<float>*>(out->data.c64), {batch, length / 2 + 1});
    ducc0::r2c(input, output, size_t(1), true, 1.0f, size_t(1));
  } catch (const std::exception& error) {
    c->ReportError(c, "BirdNET FlexRFFT: %s", error.what());
    return kTfLiteError;
  }
  return kTfLiteOk;
}
}
TfLiteRegistration* Register_BIRDNET_FLEX_ERF() {
  static TfLiteRegistration registration = {nullptr, nullptr, ErfPrepare, ErfEval};
  return &registration;
}
TfLiteRegistration* Register_BIRDNET_FLEX_RFFT() {
  static TfLiteRegistration registration = {nullptr, nullptr, RfftPrepare, RfftEval};
  return &registration;
}
}}}
