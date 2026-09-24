#!/usr/bin/env bash

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright © 2016 Zetok Zalbavar <zetok@openmailbox.org>
# Copyright © 2019 by The qTox Project Contributors
# Copyright © 2024-2025 The TokTok team.

# Script for updating translation files.  Should be ran after
# translatable strings are modified.
#
# Needed, since Weblate cannot do it automatically.

# Usage:
#   ./tools/$script_name [ALL|translation file]

set -eu -o pipefail

if [ -f /nix/store/*-qttools-*-dev/bin/lupdate ]; then
  export PATH="$PATH:$(dirname /nix/store/*-qttools-*-dev/bin/lupdate)"
fi

readonly LUPDATE_CMD=(lupdate src -no-obsolete -locations none)

if [ $# = 1 ] && [ "$1" = "ALL" ]; then
  for translation in translations/*.ts; do
    "${LUPDATE_CMD[@]}" -ts "$translation"
  done
  "${LUPDATE_CMD[@]}" -pluralonly -ts translations/en.ts
else
  "${LUPDATE_CMD[@]}" "$@"
fi

echo '<RCC>' >translations/translations.qrc
echo '    <qresource prefix="/translations">' >>translations/translations.qrc
for translation in translations/*.ts; do
  echo "        <file>$(basename "$translation" .ts).qm</file>" >>translations/translations.qrc
done
echo '    </qresource>' >>translations/translations.qrc
echo '</RCC>' >>translations/translations.qrc
