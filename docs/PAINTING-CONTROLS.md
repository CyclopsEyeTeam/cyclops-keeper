# Keeper painting controls design and implementation plan

User request, 17 October 2026: larger overhead image, then pressable terminal buttons for story, convert and rolls with a status bar. Existing installation is reported working. Extend the reviewed V0 foundation, preserving identity, privacy, attachment and input behaviour. Work in an HDD copy; install only the completed tested update with rollback, no publication.

## Design

Use nearly the full pane width for wide paintings; allow up to half the pane height, keeping at least 18 rows below. Reserve toolbar/progress/control rows separately from the canvas. Existing crest and separate lower expression remain. A persistent rendering process receives resize and command messages so playback survives resize. Main terminal reads SGR mouse events only in its own pane, plus keyboard shortcuts, and restores mouse modes at exit. Host input is never intercepted.

Story reads validated paintings from all three folders, credits folder owner/date, orders by timestamp, reveals marks over 2.4 seconds, holds 7 seconds, ends on final page. Controls pause/play/again, previous/next/end. Default session scope uses launch time; explicitly choose all saved for older work. Never write peer folders.

Convert exports current held painting or all selected story paintings, truest/faithful or both, HD/4K. Deterministic export costs zero model tokens. No fabricated refined/interpretive model engine. Truest preserves terminal cell minimum sizes and configurable channel levels; faithful uses the same marks with finer raster resolution. PNG plus SVG containing the rendered image and a standalone HTML gallery, correctly credited. No unpainted shadows/bloom. Export SVG is explicitly raster-backed, not claimed editable vectors.

Roll exports 720p, 1080p or portrait short MP4, title card without project/conversation names, painting reveal and credit, crossfades, beat-aligned holds and optional painting-derived instrumental music. Stream frames to ffmpeg, retain no frame directory. Cancellation and failures never publish a partial final file. Publish complete unique export directories inside keeper-paintings with no-replace semantics. Work files live on verified HDD scratch; final atomic staging is same-folder and is an explicit filesystem exception. Each job is bounded to 60 paintings; show count/duration before starting. Short rolls beyond three minutes require a visible confirmation.

A separate export process reports progress at most five times/second and always on completion. Progress row includes action, fraction, eighth-cell bar, percentage and cancel. UI stays responsive while worker runs; attachment changes stop owned workers/jobs. Symlink output folders refused and files created exclusively. No text from prompts, reasoning or session identifiers in artwork/exports.

## Steps and checks

- [x] Resize canvas and test aspect/space/layout at screenshot size and small panes.
- [x] Add streaming input parser, toolbar hitboxes, story timeline, session/library collection; test split mouse packets and same-context resize.
- [x] Add safe export job runner, PNG/SVG/gallery, and music/MP4 streaming; test real small output, cancellation, collisions and symlinks.
- [x] Integrate persistent panel worker and progress polling; real tmux mouse clicks, input, resize, complete progress and screenshots.
- [x] Review, focused and full regression checks, preserve diff/results/rollback, install and verify installed files.

User confirmed painting-derived music. Request payloads use a bounded anonymous memory fd rather than SSD temporary files. The progress worker publishes size-tagged frames and ignores invisible hitboxes while the pane is hidden. Collections filter before the 1000-painting limit and report an explicit error. Output folder/staging inode checks run immediately before exclusive publication. No changes to historical resource HOLD.

The overhead leaves a dedicated lower live draw box and uses the larger Keeper focus envelope. A fresh launch starts with its own live sketch state and a saved-painting outline fallback; it never borrows another launch's expression. The compact constellation replaces the decorative heading and freezes in quiet modes.

A painting may carry a nonnegative integer `tokens` reported by its generation provider. The credit row shows this count when available; absent usage is omitted, not displayed as zero. Never attribute whole-turn tokens to one picture. Per-message composition remains an explicit assistant action, requested early in each turn by the plugin instructions; the observer does not call a model or guarantee delivery.

## Roomier live sketch and choice

Idle toolbar gaps and live canvas headings are removed. With overhead art, activity wording shares the last attachment row. The lower space expands to roughly a third of the remaining height.

A fresh session without live strokes/labels shows an outline interpretation of its latest saved Keeper painting. Geometry uses the shared Catmull-Rom/mirror/seeded scene, rendered as thin theme-coloured lines; fills become outlines, glows are omitted, sprays become points. It is not an exact colour reproduction or a new authored painting. This work runs and caches in the painting worker. No other launch's expression is read. Captions can coexist; authored live strokes/labels take priority.

Click **Free** to switch to **Work**, and again to return. This choice is per attachment and is available even before any painting exists. The assistant reads `painting_brief` before composition. Work means broad abstract inspiration, never private task details or source code. Both modes retain the opted-in per-message cadence, which remains assistant-dependent.

## Truest colour steps

PNG painting pixels are stepped after resizing, before the caption. SVG is still raster-backed artwork, now inside an sRGB component-transfer group; caption background and native text are outside. There is no old artificial-depth renderer to preserve as layered. Roll painting frames use the same truest raster function; crossfades and lossy video encoding can introduce intermediate values. The existing 12-to-30 fps conversion repeats frames rather than synthesizing motion.

The level button cycles 16, 32, 64, 256, 6, 8. 256 disables posterization. Default remains 16. A supplied screenshot sample had about 3.05% of painting channel bytes divisible by 17, so 16 levels is not claimed as an exact match for this terminal. Rendering retains a bounded intermediate resolution; truest is not an exact screenshot enlargement or fully vector SVG.
