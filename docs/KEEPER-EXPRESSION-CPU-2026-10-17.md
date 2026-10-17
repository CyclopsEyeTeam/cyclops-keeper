# Keeper expression and CPU refinement — 17 October 2026

Implemented and checked in the source folder. The subsequent user-approved installation refreshed the local plugin on 17 October 2026; existing running panes need reopening. This report accompanies the source update on GitHub.

## Expression

The bounded, public event trail now supplies continuity to captions:

| Observed facts | Keeper wording example |
| --- | --- |
| Prompt immediately after interruption | A fresh line meets the held thread. |
| Tool kind changes to change | I turn a making line outward. |
| Another concurrently tracked inspection starts | Another looking line; its own tether. |
| Inspection returns while calls remain | One looking line back; others stay out. |
| Branch returns while branches remain | One side thread rests; others stay open. |
| Permission requested with open relations | At the gate, with open threads held. |
| Turn stops with unresolved relations | The turn rests; open threads stay marked. |
| Repeated returns in the observed turn trail | The looking thread folds back in. |

Repetition varies only on observed events, never on a timer. Narrow panes retain compact wording. Stale and unknown captions override these expressions. No prompt content, tool payload, inferred outcome or private thought enters the captions. Relation ownership and matching are unchanged.

## CPU diagnosis and changes

A fresh profile of 120 normal 100x32 frames attributes about 78% of cumulative render time to curve rasterization. The Python rasterizer samples many short segments and rounds subcell coordinates. This establishes an internal drawing cost; it does not establish tmux's contribution to end-to-end CPU.

The settled witness painting was being redrawn on every frame. A four-entry LRU now retains that raster using integer tile bounds plus public event class/kind. Live reveals bypass it. Body breathing and all tethers remain unchanged.

Calm frames were recomposed even after their event gestures finished. The existing one-frame cache now retains settled Calm full/compact Unicode frames. Fresh or future-dated gestures bypass it; changes to observations, size, controls or blink invalidate it. Normal motion keeps the existing 15 Hz target.

## Focused measurements

Six alternating before/after pairs; 120 identical animation samples per run at 1/15-second sample intervals; process CPU time; warmed one frame. These are composition measurements, without sleeping, polling, terminal output or tmux. They are not measured whole-process CPU percentages.

| Grid | Mode | Before median CPU seconds | After | Reduction |
| --- | --- | ---: | ---: | ---: |
| 100x32 | Normal | 0.6175 | 0.5490 | 11.1% |
| 60x54 | Normal | 0.3107 | 0.2749 | 11.5% |
| 100x32 | Settled Calm | 0.5182 | 0.00235 | 99.5% |
| 60x54 | Settled Calm | 0.3488 | 0.00218 | 99.4% |

There is substantial sample variance. The result is a focused improvement, not full resource acceptance. Existing historical HOLD evidence remains valid. The older native/paced matrix also compares different effective frame rates; it cannot by itself isolate raster efficiency. End-to-end tmux cost and current RSS were not measured in this pass.

## Checks and reproduction

- 63 existing focused tests passed: captions (8), raster conformance (4), render work (6), face (37), pacing (8).
- 864 direct before/after raster comparisons matched, including event classes, reveal boundaries, dimensions, Calm and Reduced Motion.
- 112 retained Calm frames matched fresh renders, including future timestamps, arrivals/returns, unfolding, size changes and blinks.
- Eight caption sequences were inspected, with stale override checks.

Small temporary evidence, original source files, raw measurements, captions and comparison script are on the designated HDD:

`/mnt/e0c1f9cf-dfe9-4135-9aa1-9697141a36d9/CyclopsScratch/Codex/keeper-personal-cpu-20261017/`

The comparison script reads this source folder and the retained original modules. Preserve its existing results before rerunning; it writes `results.json` and `profile.txt` in that evidence directory.

Changed runtime files: `plugins/cyclops-keeper/scripts/terminal.py` and `plugins/cyclops-keeper/scripts/terminal_art.py`.

## Deliberately excluded

No lower frame rate, removed threads, weaker geometry, random mood sentences, invented success or autonomous hidden agent. Moving the curve rasterizer to native code may reduce the remaining hot-loop cost, but adds build/platform complexity and requires its own exact-output comparison. It is not implemented here.
