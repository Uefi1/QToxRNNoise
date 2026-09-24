#!/bin/sh

set -eux

docker build -t toxchat/qtox:wasm -f platform/wasm/Dockerfile .
docker run --rm -it -p 8000:8000 toxchat/qtox:wasm
