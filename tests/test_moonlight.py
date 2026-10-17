"""Decorations must expire and cannot turn missing evidence into activity."""
import re
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'plugins/cyclops-keeper/scripts'))
import terminal
import terminal_art


def record(state='working', **extra):
    return dict(state=state, stale=False, sequence=1, active_tools=[],
                active_subagents=[], transitions=[], **extra)


class Moonlight(unittest.TestCase):
    def test_theme_changes_colour_only_across_sizes_and_fallbacks(self):
        strip=lambda value: re.sub(r'\x1b\[[0-9;]*m', '', value)
        for size in [(100,32),(24,12),(8,3)]:
            for unicode in [True,False]:
                frames=[terminal.render(record(),*size,now=100,colour=True,
                                        unicode=unicode,theme=theme)
                        for theme in ['classic','moonlight','ember','moss','terminal-green']]
                self.assertEqual(len(set(map(strip,frames))),1)
                self.assertGreater(len(set(frames)),1)
                self.assertNotIn('\x1b',terminal.render(record(),*size,theme='moonlight'))

    def test_particles_are_bounded_and_quiet_states_are_empty(self):
        def frame(state, now=100, **options):
            surface=terminal_art.Surface(40,20)
            terminal_art.expression_particles(surface,record(state),now,
                                              (40,40),1,**options)
            return sum(mask.bit_count() for row in surface.masks for mask in row)
        self.assertGreater(frame('working'),0)
        self.assertLessEqual(frame('working'),6)
        for state in ['idle','unknown','ended','interrupted','stopped']:
            self.assertEqual(frame(state),0)
        for option in ['calm','reduced_motion']:
            self.assertEqual(frame('working',**{option:True}),0)
        self.assertEqual(frame('working',lively=False),0)

    def test_stop_ripple_requires_recent_observed_stop(self):
        def frame(now, stale=False):
            surface=terminal_art.Surface(40,20)
            value=record('stopped')
            value.update(stale=stale,transitions=[dict(event='Stop',at=100)])
            terminal_art.expression_particles(surface,value,now,(40,40),1)
            return any(any(row) for row in surface.masks)
        self.assertTrue(frame(100.4))
        for now in [99,101.5,200]:
            self.assertFalse(frame(now))
        self.assertFalse(frame(100.4,stale=True))
