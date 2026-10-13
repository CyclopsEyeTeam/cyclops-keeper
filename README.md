# Cyclops Keeper

A small, single-eyed presence for the Codex terminal. Keeper’s woven membrane,
crown and trailing filaments respond to observed session activity.

0.5.0 is an unpublished release candidate. Functional checks pass; resource
acceptance remains **HOLD**. See the [validation results](docs/VALIDATION.md).

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

Keeper observes activity: a turn started, tools or branches are active,
permission is waiting, compaction happened, a turn stopped, or the session
ended. A stopped turn is not a claim of success. Missing or old evidence is
shown as unavailable.

Active decorative drawing is limited to one new body per 200 ms; slower idle
rhythms keep their existing pace. Observed state, session identity,
attachment generation, resize, blink and motion changes invalidate the held
body immediately when observed. Animation keeps its original time source.
Drawing deadlines do not delay input or feed polling. A terminal can still
show less often when the host is busy; this is not a physical display FPS claim.

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
[Validation](docs/VALIDATION.md) records the checks and measured limits for this
candidate. Historical failures remain in the development evidence; they are not
turned into passing release results.

MIT licensed. [Provenance](PROVENANCE.md). Independent project from the Cyclops
Eye Team; not made, endorsed or supported by OpenAI.
