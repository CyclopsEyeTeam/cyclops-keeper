#!/usr/bin/env python3
"""Keeper's Cyclops Link mark sheet: Keeper's own woven form, drawn by her own terminal
renderer (scripts/terminal_art.py), small, one frame per Link state.

Other presences carry a copy of keeper.json and place it at Keeper's seat;
they never draw Keeper themselves.
    python3 tools/export-link-mark.py        writes plugins/cyclops-keeper/link-mark/keeper.json
"""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'plugins' / 'cyclops-keeper' / 'scripts'))
sys.dont_write_bytecode = True
from terminal import _record          # noqa: E402  Keeper's own record normaliser
from terminal_art import draw_keeper  # noqa: E402  Keeper's own renderer

COLS, ROWS = 14, 7               # drawn at this size, then trimmed to the ink every frame shares
TOOL = 'a' * 64
AGENT = 'b' * 64

# Link state -> (Keeper's own state, what is in flight). Keeper's own words where she has them.
STATES = {
    'idle': ('idle', [], []),
    'working': ('working', [], []),
    'tool': ('tool', [{'key': TOOL, 'kind': 'execute', 'sequence': 1}], []),
    'waiting': ('waiting', [{'key': TOOL, 'kind': 'execute', 'sequence': 1}], []),
    'compacting': ('compacting', [], []),
    'stopped': ('stopped', [], []),
    'interrupted': ('interrupted', [], []),
    'ended': ('ended', [], []),
}
SGR = re.compile(r'\x1b\[([0-9;]*)m')


def cells(name):
    state, tools, agents = STATES[name]
    record = _record(state)
    record['active_tools'] = tools
    record['active_subagents'] = agents
    text = draw_keeper(record, COLS, ROWS + 1, '', mode='focus', now=0, calm=False,
                       reduced_motion=True, colour=True, truecolour=True)
    rows = []
    for line in text.split('\n')[:ROWS]:
        row, fg, i = [], None, 0
        while i < len(line):
            m = SGR.match(line, i)
            if m:
                codes = m.group(1).split(';')
                fg = None if codes == ['0'] else [int(v) for v in codes[2:5]]
                i = m.end()
                continue
            ch = line[i]
            row.append([ch, fg if ch != ' ' else None, None])
            i += 1
        rows.append((row + [[' ', None, None]] * COLS)[:COLS])
    return rows


def crop(all_frames):
    inked = [(x, y) for f in all_frames.values() for y, row in enumerate(f)
             for x, c in enumerate(row) if c[0] != ' ']
    x0, x1 = min(x for x, _ in inked), max(x for x, _ in inked) + 1
    y0, y1 = min(y for _, y in inked), max(y for _, y in inked) + 1
    return {n: [row[x0:x1] for row in f[y0:y1]] for n, f in all_frames.items()}


frames = crop({name: cells(name) for name in STATES})
ascii_frames = {name: [''.join('.' if c[0] != ' ' else ' ' for c in row) for row in frames[name]]
                for name in frames}
sheet = {
    'v': 1, 'presence': 'keeper', 'cols': len(frames['idle'][0]), 'rows': len(frames['idle']),
    'note': "Keeper's own woven form, rendered by her own terminal renderer (scripts/terminal_art.py). "
            "A host draws it at Keeper's seat; it never redraws Keeper itself.",
    'states_map': {'listening': 'idle', 'thinking': 'working'},
    'frames': frames, 'ascii': ascii_frames,
}
out = ROOT / 'plugins' / 'cyclops-keeper' / 'link-mark' / 'keeper.json'
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(sheet, ensure_ascii=False) + '\n', encoding='utf-8')
print(out.relative_to(ROOT), ' '.join(frames))
