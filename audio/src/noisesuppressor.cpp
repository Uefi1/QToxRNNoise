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

    // RNNoise ломается на уже клипнутом входе (классическая проблема Mumble).
    // Режем пики ДО модели, на выходе — 100% wet, без dry-mix и без усиления.
    constexpr float kMaxIn = 28000.0f; // ~1.3 dB запаса до int16

    for (int frameStart = 0; frameStart + kFrameSize <= sampleCount; frameStart += kFrameSize) {
        for (int i = 0; i < kFrameSize; ++i) {
            float s = static_cast<float>(samples[(frameStart + i) * stride]);
            s = std::clamp(s, -kMaxIn, kMaxIn);
            inFrame[static_cast<size_t>(i)] = s;
        }

        rnnoise_process_frame(state, outFrame.data(), inFrame.data());

        for (int i = 0; i < kFrameSize; ++i) {
            float y = outFrame[static_cast<size_t>(i)];
            y = std::clamp(y, -32768.0f, 32767.0f);
            samples[(frameStart + i) * stride] = static_cast<int16_t>(y);
        }
    }
}
