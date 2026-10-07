# Changelog

## 0.4.2 Hybrid Launcher V1 candidate

- Preserve the GNOME/X11 separate-window route and add owned tmux side/top layouts.
- Keep Codex installed and unmodified, with exact argument forwarding and verified hook attachment.
- Add private mouse history and explicit clipboard copying; respect existing tmux configuration.
- Preserve unrelated panes, initial focus, independent shutdown and terminal restoration.
- Tighten Reach: tool arguments are never read; outgoing threads require permitted evidence.

## 0.4.1 launcher candidate

- Add a reversible Bash wrapper and separate GNOME/X11 launcher for the three Keeper flags.
- Pin Keeper through its trusted host hook and a private per-launch handshake, with no latest-session fallback.
- Keep Codex unmodified, existing Link consent intact, and panel shutdown independent.


## 0.4.0

- **Cyclops Link** (off until `./keeper link on`): Keeper, Spark and Prism notice each other when they work in the same
  folder. Spark and Prism appear in Keeper's terminal at their seats (left, upper left), each in their own exported
  look, with a thread while one calls another. Keeper shares only his coarse state and counts; a heartbeat worker keeps
  that fresh while Codex runs and says so when Codex closes.
- `./keeper link reach on`, a second, separate switch: only then does Keeper tell the others when a shell call of his runs
  `claude`, `agy` or `gemini`, keeping the class and nothing of the command.
- Keeper's own Link mark sheet (`link-mark/keeper.json`) and text mark `◎`, exported by his own renderer.

## 0.3.2

- `install.sh` and `uninstall.sh`: one-step install, refresh and removal with Codex's own plugin commands.

## 0.3.1

- A woven Unicode terminal identity: smooth subcell curves, sea-glass membrane, lavender crown and a pale-gold aperture, with layered truecolour or 256-colour output.
- Matching woven browser form, with event gestures aligned to their tethers.
- Stale observations freeze in both terminal fallbacks; missing evidence keeps a hollow aperture, including the tiny browser view.
- Independently routed calls, matching late returns after session end, and a visibly severed body filament on interruption.
- Fix the stopped-turn browser crash, tiny-view relations and the launcher executable permission.
- Refreshed fixture previews and focused terminal regression checks.

## 0.3.0 (first public release)

- Cyclops Keeper as a standalone Codex plugin: the observational hooks, the single-eyed terminal companion (Balanced and
  Focus) and the local browser panel.
- Installs with Codex's own `codex plugin marketplace add` / `codex plugin add`; finds its data folder by itself.
- Writes only inside its own Codex plugin data folder.
- The browser panel draws Keeper's body in code. The private project's raster artwork is not included.
- MIT licence.

Keeper was developed privately (0.1 as "Weave", 0.2 as Cyclops Keeper) before this release.
