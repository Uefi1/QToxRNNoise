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

    // RNNoise сильно искажает уже клипнутый вход.
    // Глушим вход ~6 dB, обрабатываем, смешиваем с сухим сигналом.
    constexpr float kPreGain = 0.5f;   // ослабление до RNNoise
    constexpr float kWet     = 0.65f;  // доля очищенного сигнала
    constexpr float kDry     = 0.35f;  // доля исходного (убирает «металл» и щелчки)

    for (int frameStart = 0; frameStart + kFrameSize <= sampleCount; frameStart += kFrameSize) {
        for (int i = 0; i < kFrameSize; ++i) {
            inFrame[static_cast<size_t>(i)] =
                static_cast<float>(samples[(frameStart + i) * stride]) * kPreGain;
        }

        rnnoise_process_frame(state, outFrame.data(), inFrame.data());

        for (int i = 0; i < kFrameSize; ++i) {
            const float dry = static_cast<float>(samples[(frameStart + i) * stride]);
            // outFrame уже в масштабе pre-gain; возвращаем уровень
            const float wet = outFrame[static_cast<size_t>(i)] / kPreGain;

            float mixed = dry * kDry + wet * kWet;
            mixed = std::clamp(mixed, -32768.0f, 32767.0f);
            samples[(frameStart + i) * stride] = static_cast<int16_t>(mixed);
        }
    }
}
