"""Incremental ANSI output must reconstruct the same coloured terminal cells."""
import re
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'plugins/cyclops-keeper/scripts'))
import terminal_output


from terminal_screen import Screen

class DirtyOutput(unittest.TestCase):
    def test_movement_erases_old_cells_and_does_not_rewrite_unchanged_rows(self):
        painter = terminal_output.DirtyFrame()
        screen = Screen()
        screen.feed(painter.update('  ⠁     \nstatus  ', 8, 2))
        delta = painter.update('   ⠁    \nstatus  ', 8, 2)
        screen.feed(delta)
        self.assertEqual(screen.cells[0, 2], (' ', ''))
        self.assertEqual(screen.cells[0, 3], ('⠁', ''))
        self.assertNotIn('status', delta)
        self.assertLess(len(delta.encode()), 35)
        self.assertEqual(painter.update('   ⠁    \nstatus  ', 8, 2), '')

    def test_colour_only_changes_and_reset_do_not_bleed_into_other_cells(self):
        painter = terminal_output.DirtyFrame(); screen = Screen()
        red='\x1b[38;5;1m'; blue='\x1b[38;5;4m'; reset='\x1b[0m'
        screen.feed(painter.update(red+'⠁'+reset+' x', 3, 1))
        screen.feed(painter.update(blue+'⠁'+reset+' x', 3, 1))
        self.assertEqual(screen.cells[0, 0], ('⠁', blue))
        self.assertEqual(screen.cells[0, 2], ('x', ''))
        screen.feed(painter.update('⠁  ', 3, 1))
        self.assertEqual(screen.cells[0, 0], ('⠁', ''))
        self.assertEqual(screen.cells[0, 2], (' ', ''))

    def test_resize_and_short_rows_clear_old_content(self):
        painter = terminal_output.DirtyFrame(); screen = Screen()
        screen.feed(painter.update('long row\nold text', 8, 2))
        screen.feed(painter.update('new', 8, 2))
        self.assertEqual(screen.cells[0, 3], (' ', ''))
        self.assertEqual(screen.cells[1, 0], (' ', ''))
        delta = painter.update('ok', 4, 1)
        self.assertIn('\x1b[2J', delta)
        screen.feed(delta)
        self.assertNotIn((1, 0), screen.cells)
        self.assertEqual(screen.cells[0, 0], ('o', ''))

    def test_real_animation_deltas_match_full_coloured_frames(self):
        import terminal
        painter = terminal_output.DirtyFrame(); actual = Screen()
        for width,height in [(80,24),(80,24),(40,12),(6,1)]:
            for state in ['working','branching','waiting','unknown','idle']:
                frame=terminal.render(state,width,height,now=1000.3,colour=True,truecolour=True)
                actual.feed(painter.update(frame,width,height))
                expected=Screen()
                # Reference paints each complete row directly, without the differ.
                rows=frame.split('\n')
                for y in range(height):
                    row=rows[y] if y<len(rows) else ''
                    visible=re.sub(r'\x1b\[[0-9;]*m','',row)
                    expected.feed(f'\x1b[{y+1};1H\x1b[0m'+row+'\x1b[0m'+' '*(width-len(visible)))
                self.assertEqual(actual.cells,expected.cells)
