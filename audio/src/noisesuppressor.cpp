/* SPDX-License-Identifier: GPL-3.0-or-later
 * Copyright © 2026 by The qTox Project Contributors
 */

#include "audio/noisesuppressor.h"

#include <algorithm>
#include <cmath>

namespace {
constexpr float kFullScale = 32767.0f;
// Below this fraction of full scale, output is passed through completely
// unchanged (transparent for normal speech levels). Only samples RNNoise
// pushes above this threshold get smoothly saturated instead of hard-clipped,
// which is what was producing audible crackle on loud syllables/consonants.
constexpr float kKnee = 0.9f;

int16_t softClip(float sample)
{
    const float x = sample / kFullScale;
    const float ax = std::fabs(x);

    float y = x;
    if (ax > kKnee) {
        const float sign = x < 0.0f ? -1.0f : 1.0f;
        const float t = (ax - kKnee) / (1.0f - kKnee);
        const float saturated = kKnee + (1.0f - kKnee) * std::tanh(t);
        y = sign * saturated;
    }

    return static_cast<int16_t>(std::clamp(y * kFullScale, -32768.0f, 32767.0f));
}
} // namespace

NoiseSuppressor::NoiseSuppressor()
    : state(rnnoise_create(nullptr))
    , inFrame(kFrameSize)
    , outFrame(kFrameSize)
{
}

NoiseSuppressor::~NoiseSuppressor()
{
    if (state != nullptr) {
        rnnoise_destroy(state);
    }
}

void NoiseSuppressor::processChannel(int16_t* samples, int sampleCount, int stride)
{
    if (state == nullptr || stride <= 0) {
        return;
    }

    for (int frameStart = 0; frameStart + kFrameSize <= sampleCount; frameStart += kFrameSize) {
        // RNNoise expects float PCM in the same numeric range as int16_t
        // (i.e. NOT normalized to [-1, 1]).
        for (int i = 0; i < kFrameSize; ++i) {
            inFrame[static_cast<size_t>(i)] =
                static_cast<float>(samples[(frameStart + i) * stride]);
        }

        // Return value is a voice-activity-detection probability [0, 1];
        // we don't use it here, but it's available if a VAD-gated mode is
        // wanted later.
        rnnoise_process_frame(state, outFrame.data(), inFrame.data());

        for (int i = 0; i < kFrameSize; ++i) {
            // ~1 dB headroom so later applyGain rarely hard-clips
            samples[(frameStart + i) * stride] =
                softClip(outFrame[static_cast<size_t>(i)] * 0.9f);
        }
    }
}
