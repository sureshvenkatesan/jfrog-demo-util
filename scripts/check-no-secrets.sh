#!/usr/bin/env bash
# Quick check that no secrets appear in files that would be committed.
# Run before: git add && git commit
set -e
cd "$(dirname "$0")/.."
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repo, skipping."
  exit 0
fi
# Files that would be committed (tracked + not ignored)
FILES=$(git ls-files)
if [ -z "$FILES" ]; then
  echo "No tracked files yet."
  exit 0
fi
# JWT-like pattern (eyJ...)
if echo "$FILES" | xargs grep -l 'eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*' 2>/dev/null; then
  echo "ERROR: Possible JWT/secret found in tracked file(s) above."
  exit 1
fi
# config.yaml must not be tracked
if echo "$FILES" | grep -q '^config\.yaml$'; then
  echo "ERROR: config.yaml is tracked. Run: git rm --cached config.yaml"
  exit 1
fi
echo "OK: No obvious secrets in tracked files."
