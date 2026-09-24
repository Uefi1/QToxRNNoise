/* SPDX-License-Identifier: GPL-3.0-or-later
 * Copyright © 2026 by The qTox Project Contributors
 */

#include "audio/noisesuppressor.h"

#include <algorithm>

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
    constexpr float kPreGain = 0.5f;  // ослабление до RNNoise
    constexpr float kWet = 0.65f;     // доля очищенного сигнала
    constexpr float kDry = 0.35f;     // доля исходного (меньше щелчков)

    for (int frameStart = 0; frameStart + kFrameSize <= sampleCount; frameStart += kFrameSize) {
        for (int i = 0; i < kFrameSize; ++i) {
            inFrame[static_cast<size_t>(i)] =
                static_cast<float>(samples[(frameStart + i) * stride]) * kPreGain;
        }

        rnnoise_process_frame(state, outFrame.data(), inFrame.data());

        for (int i = 0; i < kFrameSize; ++i) {
            const float dry = static_cast<float>(samples[(frameStart + i) * stride]);
            // outFrame в масштабе pre-gain — возвращаем уровень
            const float wet = outFrame[static_cast<size_t>(i)] / kPreGain;

            float mixed = dry * kDry + wet * kWet;
            mixed = std::clamp(mixed, -32768.0f, 32767.0f);
            samples[(frameStart + i) * stride] = static_cast<int16_t>(mixed);
        }
    }
}
