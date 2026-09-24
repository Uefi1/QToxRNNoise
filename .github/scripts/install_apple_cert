#!/bin/sh

# https://docs.github.com/en/actions/use-cases-and-examples/deploying/installing-an-apple-certificate-on-macos-runners-for-xcode-development

set -euo pipefail

# Needs:
#   BUILD_CERTIFICATE_BASE64: base64-encoded dev cert
#   P12_PASSWORD:             password used to encrypt the dev cert
#   KEYCHAIN_PASSWORD:        some random password

# create variables
CERTIFICATE_PATH="$RUNNER_TEMP/build_certificate.p12"
KEYCHAIN_PATH="$RUNNER_TEMP/app-signing.keychain-db"

# if certificate is empty, do nothing
if [ -z "$BUILD_CERTIFICATE_BASE64" ]; then
  echo "No certificate provided, skipping..." >/dev/stderr
  exit 0
fi

# import certificate and provisioning profile from secrets
echo -n "$BUILD_CERTIFICATE_BASE64" | base64 --decode -o "$CERTIFICATE_PATH"

# create temporary keychain
security create-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
security set-keychain-settings -lut 21600 "$KEYCHAIN_PATH"
security unlock-keychain -p "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"

# import certificate to keychain
security import "$CERTIFICATE_PATH" -P "$P12_PASSWORD" -A -t cert -f pkcs12 -k "$KEYCHAIN_PATH"
security set-key-partition-list -S apple-tool:,apple: -k "$KEYCHAIN_PASSWORD" "$KEYCHAIN_PATH"
security list-keychain -d user -s "$KEYCHAIN_PATH"
