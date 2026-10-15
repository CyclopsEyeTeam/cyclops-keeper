"""Small independent ANSI screen model for renderer integration checks."""
import re


class Screen:
    def __init__(self):
        self.cells = {}; self.row = self.col = 0; self.style = ''

    def feed(self, output):
        for token in re.findall(r'\x1b\[[0-9;?]*[A-Za-z]|[^\x1b]', output):
            if token.startswith('\x1b['):
                if token.endswith('H'):
                    self.row, self.col = [int(n)-1 for n in token[2:-1].split(';')]
                elif token == '\x1b[2J':
                    self.cells.clear()
                elif token.endswith('m'):
                    self.style = '' if token == '\x1b[0m' else token
                elif token.endswith(('h', 'l')):
                    pass
                else:
                    raise AssertionError(token)
            else:
                self.cells[self.row, self.col] = (token, self.style)
                self.col += 1


    def text(self):
        height=max((y for y,x in self.cells),default=-1)+1
        width=max((x for y,x in self.cells),default=-1)+1
        return '\n'.join(''.join(self.cells.get((y,x),(' ',''))[0] for x in range(width)) for y in range(height))

