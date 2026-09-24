#!/bin/bash

set -eux -o pipefail

source "/opt/buildhome/emsdk/emsdk_env.sh"

export PKG_CONFIG_PATH="/opt/buildhome/lib/pkgconfig"

ccache --zero-stats
ccache --show-config

emcmake cmake \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
  -DCMAKE_FIND_ROOT_PATH="/opt/buildhome;/opt/buildhome/qt" \
  -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DSTRICT_OPTIONS=ON \
  -DBUILD_TESTING=OFF \
  -GNinja \
  -B_build-wasm \
  -H.

cmake --build _build-wasm

mkdir -p _site
cp \
  platform/wasm/_headers \
  _build-wasm/qtloader.js \
  _build-wasm/qtlogo.svg \
  _build-wasm/qtox.js \
  _build-wasm/qtox.wasm \
  _site/
cp \
  _build-wasm/qtox.html \
  _site/index.html

ccache --show-stats
