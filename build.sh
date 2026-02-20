#!/usr/bin/env bash
# Build poc-util wheel. The wheel includes dependency metadata (Requires-Dist) so
# pip install dist/poc_util-*.whl will install the package and its dependencies.
# Also adds dist/resources.zip and dist/config.yaml.example.
# Optionally uploads dist/* to Artifactory (jf CLI) using config.yaml sync.source_server_id.
# Set BUILD_UPLOAD=0 to skip upload. Set ARTIFACTORY_REPO to override repo (default: alexsh-pypi-local).
set -e
cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"
[ -d ".venv" ] && PYTHON=".venv/bin/python"
BUILD_UPLOAD="${BUILD_UPLOAD:-1}"
ARTIFACTORY_REPO="${ARTIFACTORY_REPO:-alexsh-pypi-local}"

if command -v hatch >/dev/null 2>&1; then
  hatch build
else
  "$PYTHON" -m pip install --quiet hatch
  "$PYTHON" -m hatch build
fi

# Add resources zip and example config to dist/
if [ -d resources ]; then
  zip -rq dist/resources.zip resources -x "*.DS_Store"
fi
cp config.yaml.example dist/
echo "dist/: poc_util-*.whl, poc_util-*.tar.gz, resources.zip, config.yaml.example"

# Upload dist/ to Artifactory via jf CLI (same routing as sync upload: server-id from config)
if [ "$BUILD_UPLOAD" = "1" ] && command -v jf >/dev/null 2>&1 && [ -f config.yaml ]; then
  SERVER_ID=$("$PYTHON" -c "
import yaml
try:
    with open('config.yaml') as f:
        c = yaml.safe_load(f)
    print(c.get('sync', {}).get('source_server_id', '') or '')
except Exception:
    print('')
")
  if [ -n "$SERVER_ID" ]; then
    echo "Uploading dist/ to $ARTIFACTORY_REPO (server-id=$SERVER_ID)..."
    jf rt u "dist/*" "$ARTIFACTORY_REPO/" --server-id="$SERVER_ID"
    echo "Upload done."
  else
    echo "Skipping upload: config.yaml sync.source_server_id not set."
  fi
elif [ "$BUILD_UPLOAD" = "1" ] && ! command -v jf >/dev/null 2>&1; then
  echo "Skipping upload: jf CLI not on PATH."
fi
