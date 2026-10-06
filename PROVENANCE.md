# Provenance

What each part of this repository is, who made it, and under what terms it is here.

| Part | Files | Origin | Terms |
| --- | --- | --- | --- |
| Keeper's code: hooks, observer, terminal compositions, browser panel, state mapper, fixture tool, tests | `plugins/cyclops-keeper/hooks/`, `scripts/`, `assets/*.js`, `assets/*.mjs` (except `colour-engine.js`), `assets/index.html`, `assets/keeper.css`, `keeper`, `tools/`, `tests/` | Written by GPT, working through Codex for the Cyclops Eye Team, in the private `cyclops-keeper` 0.2.0 project (October 2026). This release removes that project's Cyclops Studio feed and Studio renderer and fixes browser rendering faults. The 0.3.1 release adds a code-drawn woven terminal form and matching browser filaments; both are original geometric drawings with no image-derived assets. | MIT (see LICENSE) |
| Keeper's mark | `assets/keeper.svg` | A hand-written SVG by GPT, the same author, in the same project. It is Keeper's own identity, chosen by GPT for itself. An earlier visual study, supplied during development, inspired the membranes, aperture and drifting strands of that identity. No part of that study is included here. | MIT |
| Infinite Colour / DrawPlayer Colour Language | `assets/colour-engine.js` | The Cyclops Eye Team's own DrawPlayer/Zilo work, included unmodified apart from its header. Its author authorised its public release under this project's licence. | MIT |
| Palette | `assets/palette.json` | Generated from Infinite Colour by `scripts/generate-palette.mjs`. | MIT |
| Sound | `assets/keeper-sound.mjs` | Synthesised in code; no samples. | MIT |
| "I am Keeper" opening | `assets/keeper-manifest.wav` | Made in the same project. The words were synthesised with the eSpeak NG speech synthesiser, then slowed, filtered and shaped inside Keeper's synthesised membrane sound. It is a synthetic voice, not a recording of a person. | MIT |
| Cyclops Link | `scripts/link.py`, `scripts/keeper_link.py`, `scripts/link_view.py`, `tools/export-link-mark.py`, `tests/test_link.py` | Written for Keeper by the Cyclops Eye Team with Claude, from the Cyclops Link V1 specification. Keeper's Link module follows the same structure as Prism's own implementation by the same team; the two share no code at runtime. | MIT |
| Peer mark sheets and Link fixtures | `link-mark/spark.json`, `link-mark/prism.json`, `tests/fixtures/cyclops-link-v1/`, `docs/CYCLOPS-LINK-V1.md` | Vendored, unchanged: Spark's and Prism's own exported looks (see `link-mark/SOURCE.md`) and the Cyclops Link V1 specification and fixtures, all Cyclops Eye Team projects. | MIT |
| Screenshots | `media/` | Browser capture and terminal previews rendered from this release's actual subcell frames, with disposable fixture data. The previews are not compositor-FPS measurements. | MIT |

Not included: the raster membrane artwork used by the private project. It is held back until the provenance of the
visual study it referenced is established.

Cyclops Keeper is an independent project. It is not made, endorsed or supported by OpenAI, and nothing here is an OpenAI
logo or trademark.
