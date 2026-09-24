#!/bin/bash

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2024-2025 The TokTok team

set -eux -o pipefail

for key in .github/keys/*.asc; do
  gpg --import "$key"
done
