# Installed automatically by install.sh. Ordinary Codex stays on its update path.
if [[ ${KEEPER_SHELL_ACTIVE-} == 1 ]]; then return 0; fi
if declare -F codex >/dev/null || alias codex >/dev/null 2>&1; then
    printf '%s\n' 'Keeper: an existing codex function or alias prevents terminal integration.' >&2
    return 2
fi
KEEPER_LAUNCHER="$(cd -- "${BASH_SOURCE[0]%/*}" && pwd)/launcher.py"
KEEPER_SHELL_ACTIVE=1
codex() {
    case "${1-}" in
        --keeper|--keeper-side|--keeper-top)
            KEEPER_PLUGIN_ROOT="${KEEPER_LAUNCHER%/scripts/launcher.py}" python3 -B "$KEEPER_LAUNCHER" "$@"
            ;;
        *) command codex "$@" ;;
    esac
}
