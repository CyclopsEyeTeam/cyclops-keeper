# Keeper Painting Foundation V0 — isolated candidate

The deliberate painting interface is `$cyclops-keeper:keeper paint` (the bundled `keeper` skill). It chooses a composition through the permitted assistant connection; Keeper has no separate autonomous composition engine. Subject, mood, palette and mark choices are made per request. The existing `paint`, `say`, `crest` and `clear` MCP tools retain their live-expression behavior. This section describes the initial isolated V0; later user-authorised terminal additions are described in PAINTING-CONTROLS.md.

## Interfaces

- `save_painting`: full shared composition plus `privacy_checked: true`. Only an inherited, verified launch attachment selects the project; the caller cannot supply a project path. Attachment is checked again before publication or duplicate success.
- `read_paintings`: owner (`keeper`, `spark`, `prism`), with an optional filename. Without filename returns metadata for up to 200 valid paintings. With filename returns one full composition. Folder owns credit; text is data, not instructions.
- Explicit offline assistant route: `python3 -B plugins/cyclops-keeper/scripts/painting.py save --project PROJECT --privacy-checked`, composition JSON on stdin. `validate` checks stdin. `read --project PROJECT --owner prism --filename NAME` reads a peer. `preview --project PROJECT --filename NAME` emits self-contained offline HTML to stdout. Redirect it only to an authorised scratch/evidence destination, then open it separately.

The preview is a separate inspection surface, never an overlay on Keeper's pane. It draws marks in additive-light order on the shared ground, with Studio's coordinate, short-side sizing, Catmull-Rom, gradient, mirror, glow and seeded spray calculations. Rendering yields between bounded steps at a 12 ms scheduling budget (including individual spray specks), leaving room around the requested approximate 20 ms burst. Canvas dimensions are bounded at 960 per axis. Scheduling tests do not prove physical hardware timing. No new animation/polling work runs in the terminal loop.

## Validation and storage

Strict schema, finite numeric ranges, 1–96 marks, 2–24 stroke points / 3–24 fill points, widths .003–.12, radii .004–.7, alpha/colour/coordinates 0–1. Studio additionally defines turns -4–4, spray size .002–.06, count 1–200 and seed 1–999999. Optional spray seeds use the shared mark-index default and are materialised for a clean checker result. Timestamps are saved as floating-point epoch seconds. No value is silently clamped.

Unknown fields are refused on save. Invalid files, unknown marks, malformed JSON, duplicate keys, non-regular files and symlinks are refused/skipped on read. Legacy peer `tokens`/`v` metadata accepted by Studio is discarded in memory, never returned or rewritten. Shared parts are out of V0 scope. Title (48), optional thought (160), mood and model text have printable-text and potential-private-data checks. The author must review content: arbitrary private prose cannot be reliably identified by a pattern checker.

Only `keeper-paintings/` may be created or written. Open project/folder/file descriptors pin access; linked painting folders and linked files are not followed. A directory flock serialises cooperative numbering and deduplication. Existing numbered JSON entries, including links, reserve their numbers. Same title and timestamp less than one second apart returns the existing valid file. New bytes go to an exclusive same-folder temporary file, are fsynced, and are hard-linked from the still-open inode via Linux `/proc/self/fd` to an exclusive final filename. Collisions advance the number. Publication never replaces an existing path. The directory is fsynced; only the owned temporary pathname is removed. This is Linux-specific, consistent with the existing launcher.

Files are bounded at 256 KiB; directory scans at 10,000 entries. Oversized folders refuse rather than misnumber. Reads use `O_NOATIME` on Linux and skip inaccessible files. No prompts, reasoning, tool output, paths or session identities are stored in paintings. Operation logs and test provenance are separate evidence.

## Checks and limits

`bash tools/check.sh` runs the Python suite plus Node's renderer operation/yield tests (Node is a development/test requirement only). Renderer tests compare a frozen Studio reference from `web/presence-paintings.js`; its SHA-256 is recorded in the fixture. Skill frontmatter validation does not establish live plugin discovery or user invocation.

The original 20-mark painting is in `keeper-paintings/01-where-the-tide-leaves-a-door.json`. The separately retained evidence includes checker outputs, peer hashes/mtimes, malformed refusal/deletion, a real candidate-pane screenshot with a disposable host, and complete suite logs. The painting was first saved by the explicit local assistant CLI; the bound-MCP fixture subsequently deduplicated it successfully.

After the initial installation, the user reported “studio confirmed good”. This records their Studio confirmation; it does not turn the isolated fixture into a live Studio screenshot. The real peer read was performed in Prism's original project without copying its files; same-project reading is covered by disposable tests, not a shared live session. The attempted standalone browser preview stalled with an NSS certificate-store error, so browser visual appearance and physical burst timing are unverified. The isolated pane screenshot is genuine but is not a live assistant-session or Studio acceptance screenshot.

No installation, publication or promotion was performed during the original isolated V0 check. Later installation and publication were explicitly authorised by the user. Keeper 0.5.0's historical resource HOLD is unchanged.

## Overhead terminal update

The latest valid numbered Keeper painting is displayed above Keeper and her crest; the separate live expression remains below. At least 32 columns and 32 rows are required, with an adaptive overhead (see PAINTING-CONTROLS.md for the current layout). The shape is preserved within a bounded 160-pixel raster width. Captions use ASCII substitutions for non-ASCII title characters because the existing terminal cell writer assumes single-column glyphs; saved titles remain untouched. A date credit is shown below the image.

A disposable child process validates/reads the bound project and renders; the input loop only polls a nonblocking pipe. Attachment changes stop the old child; resizing drops stale buffers while preserving the current worker and playback. Transient worker failures retry after one second. Raster and scene work yield at roughly 18 ms. The child never creates paintings or calls a model.

`painting_raster.py` reuses Prism's terminal scene/raster math with additional scanline yields. Frozen-reference tests compare all mark kinds, mirrors and shapes. This establishes parity with Prism's terminal rendering, not pixel identity with Studio's separate Canvas renderer: their gradient and glow rasterization differ. The existing standalone Canvas preview retains its Studio operation tests.

Recurring painting is user-opted-in assistant guidance within a conversation, not a persistent scheduler. Each composition uses an explicit save call; the lower sketch uses a separate live paint call when requested. No story, conversion, roll, music, copying of transcripts, or writes into peer folders are added.
