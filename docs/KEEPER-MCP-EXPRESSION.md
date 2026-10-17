# Keeper authored space

Implemented 17 October 2026. This is a local, explicit creative channel alongside
observed activity. The authored space is not a permanent autonomous agent.

## Tools

The bundled MCP server `keeper` offers:

- `say({"caption":"A small fold of light, beside the work.","seconds":30})`
- `paint({"strokes":[{"ink":"glass","points":[[0.1,0.8],[0.3,0.3],[0.8,0.1],[0.6,0.8]]},{"ink":"gold","points":[[0.4,0.4],[0.5,0.4],[0.5,0.7],[0.4,0.7],[0.4,0.4]]}]})`
- `clear({})`
- `crest({"motif":"constellation","phrase":"A little orbit of light."})`

These are tool arguments, not shell commands. The host may prefix tool names.
Restart the Keeper-enabled Codex session after installation so it discovers the
new server. MCP tool approvals follow the host's existing settings.

The assistant may occasionally use these tools when the user has invited Keeper
expression. Silence is encouraged between useful expressions. No model loop,
watching agent, transcript reader, network request or automatic tool recursion
is added. Private thoughts are not extracted or displayed.

## Display and ownership

The lane is visibly labeled `Keeper / authored`, below the original body and
observed event captions, above the session status. It takes about 40% of pane
height, capped at 24 rows, with two-cell side margins; below 32 columns or 18 rows it is hidden. The
latest painting remains after the caption expires. Both are static, including
under Calm and Reduced Motion. Clear removes only authored content.

## Expanded drawing controls

`paint` replaces the drawing and labels together, preserving a live caption.
Supply strokes, labels, or both. An omitted collection is cleared. Use `clear`
to remove everything. Existing polyline calls remain compatible.

- Up to 32 strokes, each with 2–48 points, and at most 512 points in total.
- Optional stroke `kind`: `line` (default), `ellipse`, `rect`, or `curve`.
- Ellipses and rectangles take exactly two opposite bounding corners. Curves
  take four points: start, two control points, end. Coordinates run from 0 to 1.
- Up to six labels: `{"text":"moon","at":[0.4,0.2],"ink":"chalk"}`.
  Text is 1–40 printable ASCII characters and clips at the right margin.
- Inks: `glass`, `lavender`, `gold`, `chalk`, `mist`, `aqua`, `violet`, `rose`.
  Colours follow the selected theme; no-colour and ASCII fallback still work.
- Strokes draw in order; labels sit on top. Nothing animates automatically.

Example:

```json
{"strokes":[{"kind":"ellipse","ink":"gold","points":[[0.1,0.1],[0.35,0.65]]},{"kind":"curve","ink":"aqua","points":[[0.05,0.9],[0.3,0.5],[0.7,1],[0.95,0.6]]}],"labels":[{"text":"a little moon garden","at":[0.4,0.2],"ink":"chalk"}]}
```

Restart the Keeper-enabled Codex session after refreshing the plugin to load
the expanded MCP schema. The cached canvas also includes the selected theme.

The expressive crest occupies four rows above Keeper in panes of at least 32 columns
and 28 rows. It defaults to a decorative constellation; `crest` replaces it with
an authored `constellation`, `moon` or `ribbon`, plus an optional 0–48 character
printable ASCII `phrase`. It persists until replaced or cleared. This tool does
not change the bottom canvas or its caption. Smaller panes hide the crest.
`clear` removes the custom crest along with the canvas, leaving the default
decorative constellation. No phrase is generated automatically.

The motif gently orbits at four steps per second while the phrase stays still.
Calm, reduced motion, disabled lively motion, stale observations and unknown
sessions freeze the motif. Motion is decorative, not an activity or progress
signal; the assistant can deliberately change the motif and phrase with `crest`.
In tall panes, the observed-event drawing sits in the middle of the available
display with a smaller Keeper fitted above it. It expands to 90% of the pane
(up to 96 columns and 18 rows), retaining open colored lines and subtle corner
marks. Short panes retain their existing below-body or compact placement.

The existing event-keyed subagent satellites are the seats. No new synthetic
seat records were added. Parallel starts, late returns and out-of-order returns
continue through the existing reducer, independent of authored marks.

The MCP server uses inherited launcher ownership and verifies its process is a
descendant of the attached Codex. It cannot select another chat by argument.
Notes are private to the live launcher owner/session/generation; clear/resume
attachment changes hide old notes. Files are atomic and private, limited to one
caption and one bounded drawing. See PROTOCOL.md for bounds and privacy details.

## CPU and checks

- The MCP process blocks on stdin between calls. A two-second isolated idle
  sample recorded 0 CPU ticks (not proof of literally zero cost).
- Sampled MCP resident memory: 17.14 MiB on this host.
- 10,000 repeated painting-cache lookups: 0.00343 CPU seconds, one raster build.
- Terminal checks the artwork file at most four times per second and decodes
  only when the file signature changes. Four cached canvas layouts maximum.
- 63 existing caption/raster/render/pacing/face tests passed.
- 13 launcher checks passed with socket/X11 access; the first sandboxed run
  failed on denied local sockets and desktop access.
- Isolated MCP handshake, tool listing, real child-process publish/read,
  36 dimension/control layouts, caption expiry, clear, changed-attachment
  isolation, malformed geometry/control-text rejection and forbidden agent
  mutation all passed.

Evidence and an illustrative rendered fixture are in the HDD scratch run
`keeper-mcp-20261017`. The fixture uses simulated observed agents; it is not a
capture of a real delegated task. No full end-to-end CPU/tmux benchmark or
live Codex-host MCP invocation is claimed. Existing resource HOLD is unchanged.

## Files

New: `.mcp.json`, `scripts/expression.py`, `scripts/presence_mcp.py` inside the
plugin; this report. Updated: plugin manifest, terminal composition/reader,
README.md and PROTOCOL.md. No host event reducer or launcher ownership logic
was changed.
