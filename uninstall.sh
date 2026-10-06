#!/usr/bin/env bash
# Remove Cyclops Keeper from Codex. This folder, and the activity Keeper recorded, are left alone.
set -euo pipefail

plugin="cyclops-keeper@cyclops-keeper"
command -v codex >/dev/null 2>&1 || { printf 'Cyclops Keeper: Codex is not installed; nothing to remove.\n' >&2; exit 0; }

if codex plugin list 2>/dev/null | grep -q "^$plugin"; then
  codex plugin remove "$plugin" >/dev/null 2>&1
  printf '  plugin: removed\n'
else
  printf '  plugin: not installed\n'
fi
if codex plugin marketplace list 2>/dev/null | grep -q '^cyclops-keeper'; then
  codex plugin marketplace remove cyclops-keeper >/dev/null 2>&1
  printf '  marketplace: removed\n'
fi
printf 'Cyclops Keeper is uninstalled. This folder was not touched; delete it yourself if you like.\n'
