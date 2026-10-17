# Changelog

## Unreleased

## 0.6.2 — Single installed version · 17 October 2026

- Retain old-session hook files without their plugin manifests after a successful upgrade, preventing old caches from being rediscovered as installed versions. Failed upgrades retain the original installation metadata.

## 0.6.1 — Reactive lower canvas · 17 October 2026

- Restore the event-reactive lower drawing while work is active, with the saved painting above. Return to the authored sketch or saved outline when work settles; preserve quiet-mode and stale-signal restraint.

## 0.6.0 — Painting, expression and side chat · 17 October 2026

- Preserve previous version caches after plugin refresh, including failed installs, so existing sessions retain their hook files. Keep rollback copies outside the replaced cache.

- Add a separate painting Chat panel with follow-up history, background replies, cancellation and actual token usage. Support Studio’s dedicated Keeper question mailbox without reading the work conversation or writing chat into painting files. Studio UI support is maintained separately.

- Publish an optional privacy-filtered live/durable activity feed for Studio-owned sessions. Keep terminal activity authoritative, exact tool correlations, bounded history and producer-bound heartbeats; ordinary sessions publish no feed. This does not clear the historical resource HOLD.

- Replace the default text constellation with a compact woven-light crest and an eight-second travelling bead. Preserve custom crests, ASCII rendering and quiet-mode freezing; artwork choices remain independent.


- Remove live canvas headings and idle toolbar spacer rows; combine activity wording with attachment status and reserve a larger sketch area. Fresh sessions get a read-only outline of the latest saved Keeper painting until an authored sketch arrives.
- Add attachment-bound Free/Work-inspired painting choice and `painting_brief` MCP. This guides explicit assistant composition; it does not invoke a model automatically.
- Truest quantizes after resizing, before captions. Raster-backed SVG uses an sRGB discrete filter on its painting group and native caption text outside. Levels: 6, 8, 16 (default), 32, 64 or 256 (off). No invented shadows or depth pass.


- Show a bounded reported token count beside a painting when supplied; omit unknown usage. Recurring-picture instructions now include short follow-ups and ask for composition early in the turn.
- Preserve a lower live draw box beside the saved painting layout, enlarge Keeper with the focus envelope, and replace the crest heading with a compact moving constellation. Fresh sessions use the latest saved painting as a line-art fallback until explicitly painted; quiet modes freeze the constellation.


- Grow the overhead painting toward pane width and add clickable terminal Story, Convert and Roll menus, keyboard alternatives, completion/progress bars and cancellation. Story reads all three painters with folder credit; background exports create unique PNG/raster-backed SVG galleries and MP4 rolls with painting-derived music. Small-pane resize preserves playback/jobs.

- Saved paintings now have an overhead terminal panel using Prism’s shared raster math in a separate worker; the live sketch remains below Keeper. Small panes preserve the original layout.
- Correct Keeper skill invocation (`$cyclops-keeper:keeper`), explicitly declare its skill directory, and document opt-in per-message/active-work painting for both surfaces.

- Add explicitly authored shared paintings, strict validation, exclusive atomic storage, read-only peer access and a yielding standalone preview. The 0.5.0 resource HOLD remains unchanged; the user reported Studio confirmation after local installation.

- Add a static constellation crest above Keeper in taller panes, with a launch-bound `crest` tool for a moon, ribbon or constellation and a short authored phrase; preserve the bottom canvas and observed status.

- Expand the authored drawing box to about 40% of pane height and nearly full width; add ellipses, rectangles, cubic curves, short labels and eight themed inks, with bounded geometry and cached static rendering.

- Default new terminal launches to Moonlight, with optional Ember, Moss, Terminal Green and Classic palettes through `KEEPER_THEME` or the direct renderer's `--theme` option.
- Add sparse working particles, observed-tool sparks, a waiting pulse and a short observed-Stop ripple; quiet controls and unavailable signals suppress the new effects.
- Preserve Classic library defaults and historical raster fixtures. Focused checks pass; these additions do not resolve the existing resource HOLD or establish physical visual acceptance.

- Add an event-gated illustration canvas below Keeper, with room for the latest observed event in tall terminal views and a compact mark in shorter views.
- Add Keeper-voiced captions for observed turn, tool, branch, permission, interruption, session and compaction events; the second row reports only bounded live relations and a short event trail.
- Keep captions whole in narrow views and keep quiet, stale and unknown observations free of invented activity.
- Preserve the original terminal body fixture, update the captioned render baseline, and add explicit coverage for missing event evidence and resize-safe caption layouts.
- Reuse a bounded raster layer for settled tool and branch tethers while Keeper’s body keeps moving; fresh observed arrival gestures bypass the cache.
- Run the complete current-source terminal resource matrix and record its CPU/repeatability HOLD alongside the focused cache improvement.
- Keep the main README and validation notes aligned with the current source and scoped performance evidence.

## 0.5.0 — Simple terminal presence

- One installation command: `./install.sh` installs both the plugin and terminal commands.
- Only `codex --keeper side`, `codex --keeper top`, and `codex --keeper` launch Keeper.
- Side and top stay inside the current terminal; bare `--keeper` requests a separate fullscreen GNOME/X11 terminal.
- Keep normal keyboard input with Codex when side/top opens, including user selection during startup.
- Retire the standalone launchers, selection menu, browser runtime, optional setup mode and old flag aliases.
- Retire Link broadcasting and peer overlays; preserve older consent files without acting on them.
- Uninstall also removes the managed Bash startup block; ordinary Codex uses its normal executable directly.
- Read complete structured Codex status during uninstall; unexpected schemas stop removal without a false success claim.
- Complete 200 ms decorative deadline scheduling with immediate public-state and ownership invalidation.
- Avoid continuous metrics collection during ordinary use; CPU metrics use the process CPU clock.
- Preserve the woven artwork, exact argument forwarding, launch attachment, terminal restoration and scoped pane ownership.
- The tagged archive is a frozen snapshot. This branch’s later expression changes are listed above; see `docs/VALIDATION.md` for source and release-snapshot evidence.

## Historical development

## Local 0.4.4 paced drawing experiment — 13 October 2026

- Includes Responsive Presence V1 and the existing observer delivery repair.
- Applies a 200 ms decorative body interval with immediate public-state, identity, size and preference invalidation; retains original animation phase and native input/feed polling.
- Owner stopped further tests and requested this local update. Final repeatability and visual acceptance remain unresolved; historical HOLD and negative evidence are preserved.


## 0.4.4 — Responsive Presence V1, isolated and unpromoted

- Geometry-based full, compact, miniature and living-eye forms.
- Codex-first side/top allocation, supervised suspension and stable return.
- Owner-fenced presentation preferences persist across recreation.
- Small attachment states/counts stay visible; peer artwork yields to Keeper in small/micro forms.
- Independent review corrections verified; final Python suite149/150 with the unchanged intermittent observer-concurrency failure.
- Promotion held for observer correctness and mixed resource measurements. No live installation or activation.

## 0.4.3 — Local usability update

- `codex --keeper top` and `codex --keeper side` select the existing owned tmux layouts; older flag spellings still work.
- `codex --keeper` requests a fullscreen separate GNOME/X11 Keeper window.
- `./install.sh --shell` explicitly installs a reversible Bash startup block for commands from any project folder.
- Packaged launch entry points, `keeper start` view selection and a read-only `keeper doctor` check.
- Setup guidance distinguishes installation, hook trust, recorded activity and launch attachment.
- No changes to observer event semantics, identity, Link/Reach or sound consent.

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
