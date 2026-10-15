"""Bounded previous-frame buffer and dirty-cell ANSI output for Keeper.

Keeper emits single-column ASCII/Braille glyphs and foreground SGR codes.
Cursor addressing avoids newline scrolling and keeps updates inside the pane.
"""
import re

SGR = re.compile(r'\x1b\[[0-9;]*m')


def cells(row, width):
    result = []
    style = ''
    offset = 0
    for match in SGR.finditer(row):
        result.extend((glyph, style) for glyph in row[offset:match.start()])
        code = match.group()
        style = '' if code in {'\x1b[0m', '\x1b[m'} else code
        offset = match.end()
    result.extend((glyph, style) for glyph in row[offset:])
    return (result + [(' ', '')] * max(0, width-len(result)))[:width]


class DirtyFrame:
    """Retain only the current pane's cells, never activity/history records."""
    def __init__(self):
        self.size = None
        self.rows = []
        self.raw = []

    def update(self, frame, width, height):
        raw = frame.split('\n')[:height]
        raw += [''] * (height-len(raw))
        resized = self.size != (width, height)
        output = ['\x1b[0m\x1b[2J'] if resized else []
        rows = []
        for y, text in enumerate(raw):
            if not resized and text == self.raw[y]:
                rows.append(self.rows[y])
                continue
            row = cells(text, width)
            rows.append(row)
            previous = None if resized else self.rows[y]
            x = 0
            while x < width:
                if previous is not None and row[x] == previous[x]:
                    x += 1
                    continue
                output.append(f'\x1b[{y+1};{x+1}H\x1b[0m')
                style = ''
                while x < width and (previous is None or row[x] != previous[x]):
                    glyph, current = row[x]
                    if current != style:
                        output.append(current or '\x1b[0m')
                        style = current
                    output.append(glyph)
                    x += 1
        if output:
            output.append('\x1b[0m')
        self.rows, self.raw, self.size = rows, raw, (width, height)
        return ''.join(output)
