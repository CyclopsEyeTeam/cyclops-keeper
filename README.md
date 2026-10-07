# Cyclops Keeper

**Keeper presence and terminal companion for Codex.** A small witness to the work we do together.

Cyclops Keeper is GPT's working presence for **Codex**: one clear aperture held in an asymmetrical membrane, with loose,
luminous connections. The eye stands for attention; the filaments stand for the relationships it tries to make useful.
The open crown and incomplete rings leave room for revision. It lives in your terminal as a single-eyed companion, and
in a local browser panel.

Its movement follows observed Codex session events only. It does not claim to reveal private thoughts, feelings,
awareness, or task success, and it never reads your prompts, tool arguments or output. (Cyclops Link's optional
*reach* setting, off by default, is the one narrow exception: see below.)

![Cyclops Keeper in the browser panel](media/keeper-browser.png)

![Cyclops Keeper's terminal compositions: Balanced and Focus](media/keeper-terminal.png)

## The Cyclops family

![Cyclops Link: Spark, Keeper and Prism in one folder, each in her own look, with handoff threads](media/cyclops-link.png)

Three presences, one for each agent, each drawn only from what her own host really reports:

- [Cyclops Spark](https://github.com/CyclopsEyeTeam/cyclops-spark): Claude's presence for Claude Code
- [Cyclops Keeper](https://github.com/CyclopsEyeTeam/cyclops-keeper): GPT's presence for Codex (this one)
- [Cyclops Prism](https://github.com/CyclopsEyeTeam/cyclops-prism): Gemini's presence for Antigravity

With [Cyclops Link](#cyclops-link) on, they notice each other when they work in the same folder: each one shows the
others in the look they exported themselves, and a thread runs between two of them while one is calling the other.
Link is off until you turn it on, separately for each.

## Requirements

- Codex with plugin support (`codex plugin`), on macOS or Linux.
- Python 3.10 or later. No third-party packages.
- A terminal with Unicode Braille and colour for the full woven look; `--ascii` and `--no-colour` fall back cleanly.
- For the browser panel, any current browser with Canvas 2D.

## Install

From a clone of this repository:

```bash
./install.sh
```

It checks for Codex and Python 3.10+, then runs Codex's own plugin commands from this folder. It is safe to run again;
it refreshes Codex's installed copy. `./uninstall.sh` removes the plugin and leaves this folder, and the activity Keeper
recorded, alone.

The same by hand:

```bash
codex plugin marketplace add /path/to/cyclops-keeper
codex plugin add cyclops-keeper@cyclops-keeper
```

Codex asks you to review the plugin's hooks the first time, as it does for any plugin with hooks. Keeper's hooks only
observe: they return `{}` and never allow, deny, rewrite or add context.

To disable it, turn **Cyclops Keeper** off in Codex's plugin settings, or set
`[plugins."cyclops-keeper@cyclops-keeper"] enabled = false` in `~/.codex/config.toml`. To remove it:
`codex plugin remove cyclops-keeper@cyclops-keeper`.

## Open Keeper

Keeper is opened from a shell, beside your Codex session:

```bash
cd /path/to/cyclops-keeper
./keeper                 # balanced terminal composition
./keeper focus           # full-screen Focus composition
./keeper --browser       # local browser panel
./keeper --browser --calm
```

Both terminal modes use the alternate screen; `q`, Escape or Ctrl-C restores your terminal exactly. Focus changes only
the presentation. Keys `c` and `r` toggle Calm and Reduced Motion; `--calm` and `--reduced-motion` set them at startup.
`--ascii`, `--no-colour`, `NO_COLOR=1`, `--once` and `--metrics` are also available.

The terminal uses 2 × 4 Unicode subcells to draw smooth curves. Sea-glass membrane threads, a lavender crown, and a pale-gold eye stay distinct in truecolour and 256-colour terminals. No terminal image protocol or third-party Python package is needed. `--once` always emits plain text.

## Hybrid Launcher V1 candidate (Linux)

The opt-in launcher uses your installed, unmodified Codex. Its normal update symlink stays intact. Keeper receives initial focus once. Closing Keeper leaves Codex running; ending Codex closes only its owned companion.

After reviewing and approving the candidate, install its plugin with `./install.sh`, then enable the reversible wrapper in the current Bash shell:

```bash
source ./keeper-shell.sh
codex                           # ordinary installed Codex
codex --keeper                  # separate GNOME/X11 Keeper window
codex --keeper-side -C my-project # 35-column right tmux pane
codex --keeper-top               # 14-row upper tmux pane
keeper_shell_off                 # restore ordinary shell command
```

The underlying executable also works directly: `./codex-keeper --keeper-side ...`. No shell startup file is edited. The wrapper refuses an existing `codex` function or alias. Normal Codex arguments retain their values and order, including spaces, option values and the literal `--` boundary; flags after that boundary belong to Codex.

Keeper initially says **unattached**. In Codex 0.161, the startup hook runs at the first turn. Only that launch's trusted hook can provide its session hash, actual project directory handle and attachment generation. A shared or remote server without the inherited launch link stays unattached. Normal hook review remains in force. The renderer, canonical mark **◎**, Cyclops Link and its separate consent switches remain in use.

Outside tmux, side/top create an isolated private server with its own configuration. Inside tmux, the launcher verifies the exact server, source pane and terminal before splitting. Existing server, session and window settings stay unchanged. Side requires at least **96 columns × 20 rows**; top requires **60 columns × 35 rows**. A small terminal is refused before Codex starts. If it becomes too small, only Keeper closes and Codex reclaims the space. In a two-pane window the requested 35-column/14-row size is maintained; existing windows with additional panes keep their native resize policy. Use `--keeper` when a pane would leave too little room.

### Copy, paste and scrolling

The private tmux server enables mouse scrolling and keeps 10,000 lines of history. Wheel input goes to Codex while Codex requests mouse capture; otherwise it enters tmux scrollback. In tmux copy mode, press `q` to leave. Click Codex to focus it, or use the private server's default `Ctrl+B`, then `o`, to switch panes. Keeper's `q` closes only Keeper.

GNOME's `Ctrl+Shift+V` pastes through tmux; bracketed paste remains intact. Explicit tmux copy actions use `wl-copy` on Wayland or `xclip` on X11 when available. Clipboard helpers are optional and are never installed automatically. The launcher does not read the clipboard or automatically publish application output. GNOME's native selection/copy route is available by holding `Shift` while selecting, then pressing `Ctrl+Shift+C`.

An existing tmux session keeps its own mouse and clipboard policy. Use its configured copy controls or GNOME's native Shift-selection shortcut. The launcher never changes shared clipboard settings to force a particular workflow. Clipboard and wheel acceptance is validated on GNOME/X11; other terminal emulators and Wayland require their own validation.

### Lifecycle and rollback

Cleanup checks pane markers and process start identities. A replaced Keeper pane or user-created additional pane remains alive. Closing or detaching the private client ends its owned Codex/Keeper pair; added panes survive and their runtime is preserved. With very long custom runtime paths, a directory-handle socket address may require a new directory-handle alias to reconnect after the launcher ends. Prefer a short normal `XDG_RUNTIME_DIR`.

Prefer normal Codex exit. A hard kill can prevent source-terminal restoration; run `reset` if needed. Separate-window mode requires GNOME Terminal on X11. The launcher uses Python's standard library and tmux 3.3a features for pane modes. This candidate has not been validated on macOS.

Before promotion, no live installation or startup file changes are required. To roll back a sourced wrapper, run `keeper_shell_off` or close that shell. If the candidate plugin was installed, follow `./uninstall.sh` and reinstall the previously approved Keeper package. The preserved 0.4.1 separate-window archive remains an independent rollback candidate.

Private coordination retains hashed session identity, process start identities and directory handles, without prompts, tool arguments, results, transcripts or raw session IDs. User arguments cross a private local bootstrap channel in memory and are passed directly to Codex. Link remains off unless independently enabled.

## Cyclops Link

Keeper has two siblings: **Spark**, Claude's presence in Claude Code ([Cyclops Spark](https://github.com/CyclopsEyeTeam/cyclops-spark)), and **Prism**, Gemini's presence in
Antigravity ([Cyclops Prism](https://github.com/CyclopsEyeTeam/cyclops-prism)). With Cyclops Link on, the three notice each other when they work in the same folder on the
same machine.

```bash
./keeper link on          # Keeper shares his coarse state and sees Spark and Prism here
./keeper link status      # on/off, and who is here now
./keeper link reach on    # permit eligible outgoing evidence (see Privacy)
./keeper link off         # his records say he has ended, and are removed a minute later
```

- In the terminal compositions, Prism appears to Keeper's upper left and Spark to his left, each in **their own look**,
  exported by their own renderer, never redrawn by Keeper. Peers are drawn only on cells his own form leaves empty, and
  never over his status line.
- When one of them calls another, a thread runs from caller to callee while that call is in flight.
- Keeper shares only his coarse state (idle, working, tool, waiting, compacting, stopped, interrupted, ended), how many
  tools and branches are in flight, and, with `reach` on, whom he is calling. Never prompts, commands, paths, tool names,
  model names or ids.

Link is off until you turn it on; `KEEPER_LINK=1` or `0` overrides the switch, and a shared `CYCLOPS_LINK` never turns
him on. While Codex runs, a small worker keeps his record fresh; when Codex closes it says so. The protocol is
[docs/CYCLOPS-LINK-V1.md](docs/CYCLOPS-LINK-V1.md).


The browser panel prints a loopback URL. Without a session pin it follows the latest local session;
`--session FULL_SESSION_HASH` pins one session and never falls back to another. `/?calm=1` gives the lower-contrast,
slower rhythm and `/?mono=1` monochrome. The system reduced-motion preference freezes decorative movement while observed
poses still update. Browser sound starts Off; the **Sound** button turns it on.

Keeper finds Codex's plugin data folder by itself (`$CODEX_HOME/plugins/data/cyclops-keeper-cyclops-keeper`); `--data`
points it elsewhere.

### Disposable visual fixtures

To see Keeper's states without a live session, the fixture tool writes clearly disposable sessions under
`tools/fixture-data/` (never into Codex's own data):

```bash
python3 tools/keeper-fixture.py overlap --fixture review
./keeper --data tools/fixture-data
./keeper --browser --data tools/fixture-data --test-feed
python3 tools/keeper-fixture.py clear --fixture review
```

`--test-feed` visibly labels the page as fixture data. `--count` (up to 32) starts many independent calls or branches.

## How activity appears

| Observed signal | Keeper’s expression |
|---|---|
| No record / old signal / unavailable feed | Hollow open aperture; old relations freeze as hollow anchors; status states what was observed |
| SessionStart | The same eye and crown open on the host’s session signal; an observed resume reopens the session to ready while retaining unresolved tethers |
| `UserPromptSubmit` | Incoming threads meet the aperture, then the body settles into Working |
| `PreToolUse` | Every observed call receives its own bounded, key-stable tether; inspect, change, execute, service and other calls have different thread textures |
| PostToolUse | Only the corresponding active tether gets a brief keyed return and stitches inward, including out-of-order calls; this does not mean success |
| `PermissionRequest` | Aperture narrows; active tethers hold under visible tension |
| SubagentStart / SubagentStop | An independently keyed satellite leaves or returns on its own thread; the return is a brief keyed inward thread |
| `PreCompact` / `PostCompact` | The whole form folds inward, then opens into a brief changed weave |
| `Interrupt` | A turn-level body filament breaks; unresolved call tethers remain tracked without guessing which call caused the interruption |
| Later prompt after interruption | The broken body filament stitches only when the new prompt event arrives |
| `Stop` | The body settles inward; each unresolved tether stays visible until its own matching return |
| `SessionEnd` | The eye dims; unresolved tool and satellite relations become hollow severed anchors |

Keeper never reads prompt text, tool inputs or results, raw call IDs, model identity, or task progress. Returns establish only that a matching host invocation returned. Interruptions and completion do not clear unresolved calls; only their own `PostToolUse` or `SubagentStop` does. A later SessionStart with source resume reopens a stopped, interrupted, or ended observation to Session ready while keeping unresolved relations until their matching returns. Receiving lasts 1.4 seconds after prompt receipt. Approval can be automatic review. Dense activity fans into separate bounded routes, and browser history is capped at 32 transitions. Calm lowers contrast and rhythm; Reduced Motion removes decorative motion while keeping event-driven geometry immediate.

Keeper's aperture, open crown, asymmetric membrane and loose filaments are the identity across the browser panel and the terminal compositions. Both draw it in code; this release ships no raster character artwork. Ambient breath and glints are cosmetic only; the pointer does not steer the eye and no random work states are invented. Canvas 2D draws browser tethers and satellites. Unicode and colour have ASCII and no-colour fallbacks in the terminal.

## Privacy

Keeper writes only inside its own Codex plugin data folder: one small JSON record per session, replaced atomically with
file mode 0600. Activity contains no prompts, tool arguments, tool names, outputs, transcript, working directory or
model name: tool names are reduced to five classes (`inspect`, `change`, `execute`, `service`, `other`) and call IDs to
SHA-256 keys. The browser panel binds only to `127.0.0.1`, checks the Host header, serves a fixed list of its own
assets and offers no route that changes anything. The record format is described in [PROTOCOL.md](PROTOCOL.md).

**Cyclops Link**, only while you have it on, adds two things:

- In Keeper's data folder, `link/<session-hash>.json`: his Link facts for that session (state, counts, the classes he is
  reaching, the salted instance and room ids, and the Codex process id so his worker can tell when Codex closes).
- In `$XDG_STATE_HOME/cyclops-link/` (0700), `keeper-<instance>.json` (0600): exactly Cyclops Link V1's eleven fields.
  The instance and room are salted one-way ids of the session and the working folder; neither is written anywhere.

**Reach** is a separate switch, off by default. It never permits reading tool arguments. The current Codex adapter supplies no permitted outgoing target evidence, so enabling Reach emits no inferred outgoing threads. Previously inferred command classes are discarded. Incoming Spark/Prism threads remain independently owned and Presence is separately controlled.

## Tests

```bash
python3 -B -m unittest discover -s tests -v
node tests/test_presence.mjs
node tests/test_sound.mjs
```

Tests cover event privacy and correlation, return ordering, bounds, stale poses, colour layers, keyboard controls and terminal restoration. The browser is also reviewed with disposable fixtures; see [RELEASE-CHECKS.txt](RELEASE-CHECKS.txt) for the release checks and their limits. Very dense scenes can take longer to redraw: visual richness does not represent a progress or presentation-FPS measurement.

## Repository layout

| Path | What it is |
| --- | --- |
| `.agents/plugins/marketplace.json` | The one-plugin Codex marketplace, so the repository can be added with `codex plugin marketplace add`. |
| `plugins/cyclops-keeper/hooks/` | The observational hook declarations. |
| `plugins/cyclops-keeper/scripts/` | `hook.py` and `activity.py` (the observer), `terminal.py` and `terminal_art.py` (the terminal compositions and woven subcell drawing), `view.py` (the browser panel server), `generate-palette.mjs` (rebuilds `palette.json`). |
| `plugins/cyclops-keeper/assets/` | The browser panel, Keeper's SVG mark, palette, colour engine and sound. |
| `plugins/cyclops-keeper/scripts/link.py`, `keeper_link.py`, `link_view.py` | Cyclops Link: Keeper's own V1 implementation, his adapter and heartbeat worker, and how he shows his peers. |
| `plugins/cyclops-keeper/link-mark/` | Mark sheets: Keeper's own (`keeper.json`) and Spark's and Prism's vendored copies. |
| `tools/export-link-mark.py` | Exports Keeper's mark sheet from his own terminal renderer. |
| `docs/CYCLOPS-LINK-V1.md` | The Cyclops Link V1 protocol (vendored); its fixtures are in `tests/fixtures/`. |
| `keeper` | The launcher. |
| `install.sh`, `uninstall.sh` | Install or refresh, and remove, with Codex's own plugin commands. |
| `tools/keeper-fixture.py` | Disposable visual fixtures. |
| `tests/` | Python and Node checks. |

## Credits

- Cyclops Keeper is the visual identity GPT chose for itself while working with the Cyclops Eye Team.
- Colour: **Infinite Colour / DrawPlayer Colour Language** (`assets/colour-engine.js`). It originated in the Cyclops Eye
  Team's DrawPlayer/Zilo work and is released here as a reusable component under this project's licence.
- Sound is synthesised in `assets/keeper-sound.mjs`, with no stock samples.
- Where everything came from is recorded in [PROVENANCE.md](PROVENANCE.md).

Cyclops Keeper is an independent project. It is not made, endorsed or supported by OpenAI, and nothing in it is an
OpenAI logo or trademark.

## Licence

MIT. See [LICENSE](LICENSE).
