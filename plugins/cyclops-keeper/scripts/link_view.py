"""What Keeper shows of the other presences when Cyclops Link is on.

Keeper never draws Spark or Prism himself. Each of them exported her own small look from her
own renderer (link-mark/spark.json, link-mark/prism.json, vendored with their SOURCE note);
Keeper places that look at the peer's seat in the canonical triangle and draws the handoff
threads their own records declare, over his own frame, on cells he left empty.

Seats (SPEC 11): Keeper sees Prism to the upper left (120 deg) and Spark to the left (180 deg).
"""
import json
import os
from pathlib import Path
import re
import time

import link

MARKS = Path(__file__).resolve().parents[1] / 'link-mark'
MAX_SHEET_BYTES = 256 * 1024
NAMES = {'spark': 'Spark', 'keeper': 'Keeper', 'prism': 'Prism'}
SGR = re.compile(r'\x1b\[([0-9;]*)m')


# ---------------------------------------------------------------- mark sheets (display only)

def _rgb(v):
    if v is None:
        return None
    if isinstance(v, list) and len(v) == 3 and all(type(c) is int and 0 <= c <= 255 for c in v):
        return tuple(v)
    raise ValueError('colour')


def load_sheet(presence, directory=MARKS):
    """A peer's own mark sheet, validated; None when missing or malformed (then no mark is invented)."""
    path = Path(directory) / f'{presence}.json'
    try:
        if path.is_symlink() or path.stat().st_size > MAX_SHEET_BYTES:
            return None
        raw = json.loads(path.read_text(encoding='utf-8'))
        if raw.get('v') != 1 or raw.get('presence') != presence:
            return None
        cols, rows = raw['cols'], raw['rows']
        if not (type(cols) is int and type(rows) is int and 0 < cols <= 64 and 0 < rows <= 32):
            return None
        frames = {}
        for state, grid in raw['frames'].items():
            if state not in link.STATES or len(grid) != rows or any(len(r) != cols for r in grid):
                return None
            frames[state] = [[(c[0] if isinstance(c[0], str) and len(c[0]) == 1 else ' ', _rgb(c[1]), _rgb(c[2]))
                              for c in row] for row in grid]
        if 'idle' not in frames:
            return None
        states_map = {k: v for k, v in (raw.get('states_map') or {}).items() if k in link.STATES and v in frames}
        ascii_frames = {s: [str(l)[:cols].ljust(cols) for l in lines] for s, lines in (raw.get('ascii') or {}).items()
                        if s in frames and isinstance(lines, list) and len(lines) == rows}
        core = raw.get('core')
        if not (isinstance(core, list) and len(core) == 4 and all(type(v) is int for v in core)
                and 0 <= core[0] < core[2] <= cols and 0 <= core[1] < core[3] <= rows):
            core = None
        return {'presence': presence, 'cols': cols, 'rows': rows, 'frames': frames,
                'states_map': states_map, 'ascii': ascii_frames, 'core': core}
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
        return None


def frame_for(sheet, state):
    if state in sheet['frames']:
        return state
    mapped = sheet['states_map'].get(state)
    return mapped if mapped in sheet['frames'] else 'idle'


def accent(sheet):
    best, score = (200, 200, 200), -1
    for row in sheet['frames']['idle']:
        for _, fg, _ in row:
            if fg and sum(fg) > score:
                best, score = fg, sum(fg)
    return best


# ---------------------------------------------------------------- reading the room

class Watch:
    """Keeper's Link reader for his terminal: off unless he is linked, at most one poll a second."""

    def __init__(self, data, environ=None):
        self.data = Path(data)
        self.environ = os.environ if environ is None else environ
        self.reader = link.Reader(self.environ)
        self.checked = -1e9
        self.on = False
        self.sheets = {p: load_sheet(p) for p in ('spark', 'prism')}

    def view(self, session_key, now=None):
        mono = time.monotonic()
        if mono - self.checked >= 1:
            self.checked = mono
            self.on = link.enabled(self.environ)
        if not self.on:
            return None
        now = time.time() if now is None else now
        records = self.reader.poll(mono)
        if self.reader.salt is None:
            return {'peers': [], 'threads': []}
        own = None
        mine = None
        if isinstance(session_key, str) and len(session_key) == 64:
            try:
                mine = json.loads((self.data / 'link' / (session_key + '.json')).read_text())
            except (OSError, ValueError):
                mine = None
        if isinstance(mine, dict) and link.HEX16.match(str(mine.get('instance', ''))):
            own = next((r for r in records if r['presence'] == 'keeper' and r['instance'] == mine['instance']), None)
            if own is None and link.HEX16.match(str(mine.get('room', ''))):
                own = {'presence': 'keeper', 'instance': mine['instance'], 'room': mine['room'],
                       'reaching': [], 'ended': False}
        if own is None:
            try:
                room = self.reader.own_room(os.path.realpath(os.getcwd()))
            except OSError:
                return {'peers': [], 'threads': []}
            own = {'presence': 'keeper', 'instance': '0' * 16, 'room': room, 'reaching': [], 'ended': False}
        return link.compose(own, records, now)


def status(view):
    if view is None:
        return 'Link: off'
    if not view['peers']:
        return 'Link: on · alone here'
    return 'Link: on · ' + ', '.join(sorted({NAMES[p['presence']] for p in view['peers']}))


# ---------------------------------------------------------------- composing over Keeper's own frame

def _parse(frame):
    """Keeper's rendered frame as rows of [character, sgr] cells."""
    rows = []
    for line in frame.split('\n'):
        row, code, i = [], '', 0
        while i < len(line):
            m = SGR.match(line, i)
            if m:
                code = '' if m.group(1) in ('', '0') else m.group(0)
                i = m.end()
                continue
            if line[i] == '\x1b':  # any other escape is left out of the cell grid
                i += 1
                continue
            row.append([line[i], code])
            i += 1
        rows.append(row)
    return rows


def _serialise(rows, colour):
    out = []
    for row in rows:
        parts, current = [], ''
        for ch, code in row:
            if colour and code != current:
                parts.append('\x1b[0m' + code if (current and '[48;' in current) or not code else code)
                current = code
            parts.append(ch)
        if colour and current:
            parts.append('\x1b[0m')
        out.append(''.join(parts))
    return '\n'.join(out)


def _code(fg, bg, colour, truecolour, dim=1.0):
    if not colour:
        return ''
    def one(rgb, base):
        rgb = [max(0, min(255, int(c * dim))) for c in rgb]
        if truecolour:
            return f'\x1b[{base};2;{rgb[0]};{rgb[1]};{rgb[2]}m'
        r, g, b = [round(v / 255 * 5) for v in rgb]
        return f'\x1b[{base};5;{16 + 36 * r + 6 * g + b}m'
    return (one(fg, 38) if fg else '') + (one(bg, 48) if bg else '')


def overlay(frame, width, height, view, sheets, *, unicode=True, colour=False, truecolour=False,
            now=0.0, reduced_motion=False, eye=None):
    """Keeper's frame with each present peer's own mark at her seat and the declared threads."""
    if not view or not view['peers']:
        return frame
    rows = _parse(frame)
    body = max(0, min(len(rows), height) - 1)  # the last row is Keeper's status line: never drawn over
    for row in rows:
        row.extend([' ', ''] for _ in range(width - len(row)))
    solid = set()

    def blank(x, y):
        return 0 <= y < body and 0 <= x < width and rows[y][x][0] == ' ' and (x, y) not in solid

    def put(x, y, ch, code):
        if 0 <= y < body and 0 <= x < width:
            rows[y][x] = [ch, code]

    by_class = {}
    for peer in view['peers']:
        by_class.setdefault(peer['presence'], []).append(peer)
    eye = eye or (width * .425, (height - 1) * .465)
    anchors = {'keeper': eye}
    for presence, peers in sorted(by_class.items()):
        sheet, first = sheets.get(presence), peers[0]
        label = f"{presence} · {first['state']}" + (f' ×{len(peers)}' if len(peers) > 1 else '')
        if not unicode:
            label = label.replace('·', '-').replace('×', 'x')
        if sheet:
            crop = None
            cols, nrows = sheet['cols'], sheet['rows']
            if (cols > width * .3 or nrows > body // 3) and sheet.get('core'):
                crop = sheet['core']
                cols, nrows = crop[2] - crop[0], crop[3] - crop[1]
            x0 = 1
            # Prism is up and to the left; Spark is level with Keeper's eye, to the left
            y0 = 1 if presence == 'prism' else max(1, min(body - nrows, round(eye[1] - nrows / 2) + 1))
            if presence == 'spark' and 'prism' in anchors and y0 <= anchors['prism'][1] + 2:
                y0 = min(body - nrows, int(anchors['prism'][1]) + 4)
            cx0, cy0, cx1, cy1 = crop or (0, 0, sheet['cols'], sheet['rows'])
            name = frame_for(sheet, first['state'])
            ascii_rows = sheet['ascii'].get(name)
            for yy in range(cy0, cy1):
                for xx in range(cx0, cx1):
                    ch, fg, bg = sheet['frames'][name][yy][xx]
                    if not unicode:
                        ch = ascii_rows[yy][xx] if ascii_rows else ('.' if ch != ' ' else ' ')
                        bg = None
                    if ch == ' ' and not bg:
                        continue
                    put(x0 + xx - cx0, y0 + yy - cy0, ch, _code(fg, bg, colour, truecolour))
                    solid.add((x0 + xx - cx0, y0 + yy - cy0))
            anchors[presence] = (x0 + cols / 2, y0 + nrows / 2)
            hue = accent(sheet)
        else:
            x0, y0, cols = 1, 1 if presence == 'prism' else round(eye[1]), len(NAMES[presence])
            for i, ch in enumerate(NAMES[presence]):
                put(x0 + i, y0, ch, _code((200, 200, 200), None, colour, truecolour))
                solid.add((x0 + i, y0))
            anchors[presence] = (x0 + cols / 2, y0)
            hue = (200, 200, 200)
        ly = y0 - 1
        if ly >= 0:
            for i, ch in enumerate(label[:max(0, width - x0)]):
                put(x0 + i, ly, ch, _code(hue, None, colour, truecolour, .8))
                solid.add((x0 + i, ly))
    dot, bead = ('·', '•') if unicode else ('.', 'o')
    for thread in view['threads']:
        a, b = anchors.get(thread['from']), anchors.get(thread['to'])
        if not a or not b:
            continue
        src = sheets.get(thread['from'])
        hue = accent(src) if src else (186, 167, 224)
        n = max(1, int(max(abs(b[0] - a[0]), abs(b[1] - a[1]) * 2)))
        path, seen = [], set()
        for i in range(n + 1):
            p = (round(a[0] + (b[0] - a[0]) * i / n), round(a[1] + (b[1] - a[1]) * i / n))
            if p not in seen:
                seen.add(p)
                if blank(*p):
                    path.append(p)
        for x, y in path:
            put(x, y, dot, _code(hue, None, colour, truecolour, .55))
        if path and not reduced_motion:
            x, y = path[int((now * 6) % len(path))]
            put(x, y, bead, _code(hue, None, colour, truecolour))
    return _serialise(rows, colour)
