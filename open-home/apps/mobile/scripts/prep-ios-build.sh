#!/usr/bin/env bash
#
# Prepare a fresh checkout for an iOS build.
#
# credentials.json and creds/profile.mobileprovision are deliberately NOT in
# git — they reference a distribution certificate, and a provisioning profile
# is machine-specific anyway. So every new clone needs them minted once. This
# script is that step, so nobody has to rediscover it.
#
# It reuses the SHARED Apple Distribution certificate in ~/.openclaw/ios-creds
# (Apple's model: one dist cert, many provisioning profiles) and mints a fresh
# profile for this bundle id.
#
#   ./scripts/prep-ios-build.sh
#   npx eas-cli build --platform ios --profile production
#
set -euo pipefail
cd "$(dirname "$0")/.."

STORE="${IOS_CREDS_STORE:-$HOME/.openclaw/ios-creds}"
BUNDLE="$(python3 -c "import json;print(json.load(open('app.json'))['expo']['ios']['bundleIdentifier'])")"
NAME="$(python3 -c "import json;print(json.load(open('app.json'))['expo']['name'])")"

if [ ! -d "$STORE" ]; then
  echo "No signing store at $STORE" >&2
  echo "It is mirrored from the droplet: root@146.190.214.134:/root/.openclaw/ios-creds" >&2
  echo "It is signing material and lives outside any git repository on purpose." >&2
  exit 1
fi

MAKER="${ASC_TOOLS:-$HOME/.openclaw/asc-tools}/make_ios_creds.py"
[ -f "$MAKER" ] || { echo "make_ios_creds.py not found at $MAKER" >&2; exit 1; }

echo "bundle: $BUNDLE"
echo "name:   $NAME"
echo "store:  $STORE"

# The tooling reads the ASC key from here rather than hardcoding a path, so the
# same command works on this Mac and on the droplet.
export ASC_KEY_PATH="${ASC_KEY_PATH:-$STORE/asc-api-key.p8}"

python3 "$MAKER" "$BUNDLE" "$NAME" "$(pwd)"

# Fail loudly rather than letting the build discover it later.
for f in credentials.json creds/profile.mobileprovision; do
  [ -s "$f" ] || { echo "expected $f to exist and be non-empty" >&2; exit 1; }
done

echo
echo "ready. credentials.json and creds/ are gitignored — do not commit them."
echo "next: npx eas-cli build --platform ios --profile production"
