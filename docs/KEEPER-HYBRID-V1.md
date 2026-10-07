# Keeper Hybrid Launcher V1 — validated public candidate 0.4.2

Validated on Linux, GNOME/X11, tmux 3.3a and installed unmodified Codex 0.161.0. Codex source was neither modified nor rebuilt. The earlier native build investigation is retired from this design; its findings and original 0.4.1 candidate remain preserved separately.

## Commands

After installing this plugin with `./install.sh`, source `./keeper-shell.sh` in the current Bash shell.

| Command | Result |
| --- | --- |
| `codex` | Ordinary installed Codex, resolving its normal launcher each time. |
| `codex --keeper` | Existing GNOME/X11 separate window. |
| `codex --keeper-side` | Right-hand 35-column tmux pane. |
| `codex --keeper-top` | Upper 14-row tmux pane. |
| `keeper_shell_off` | Remove this shell's reversible wrapper. |

The underlying `./codex-keeper` executable accepts the same flags. Normal arguments retain their order and bytes, including option values, spaces, Unicode, shell metacharacters and literal `--` boundaries. No shell startup file or Codex update mechanism is changed.

## Implementation and attachment

The GNOME launcher body is byte-identical to 0.4.1. A separate standard-library Python adapter owns tmux layout and lifecycle. Outside tmux, it creates a private server. Inside tmux, it verifies the socket owner, server process start, launching pane and actual terminal before changing any pane. Existing global/session/window settings and unrelated panes stay intact. Only its newly owned pane gets a marker and a pane-local shutdown setting.

The existing private launch handshake supplies a verified session hash, actual project directory handle and attachment generation. Shared folders or recent activity are never treated as session identity. Keeper stays unattached until the trusted host hook runs; Codex 0.161 queues SessionStart until the first turn. Shared/remote hosts without the inherited handshake remain unattached.

Keeper receives one ready-gated focus request. Closing Keeper leaves Codex alive. Codex exit closes only its owned companion. Exact process start identities and pane markers guard cleanup. Replaced panes and user-created additional panes survive; the private runtime is retained if additional panes remain. No cleanup trap depends on an `exec` replacement.

Twenty-six protected baseline files remain byte-identical, including renderer, sound, identity exports, trusted attachment helpers, window implementation, hook declarations and protocol fixtures. Keeper's canonical mark remains **◎**.

## Clipboard and scroll acceptance

Both side and top passed actual GNOME/X11 input tests on an isolated Xvfb display with a private bus/profile. These tests did not read or change the desktop clipboard.

- Mouse-wheel input entered tmux history for a host without mouse capture, without injecting arrow keys or escape input into its prompt.
- Explicit tmux copy actions reached the isolated system clipboard through xclip.
- Native Shift-selection and **Ctrl+Shift+C** copied actual terminal text.
- **Ctrl+Shift+V** delivered intact bracketed paste, without a prompt-submit carriage return.
- Both host and Keeper stayed responsive.

Additional installed-Codex GUI checks passed in both layouts: Ctrl+Shift+V made the test text visible without submitting a turn; wheel-up/down left the composer intact while Codex requested mouse capture. This extra isolated GUI check explicitly used `--no-daemon` and the disposable local-hook bypass after the isolated background-server route reported a compatibility dialog. The earlier default-mode launch/session smoke passed. No daemon option is inserted by the launcher. No transcript scroll-distance claim is made.

Private servers enable mouse support and 10,000 history lines. Wheel handling belongs to Codex when it requests mouse capture; tmux history handles the remaining case. They use an available xclip/wl-copy backend only for explicit copies. Existing tmux sessions retain their own mouse/clipboard policy; their configured controls or native terminal Shift-selection apply. The launcher does not force shared mouse settings, so automatic wheel behavior there depends on the existing configuration.

## Validation evidence

- Preserved 0.4.1 baseline: 92 Python and 12 renderer/sound checks re-run before implementation.
- Final candidate: **112 Python checks passed**, including 20 added checks. Two legacy Reach assertions were revised for the stricter privacy boundary. **12 renderer/sound checks passed**.
- Final optional GUI tests: 2 passed after test portability adjustments.
- Actual tmux fixtures verified 35-column/14-row geometry, minimum-size refusal, resize recovery, independent inputs/focus, exact argv, large valid escaped argv, duplicate refusal and multiple same-project sessions without cross-attachment.
- Disposable fault tests verified split failure, outer/supervisor termination, early pre-bootstrap outer death, terminal restoration, foreign-pane survival and unchanged existing settings (including remain-on-exit).
- Installed Codex smoke passed all three layouts in a disposable CODEX_HOME. Real SessionStart, hashed session attachment, actual project handles, generation, one-time focus, Keeper-first closure and restored terminal were verified. Codex exited through its own terminal; its observed exit statuses were preserved, including 130 for Ctrl+C.
- The smoke used a closed loopback provider, copied no credentials and made no external model call. The vetted local hook trust bypass existed only in the disposable home; ordinary hook review is still required.
- Independent read-only review found no remaining material blockers after four regression-backed corrections: environment presence, foreign-runtime preservation, retained dead panes and bootstrap cleanup. It also checked the argument-boundary correction.

The tests establish local launcher/attachment behavior. They are not a production model-task, frame-rate, macOS, Wayland or other-terminal validation.

## Privacy

Presence remains independently controlled. Reach defaults off and never reads tool arguments. Previously inferred outgoing command classes are discarded. This Codex adapter currently supplies no permitted outgoing target evidence, so enabling Reach does not invent outgoing threads. Incoming Spark/Prism threads remain independently owned. No new observation permission is introduced.

## Resources and storage

A six-second side-layout fixture sample measured about **71.4 MiB resident memory** and **5.5% of one CPU** across the outer launcher, supervisor, renderer, tmux server and private client. It includes reaped helper CPU, excludes Codex execution, the compositor and unmeasured external helpers, and makes no FPS claim. Installed tmux on this host is an AppImage, so its invocation overhead is included where measured. No Rust build, bundled Codex or third-party Python runtime is required.

Development and disposable state stayed on the designated HDD. The run used about **98.4 MiB of readable data**, including the disposable Codex catalog/home. Three inaccessible stale external FUSE mount entries from failed fixtures were recorded separately; old harnesses were not retired. Xvfb's small /tmp X11 lock/socket files were the necessary local IPC exception. Only selected reports and source are promoted; the whole harness is not release evidence.

## Limits and rollback

Side needs 96×20 characters; top needs 60×35. Small terminals are refused before Codex starts. On excessive shrink, only Keeper closes and Codex recovers the space. A two-pane window keeps exact requested dimensions; existing windows with extra panes keep their native resize policy.

Separate-window mode requires GNOME/X11. Side/top require an interactive Linux terminal and tmux 3.3a features. Clipboard helpers are optional; native copy/paste controls remain available. Wayland, macOS, other emulators and shared/remote session inheritance need separate validation. With very long custom runtime paths, reconnecting surviving added panes after launcher exit can require a directory-handle socket alias. Normal short XDG_RUNTIME_DIR paths avoid that limitation. Hard kill can prevent source-terminal restoration; use `reset` if needed.

Run `keeper_shell_off`, or close the sourced shell, to restore ordinary command lookup. No permanent shell or Codex binary replacement exists. If reverting an installed plugin, run `./uninstall.sh` and reinstall the previously approved version. The original 0.4.1 archive and its evidence are preserved independently.

Recommendation: promote this as a Linux public candidate, with a short user pilot before wider terminal/platform support. GitHub source publication is authorized; local global activation remains a separate action.
