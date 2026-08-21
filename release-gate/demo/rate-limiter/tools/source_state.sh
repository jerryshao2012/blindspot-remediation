#!/bin/sh
# Print the demo's source state: git commit (if available) and a sha256 tree
# hash over the source files. Works from any working directory — evidence.md
# cites this script so the recorded hash is reproducible without ambiguity.
set -e
cd "$(dirname "$0")/.."
if git rev-parse --short HEAD >/dev/null 2>&1; then
  printf "commit: %s\n" "$(git rev-parse --short HEAD)"
else
  printf "commit: (no git)\n"
fi
# Editable installs create src/ratelimiter.egg-info. It is build output, not
# source, and must not make the reproducible source hash change after setup.
# Cover both the library and the Release Gate demo surfaces. Evidence output and
# generated workbench state are deliberately excluded.
tree_hash=$(find assets controls examples oracle src tests tools \
  .gitignore README.md demo.py pyproject.toml requirements-dev.txt spec.md \
  -type f -not -path "*__pycache__*" -not -path "*.egg-info*" \
  | sort | xargs shasum -a 256 | shasum -a 256 | cut -c1-16)
printf "tree:   %s\n" "$tree_hash"
