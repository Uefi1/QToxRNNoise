# cmake-format: off
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2020 by The qTox Project Contributors
# Copyright © 2024-2025 The TokTok team
# cmake-format: on

set(SOURCE_FILES
    "include/audio/audio.h"
    "include/audio/iaudiocontrol.h"
    "include/audio/iaudiosettings.h"
    "include/audio/iaudiosink.h"
    "include/audio/iaudiosource.h"
    "include/audio/noisesuppressor.h"
    "src/iaudiosettings.cpp"
    "src/iaudiosink.cpp"
    "src/audio.cpp"
    "src/noisesuppressor.cpp"
    "src/backend/alsink.cpp"
    "src/backend/alsink.h"
    "src/backend/alsource.cpp"
    "src/backend/alsource.h"
    "src/backend/openal.cpp"
    "src/backend/openal.h")

# --- RNNoise (background noise suppression) ---------------------------------
# Vendored via FetchContent instead of a git submodule so forks/CI don't need
# any extra --recurse-submodules step. This is the same fork (plain portable
# C, no autotools/config.h required, no SSE/NEON RTCD) that Mumble has shipped
# on Windows/Linux/macOS for years, so it's known to cross-compile cleanly
# with MinGW.
include(FetchContent)
FetchContent_Declare(
    rnnoise_upstream
    GIT_REPOSITORY https://github.com/mumble-voip/rnnoise.git
    GIT_TAG master
    GIT_SHALLOW TRUE)
FetchContent_MakeAvailable(rnnoise_upstream)

add_library(rnnoise STATIC
    "${rnnoise_upstream_SOURCE_DIR}/src/denoise.c"
    "${rnnoise_upstream_SOURCE_DIR}/src/kiss_fft.c"
    "${rnnoise_upstream_SOURCE_DIR}/src/pitch.c"
    "${rnnoise_upstream_SOURCE_DIR}/src/celt_lpc.c"
    "${rnnoise_upstream_SOURCE_DIR}/src/rnn.c"
    "${rnnoise_upstream_SOURCE_DIR}/src/rnn_data.c"
    "${rnnoise_upstream_SOURCE_DIR}/src/rnn_reader.c")
target_include_directories(rnnoise PUBLIC "${rnnoise_upstream_SOURCE_DIR}/include")
target_include_directories(rnnoise PRIVATE "${rnnoise_upstream_SOURCE_DIR}/src")
if(NOT MSVC)
    target_link_libraries(rnnoise PRIVATE m)
endif()
# ------------------------------------------------------------------------------

add_library(audio_library STATIC ${SOURCE_FILES} resources/audio_res.qrc)

# We need this directory, and users of our library will need it too
target_include_directories(audio_library PUBLIC include/)

target_link_libraries(audio_library util_library)
target_link_libraries(audio_library Qt6::Core)
target_link_libraries(audio_library ${OPENAL_LIBRARIES})
target_link_libraries(audio_library rnnoise)
target_link_libraries(audio_library qtox::warnings)
