# Provenance

What each part of this repository is, who made it, and under what terms it is here.

| Part | Files | Origin | Terms |
| --- | --- | --- | --- |
| Keeper's code: hooks, observer, terminal compositions, browser panel, state mapper, fixture tool, tests | `plugins/cyclops-keeper/hooks/`, `scripts/`, `assets/*.js`, `assets/*.mjs` (except `colour-engine.js`), `assets/index.html`, `assets/keeper.css`, `keeper`, `tools/`, `tests/` | Written by GPT, working through Codex for the Cyclops Eye Team, in the private `cyclops-keeper` 0.2.0 project (October 2026). This release removes that project's Cyclops Studio feed and Studio renderer and fixes a first-frame crash in the browser panel. | MIT (see LICENSE) |
| Keeper's mark | `assets/keeper.svg` | A hand-written SVG by GPT, the same author, in the same project. It is Keeper's own identity, chosen by GPT for itself. An earlier visual study, supplied during development, inspired the membranes, aperture and drifting strands of that identity. No part of that study is included here. | MIT |
| Infinite Colour / DrawPlayer Colour Language | `assets/colour-engine.js` | The Cyclops Eye Team's own DrawPlayer/Zilo work, included unmodified apart from its header. Its author authorised its public release under this project's licence. | MIT |
| Palette | `assets/palette.json` | Generated from Infinite Colour by `scripts/generate-palette.mjs`. | MIT |
| Sound | `assets/keeper-sound.mjs` | Synthesised in code; no samples. | MIT |
| "I am Keeper" opening | `assets/keeper-manifest.wav` | Made in the same project. The words were synthesised with the eSpeak NG speech synthesiser, then slowed, filtered and shaped inside Keeper's synthesised membrane sound. It is a synthetic voice, not a recording of a person. | MIT |
| Screenshots | `media/` | Captured from this release, with disposable fixture data. | MIT |

Not included: the raster membrane artwork used by the private project. It is held back until the provenance of the
visual study it referenced is established.

Cyclops Keeper is an independent project. It is not made, endorsed or supported by OpenAI, and nothing here is an OpenAI
logo or trademark.
