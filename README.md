# Cyclops Keeper

A small, single-eyed presence for the Codex terminal. Keeper’s woven membrane,
crown and trailing filaments respond to observed session activity.

The current `main` branch adds an event canvas and Keeper-voiced captions that
translate observed Codex events. Install instructions below use the current
`main` source; tagged archives are separate snapshots. The
[validation results](docs/VALIDATION.md) describe the checks and measured
limits for the current source.

![Keeper’s terminal expression](media/keeper-terminal.png)

## Install

```bash
git clone https://github.com/CyclopsEyeTeam/cyclops-keeper.git
cd cyclops-keeper
./install.sh
```

Open a new Bash terminal, go to your project, and use:

| Command | View |
| --- | --- |
| `codex --keeper side` | Keeper beside Codex, inside the current terminal |
| `codex --keeper top` | Keeper above Codex, inside the current terminal |
| `codex --keeper` | Codex here, with Keeper in a separate fullscreen terminal |
| `codex` | Ordinary Codex |

That is the complete launch interface. Put the Keeper prefix first; any Codex
arguments or prompt follow it, for example:

```bash
codex --keeper side -C "my project"
```

In Codex, open `/hooks`, review Keeper’s hooks, then send your first message.
Keeper stays **unattached** until a trusted hook identifies that exact launch.

Installation registers the plugin and one reversible block in `.bashrc`.
The commands use Codex’s installed executable and follow its normal updates.
Running `./install.sh` again refreshes Keeper. A checkout can be moved after
installation because the commands use Codex’s installed plugin copy.

## Authored captions and paintings

Keeper includes a small local MCP server named `keeper`, with `say`, `paint`,
and `clear` tools. After refreshing the plugin, start a new Keeper-enabled
Codex session so the host discovers the tools. Normal tool approval settings
still apply. An ordinary Codex session without a Keeper launch cannot publish.

Ask Codex to occasionally leave an original caption or small painting alongside
its work. The separate **Keeper / authored** space appears below the body when
there is room (at least 32 columns and 18 rows). It never replaces the observed
status. Captions last 5–120 seconds; paintings remain still until replaced,
cleared or the launch ends. Below the minimum size, content is retained but hidden.

The drawing box uses about 40% of the pane height (up to 24 rows), with nearly
the full width available. `paint` supports polylines, ellipses, rectangles and
cubic curves, plus six short labels. Use up to 32 strokes and 512 total points;
eight inks follow the active theme. See [drawing controls](docs/KEEPER-MCP-EXPRESSION.md).

Panes at least 32 columns wide and 28 rows tall also show a quiet constellation
crest above Keeper. The `crest` tool can replace it with a moon or ribbon and
an original phrase of up to 48 characters. This static decoration is separate
from observed activity and leaves the bottom drawing in place. `clear` removes
custom authored content and returns the top to its decorative constellation.

Authored content is an explicit creative message, not inferred emotion, private
reasoning or evidence of progress. Do not submit prompts, transcript excerpts,
paths, credentials or tool payloads. This opt-in tool content is stored separately
from the privacy-filtered activity feed, only in the private launch directory.

Subagent satellites remain driven exclusively by observed starts and matching
returns. The MCP tools cannot create agents, claim success or change work state.
The server sleeps on stdin; it does not run a background model. Painting rasters
are cached, and the view checks for changed artwork at most four times a second.

## Requirements

- Linux and Bash, with Codex plugin support.
- Python 3.10 or later; no Python packages to install.
- tmux for the two views inside your terminal.
- GNOME Terminal on an X11 desktop for the separate fullscreen view.

Existing direct `codex` aliases or functions must be removed before installing;
Keeper refuses to overwrite them. Indirect shell customisations are also refused
when a new terminal loads the integration.

The installer checks these tools and reports missing dependencies. It does not
install system packages. macOS, other shells and a Wayland fullscreen window
are outside this release’s supported setup.

Keeper adapts to the space available. If a pane becomes too small, Codex keeps
the room and Keeper returns when space settles. Returning never steals focus.
Colour and Unicode support are detected automatically; `NO_COLOR` is respected.

Side and top keep keyboard input with Codex. Press `q` in Keeper to close its
view. Codex continues running. Exiting Codex
closes only its own Keeper view. Other tmux panes and existing tmux settings
are preserved. Use your terminal’s normal copy and paste shortcuts; inside a
private tmux session, `Ctrl+B`, then `o`, switches focus between panes.

## What the expression means

Keeper translates observed events into short captions: a new turn turns the
aperture toward its line, a tool sends a thread outward and its matching return
brings that thread home, a branch opens at the side, and compaction gathers or
reopens the weave. Permission waits at a gate; interruption leaves a severed
filament. A stopped turn is not a claim of success. Missing or old evidence is
shown as unavailable.

Wide, tall views give the latest observed event its own canvas below Keeper,
with a two-row caption for the event and any still-open tool or branch threads.
Shorter views keep a compact mark or one caption line. The canvas appears only
when the matching host event is present in the current bounded event record.
Calm and reduced motion keep that event meaning while stopping decorative
movement; stale and unknown signals do not gain motion or guessed activity.

Keeper’s membrane breathes and flexes, trailing filaments sway independently,
and the crown and nearby satellite move subtly. Waiting is quieter. Arrival and
return gestures follow observed events and last long enough to read.

New launches use **Moonlight**: cool blue weave and a silver aperture.
Choose `moonlight`, `ember`, `moss`, `terminal-green`, or `classic` with
`KEEPER_THEME`, for example `KEEPER_THEME=moss codex --keeper side`.
The direct renderer also accepts `--theme moss`. Refresh an installed plugin
with `./install.sh` before starting a new session to use checkout changes.

Working has three sparse orbiting particles; observed tool starts and returns
add a brief spark. Waiting carries a slow aperture pulse, and an observed Stop
produces one expanding ripple lasting 1.2 seconds. Stop does not imply success.
Idle adds no particles. Calm, reduced motion, stale signals, and unknown or
ended sessions suppress these effects. Tiny views retain their compact state
indicator, and the large ASCII fallback retains its existing geometry.
Themes change colour only; `NO_COLOR` still applies. The rendering library
defaults to Classic so historical raster fixtures remain reproducible.

Active decoration targets at most 15 new bodies per second; slower idle and
calm rhythms keep their existing pace. Only changed terminal cells are written,
with a complete repaint on resize. Observed state, session identity,
attachment generation, resize, blink and motion changes invalidate the held
body immediately when observed. Drawing deadlines do not delay input or feed
polling. These are scheduling targets, not measured physical display FPS.

Once a tool or branch arrival gesture settles, its tether layer is rasterized
once and reused while Keeper’s membrane and aperture continue moving. A new
observed arrival bypasses the cache until its gesture settles. In a focused
100×32 dense PTY comparison, the layer cache reduced median renderer CPU from
35.75% to 23.94% of one core; sampled memory rose by 0.69 MiB. This is a
three-pair synthetic comparison. The complete current-source 90-case matrix
has now run: 7/15 CPU bounds, 15/15 RSS bounds and 14/15 composition bounds
passed, while 0/15 cells passed the repeatability bound. Its recommendation is
HOLD. The run uses a renderer PTY without tmux and is not a physical display
latency test; the paced 15 Hz target also produces more frames than the
uncapped control. See [validation](docs/VALIDATION.md) for full results and
limits.

Keeper does not store prompts, replies, reasoning, tool arguments, results,
transcripts, raw session IDs or project paths in its public presence feed.
Its hooks return an inert JSON object and make no permission decisions.
This release is local-only: Cyclops Link broadcasting and peer overlays are
retired. Older consent files are preserved but inactive here. Existing sessions
keep their loaded version; start a new session after refresh. See [PROTOCOL.md](PROTOCOL.md).

## Remove

```bash
./uninstall.sh
```

Open a new Bash terminal afterwards. Uninstall removes the plugin, marketplace
registration and Keeper’s startup block, preserving your other shell settings,
this checkout and recorded activity.

## Development and release

Run `./tools/check.sh` to check shell syntax and run the terminal test suite.
[Validation](docs/VALIDATION.md) records current test results, measurements,
platform limits and retained historical evidence.

MIT licensed. [Provenance](PROVENANCE.md). Independent project from the Cyclops
Eye Team; not made, endorsed or supported by OpenAI.

## Keeper paintings

Keeper makes deliberate saved paintings through `$cyclops-keeper:keeper paint` and the separate `save_painting` / `read_paintings` MCP tools. The latest valid saved Keeper painting appears above Keeper in panes at least 32 columns by 32 rows. The live-expression `paint` tool keeps its separate lower sketch space. Small panes hide the overhead. The launcher and historical 0.5.0 resource HOLD remain unchanged. Composition is explicitly assistant-authored; there is no autonomous painting engine or fixed style.

See [Painting Foundation V0](docs/PAINTING-V0.md) for validation, storage, peer reading and standalone preview. The user reported Studio confirmation after the V0 installation. That confirmation does not change the historical resource HOLD.

The skill is discoverable as `cyclops-keeper:keeper`; invoke it with `$`, not `/keeper`. You may opt into one picture per user message, plus roughly every 15 minutes of long active work, and ask for both saved and live pictures. That cadence is assistant guidance within the conversation, not an autonomous idle timer. Restart Keeper to load installed plugin updates.

### Painting buttons

The overhead grows toward the pane width, up to half the pane height, while retaining Keeper, the crest and lower live sketch. Click **Story**, **Convert** or **Roll** inside Keeper’s pane. Mouse support uses the terminal’s SGR protocol; keyboard alternatives in Keeper’s pane are `s` (story), `v` (convert), `o` (roll), Space (pause/play), `p`/`n` (previous/next), `e` (end story), and `x` (cancel export). Normal input in the Codex pane is unchanged.

- **Story:** choose this launch’s session or **All saved**, including older Keeper/Spark/Prism paintings. Each page reveals for 2.4 seconds, holds for 7, and stays on the last page. Pause/play, previous, next and end buttons sit below the painting. Folder determines painter credit.
- **Convert:** choose the held picture or all paintings in the selected scope; choose truest, faithful or both, then HD (1920 wide) or 4K (3840 wide). Truest keeps terminal cell weight and offers 6, 8, 16 (default), 32, 64 or 256 colour levels. These modes use no model tokens. PNG, raster-backed SVG and an HTML gallery are saved together. SVG contains the rendered image, not editable vector marks. Faithful renders the same marks into a bounded internal raster and smoothly enlarges it; it is not a new composition.
- **Roll:** choose session or all saved, then 720p, 1080p or portrait Short. Music derived from the marks is on by default and can be toggled off. The menu shows count and estimated duration; portrait rolls over three minutes ask for confirmation. Each roll has an eye title card, revealed paintings, date/painter credits, crossfades and a 30fps H.264/AAC MP4. Source animation is 12fps; the encoder duplicates frames to 30fps.

Exports run separately with a progress bar, percentage, completion at **100%**, and **Cancel**. Resizing to a small pane hides the surface without cancelling playback or a job. Closing Keeper or changing the attachment stops owned jobs. Completed exports appear in unique `keeper-paintings/convert-…/` or `keeper-paintings/roll-…/` directories with `index.html`; peer folders and original JSON paintings are unchanged.

Export dependencies are Pillow (`python3-pil`) and ffmpeg for rolls. Roll work storage uses the configured Cyclops HDD scratch volume and refuses a missing/wrong volume. At most 60 paintings per export; the selectable collection is limited to 1000, with an explicit message rather than silent truncation. No automatic refined/interpretive model calls, transcript copying, or shared painting parts are added.

The **Free/Work** button selects independent or broadly work-inspired subjects for the next assistant composition. The assistant reads the launch-bound painting brief; this is not a background model call. Fresh windows show an outline of the latest saved Keeper painting until a live sketch arrives. Reported painting token counts appear when supplied; unknown usage is omitted.
