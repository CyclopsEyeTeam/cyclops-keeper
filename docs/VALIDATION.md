# Validation — 0.5.0

Prepared locally on 13 October 2026; not published. **Functional checks pass;
resource acceptance remains HOLD.** This is an unpublished release candidate,
not an accepted resource-performance release.

## Terminal interface and installation

The public launch interface is exactly `codex --keeper side`,
`codex --keeper top`, and `codex --keeper`. A plain `./install.sh` registers
the plugin and the managed Bash block together. Ordinary `codex` calls the
installed executable directly. Standalone launchers, the menu, browser route,
optional shell setup and legacy flag aliases are retired.

- Final full suite: 138 tests passed, no failures, errors or skips. The eight
  installation/removal checks include unexpected SDK status shapes; invalid
  status stops removal without claiming success.
- A real, credential-free installation of Codex 0.162.1 ran all three exact
  launch forms with its default host mode. Trusted-hook attachment, project
  directory, independent Keeper closure, terminal restoration and owned runtime
  cleanup passed. The separate GNOME/X11 window entered fullscreen.
- The fixture used a closed loopback provider, with no external model call.
  Hook-trust bypass was confined to that disposable fixture. Normal users review
  Keeper through `/hooks` and send the first message to attach.
- Reinstall refreshed the actual installed copy: all 17 runtime source/assets
  matched the candidate. Real uninstall removed the cached plugin files, disabled its
  configuration, removed the marketplace and Bash block, and preserved all 15
  recorded activity files byte for byte. Repeating uninstall also passed.
- The focus regression was reproduced in both layouts. Actual PTY keystrokes
  now reach Codex without first selecting its pane. Resize/reappearance also
  preserves user focus and existing tmux settings and unrelated panes.

## Artwork, privacy and pacing

The four core artwork files remain byte-identical to the source snapshot.
120 preserved golden frames and the wider raster conformance checks passed.
The GNOME/tmux checks exercised mouse scrollback, native selection/copy,
system clipboard transfer and bracketed paste on an isolated X11 display.

Active decoration uses the completed 200 ms deadline. Public observations,
session and attachment generation, geometry, blink and motion preferences
invalidate a held body immediately when observed. Slower idle/frozen polling
is preserved. Polling remains live between decorative frames; absolute
animation time is preserved. Tests include nested in-place changes and fresh
independently decoded snapshots. Held dense micro-frame work costs less than
one quarter of native composition in the scoped 1,000-call CPU test; this
is not a whole-process or physical-display result.

No prompts, reasoning, replies, tool arguments/results, raw session IDs or
project paths enter the public presence feed. Hooks return inert `{}` and
make no permission decisions. Link publishing and overlays are absent from
this runtime; older consent files are preserved and inactive here. Older
running versions keep their loaded code until those sessions end.

## Input and resize checks

Three 20-second windows per layout/variant, 20 literal character probes each,
a 320×100 terminal, 32 tools plus 32 branches, and a synthetic busy one-core
foreground fixture. Echo was observed through real tmux and a PTY, including
CLI and sampling overhead. This is not a heavy real-model or physical-paint test.
The baseline here is the preserved pre-cleanup 0.4.4 source, already paced.

| Layout | Baseline median p95 echo | Candidate | Limit | Result |
| --- | ---: | ---: | ---: | --- |
| side | 57.140 ms | 52.110 ms | 76.425 ms and ≤100 ms | PASS |
| top | 82.951 ms | 55.734 ms | 108.689 ms and ≤100 ms | PASS |

Each layout completed 100 resize transitions, including collapse/return,
with session/generation, Codex lifetime, focus and the 48×12 Codex floor intact.

| Layout | Resize p95 | Unchanged limit | Result |
| --- | ---: | ---: | --- |
| side | 750.403 ms | 1,308.645 ms | PASS |
| top | 765.668 ms | 1,270.720 ms | PASS |

## Resource comparison: HOLD

90 cases completed: three 20-second CPU windows after two-second warmup for
idle/working/32-tool+32-branch activity, four physical grids, and a full-size
truecolour supplement. Body width is physical columns minus one for wrap safety.
The native control disables decoration pacing in the same current renderer;
it is not a historical 0.4.3 binary. Both variants enable metrics equally.
Adjacent AB/BA/AB pairs used CPU affinity 7; frequency/load and 1 Hz RSS samples
were retained. CPU is renderer own user+system time as percent of one core.
Composition-loop metrics include cache hits and warmup; CPU windows exclude
warmup. RSS is a sampled maximum, not an exhaustive allocation peak.

| Physical grid | Colour | Activity | Native median CPU | Paced median CPU | CPU | Work loop | Repeatability |
| --- | --- | --- | ---: | ---: | --- | --- | --- |
| 100×32 | off | idle | 5.799% | 7.193% | FAIL | FAIL | HOLD |
| 100×32 | off | working | 15.739% | 9.399% | PASS | PASS | HOLD |
| 100×32 | off | dense | 30.424% | 18.793% | PASS | PASS | PASS |
| 48×20 | off | idle | 2.649% | 2.497% | PASS | PASS | HOLD |
| 48×20 | off | working | 7.399% | 4.298% | PASS | PASS | HOLD |
| 48×20 | off | dense | 20.691% | 12.796% | PASS | PASS | HOLD |
| 24×12 | off | idle | 0.999% | 1.200% | PASS | PASS | HOLD |
| 24×12 | off | working | 3.000% | 2.298% | PASS | PASS | HOLD |
| 24×12 | off | dense | 5.947% | 5.445% | PASS | PASS | HOLD |
| 6×1 | off | idle | 0.350% | 0.350% | PASS | PASS | HOLD |
| 6×1 | off | working | 0.949% | 1.299% | PASS | PASS | HOLD |
| 6×1 | off | dense | 3.948% | 3.947% | PASS | PASS | HOLD |
| 100×32 | truecolour | idle | 7.146% | 7.149% | PASS | PASS | HOLD |
| 100×32 | truecolour | working | 16.448% | 8.697% | PASS | PASS | HOLD |
| 100×32 | truecolour | dense | 31.229% | 17.840% | PASS | PASS | HOLD |

All 15 sampled RSS cells stayed within the unchanged native +8 MiB guard.
CPU uses the unchanged median bound: native + max(1 percentage point, 10%).
Work-loop p95 uses native ×1.10 +0.5 ms. Repeat spread uses
(max−min)/max(median,1 percentage point) ≤0.10 for each variant/cell.
No unfavorable sample was discarded. Full-size uncoloured idle failed CPU
and work-loop bounds; 14 of 15 cells failed repeatability. CPU frequency varied
substantially during the run. That is a recorded confound, not a demonstrated
root cause or a passing result. The source, captured source and harness hashes
matched before/after the run.

The uncoloured full-size dense cell passed every declared comparison bound:
native 30.424% versus paced 18.793% of one core. This scoped result does not
clear the failed cells or establish universally lightweight behaviour.
Historical failures, stopped/incomplete matrices and their original HOLD
recommendations remain preserved. This run does not upgrade those earlier gates.

## Filesystem and platform limits

Two HDD suite runs retained explicit observer timeouts under the unchanged
2.4-second hook budget: one 16-writer timing case and one initial SessionStart.
The final functional checks used small hook/state/path fixtures on SSD to match
the installed application-state layout and exercise fsync/path semantics.
Terminal/AppImage/X11 scratch, screenshots and other generated outputs stayed
on the designated HDD. This exception is recorded in the private run evidence.
Slow storage can reject an unacknowledged observation; the view then remains
unattached/unavailable. These failures were not tuned away or relabelled passes.

Supported setup: Linux/Bash, Python 3.10+, tmux for side/top, and GNOME Terminal
on an X11 desktop for the separate fullscreen view. Local tests used Python
3.12.3. Other shells, macOS and Wayland fullscreen placement
are not validated for this release.

The GitHub workflow is configured for Ubuntu 24.04 / Python 3.10 and 3.12 with
an isolated X11 display. Its structure was checked locally; cloud CI has not run.
Publishing and live user installation are separate from this prepared candidate.
