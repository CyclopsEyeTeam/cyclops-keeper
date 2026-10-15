#!/usr/bin/env bash
# Remove Cyclops Keeper from Codex. This folder, and the activity Keeper recorded, are left alone.
set -euo pipefail

plugin="cyclops-keeper@cyclops-keeper"
here="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 -B "$here/plugins/cyclops-keeper/scripts/shell_setup.py" remove
command -v codex >/dev/null 2>&1 || { printf 'Cyclops Keeper: Codex is not installed; nothing to remove.\n' >&2; exit 0; }

# Read complete structured replies: an early-exiting text filter can give
# Codex a broken pipe and falsely report absence under pipefail.
status_contains() {
  python3 -c '
import json, sys
field, identifier, wanted = sys.argv[1:]
value = json.load(sys.stdin)
if not isinstance(value, dict) or not isinstance(value.get(field), list):
    sys.exit("Cyclops Keeper: unexpected Codex status; removal stopped.")
rows = value[field]
if any(not isinstance(row, dict) or not isinstance(row.get(identifier), str)
       or not row[identifier] for row in rows):
    sys.exit("Cyclops Keeper: unexpected Codex status; removal stopped.")
print("yes" if any(row[identifier] == wanted for row in rows) else "no")
' "$@"
}
installed_plugins="$(codex plugin list --json)"
has_plugin="$(status_contains installed pluginId "$plugin" <<< "$installed_plugins")"
if [[ "$has_plugin" == yes ]]; then
  codex plugin remove "$plugin" >/dev/null 2>&1
  printf '  plugin: removed\n'
else
  printf '  plugin: not installed\n'
fi
registered_markets="$(codex plugin marketplace list --json)"
has_market="$(status_contains marketplaces name cyclops-keeper <<< "$registered_markets")"
if [[ "$has_market" == yes ]]; then
  codex plugin marketplace remove cyclops-keeper >/dev/null 2>&1
  printf '  marketplace: removed\n'
fi
printf 'Cyclops Keeper is uninstalled. Open a new Bash terminal. Your activity data and this folder were preserved.\n'
