/* SPDX-License-Identifier: GPL-3.0-or-later
 * Copyright © 2026 by The qTox Project Contributors
 */

#pragma once

#include <cstdint>
#include <vector>

extern "C" {
#include <rnnoise.h>
}

/**
 * @brief Wraps RNNoise-based background noise suppression for a single audio
 *        channel of a capture stream.
 *
 * RNNoise operates on fixed-size 10ms (480 sample) mono float frames at
 * 48kHz. qTox captures 20ms frames (960 samples per channel) at 48kHz, so
 * each call to processChannel() runs RNNoise twice internally. One
 * NoiseSuppressor instance is required per audio input channel (mono
 * capture needs one, stereo capture needs two, etc).
 *
 * This is deliberately a thin, self-contained wrapper: it owns its RNNoise
 * state and scratch buffers, and has no dependency on the rest of the audio
 * backend beyond raw PCM in/out.
 */
class NoiseSuppressor
{
public:
    NoiseSuppressor();
    ~NoiseSuppressor();

    NoiseSuppressor(const NoiseSuppressor&) = delete;
    NoiseSuppressor& operator=(const NoiseSuppressor&) = delete;
    NoiseSuppressor(NoiseSuppressor&&) = delete;
    NoiseSuppressor& operator=(NoiseSuppressor&&) = delete;

    // RNNoise's fixed internal frame size (10ms @ 48kHz).
    static constexpr int kFrameSize = 480;

    /**
     * @brief Denoises audio in place for a single channel of a PCM buffer.
     * @param samples First sample belonging to this channel.
     * @param sampleCount Number of samples for this channel. Must be a
     *        multiple of kFrameSize (qTox's 960-sample, 20ms frames are
     *        exactly 2x kFrameSize, so this always holds in practice).
     * @param stride Distance, in samples, between consecutive samples of
     *        this channel inside an interleaved buffer (1 for a
     *        non-interleaved/mono buffer, equal to the channel count for
     *        an interleaved multi-channel buffer).
     */
    void processChannel(int16_t* samples, int sampleCount, int stride);

private:
    DenoiseState* state = nullptr;
    std::vector<float> inFrame;
    std::vector<float> outFrame;
};
