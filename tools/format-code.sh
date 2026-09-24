#!/bin/bash

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2017-2019 by The qTox Project Contributors
# Copyright © 2024-2025 The TokTok team

# Format all C++ codebase tracked by git using `clang-format`.

# Requires:
#   * git
#   * clang-format

# usage:
#   ./$script

# Fail as soon as error appears
set -eu -o pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly BASE_DIR="$SCRIPT_DIR/../"

format() {
  cd "$BASE_DIR"
  [[ -f .clang-format ]] # make sure that it exists
  # NOTE: some earlier than 3.8 versions of clang-format are broken
  # and will not work correctly
  clang-format -i -style=file "$(git ls-files "*.cpp" "*.h" "*.mm")"
}
format
