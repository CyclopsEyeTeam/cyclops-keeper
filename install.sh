#!/usr/bin/env bash
# Install (or refresh) Cyclops Keeper for Codex from this folder.
# Install the hooks and the three terminal commands together.
set -euo pipefail

here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
plugin="cyclops-keeper@cyclops-keeper"
[[ $# == 0 ]] || { printf 'Usage: ./install.sh\n' >&2; exit 2; }

say() { printf '%s\n' "$*"; }
fail() { printf 'Cyclops Keeper: %s\n' "$*" >&2; exit 1; }

command -v codex >/dev/null 2>&1 || fail "Codex (the 'codex' command) is not installed or not on your PATH."
command -v python3 >/dev/null 2>&1 || fail "Python 3.10 or later is needed (no 'python3' command found)."
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || fail "Python 3.10 or later is needed (you have $(python3 -c 'import platform; print(platform.python_version())'))."
[[ "$(uname -s)" == Linux ]] || fail "This release supports Linux with Bash."
command -v tmux >/dev/null 2>&1 || fail "Install tmux for the side and top views, then run ./install.sh again."
command -v gnome-terminal >/dev/null 2>&1 || fail "Install GNOME Terminal for the separate fullscreen view, then run ./install.sh again."
python3 -B "$here/plugins/cyclops-keeper/scripts/shell_setup.py" check

say "Cyclops Keeper: installing from $here"
codex plugin marketplace add "$here" >/dev/null 2>&1 \
  || fail "Codex could not add this folder as a marketplace. Run 'codex plugin marketplace add \"$here\"' to see why."
say "  marketplace: ready"
# Adding again refreshes Codex's installed copy from this folder.
python3 -B "$here/install_cache.py" >/dev/null 2>&1 \
  || fail "Codex could not install the plugin. Run 'codex plugin add $plugin' to see why."
say "  plugin: installed"

python3 -B "$here/plugins/cyclops-keeper/scripts/shell_setup.py" install
say ""
say "Installed. Open a new Bash terminal, then use:"
say "  codex --keeper side    Keeper beside Codex in this terminal"
say "  codex --keeper top     Keeper above Codex in this terminal"
say "  codex --keeper         Keeper in a separate fullscreen terminal"
say "In Codex, open /hooks, review Keeper, then send your first message to attach."
