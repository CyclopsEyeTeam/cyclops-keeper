# Bash: source this file to add Keeper flags; no startup file is edited.
# Refuse conflicting shell state so removal really restores ordinary Codex.
if [[ ${KEEPER_SHELL_ACTIVE-} == 1 ]]; then return 0; fi
if declare -F codex >/dev/null || alias codex >/dev/null 2>&1 || [[ ${KEEPER_LAUNCHER+x} ]]; then
  printf '%s\n' 'Keeper: existing codex shell customisation detected; use the separate codex-keeper launcher.' >&2
  return 2
fi
export KEEPER_LAUNCHER="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/codex-keeper"
KEEPER_SHELL_ACTIVE=1
codex() { "$KEEPER_LAUNCHER" "$@"; }
keeper_shell_off() { unset -f codex keeper_shell_off; unset KEEPER_LAUNCHER KEEPER_SHELL_ACTIVE; }
