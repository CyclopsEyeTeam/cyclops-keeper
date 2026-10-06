#!/usr/bin/env bash
# Install (or refresh) Cyclops Keeper for Codex from this folder.
# It only runs Codex's own plugin commands; nothing in your settings is edited by hand.
set -euo pipefail

here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
plugin="cyclops-keeper@cyclops-keeper"

say() { printf '%s\n' "$*"; }
fail() { printf 'Cyclops Keeper: %s\n' "$*" >&2; exit 1; }

command -v codex >/dev/null 2>&1 || fail "Codex (the 'codex' command) is not installed or not on your PATH."
command -v python3 >/dev/null 2>&1 || fail "Python 3.10 or later is needed (no 'python3' command found)."
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || fail "Python 3.10 or later is needed (you have $(python3 -c 'import platform; print(platform.python_version())'))."

say "Cyclops Keeper: installing from $here"
codex plugin marketplace add "$here" >/dev/null 2>&1 \
  || fail "Codex could not add this folder as a marketplace. Run 'codex plugin marketplace add \"$here\"' to see why."
say "  marketplace: ready"
# Adding again refreshes Codex's installed copy from this folder.
codex plugin add "$plugin" >/dev/null 2>&1 \
  || fail "Codex could not install the plugin. Run 'codex plugin add $plugin' to see why."
say "  plugin: installed"

say ""
say "Done. Start Codex; the first time, it asks you to review Keeper's hooks (they only observe)."
say "Then, from this folder:  ./keeper   (terminal companion)   or   ./keeper --browser"
