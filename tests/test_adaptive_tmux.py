import json
import os
from pathlib import Path
import tempfile
import time
import unittest

from test_tmux_launcher import Launch, link


class AdaptiveLayouts(unittest.TestCase):
    def test_normal_small_terminals_start_both_layouts(self):
        for mode, size, expected in [('side', (80, 24), 23), ('top', (80, 24), 8),
                                     ('side', (60, 20), 11), ('top', (60, 20), 7)]:
            with self.subTest(mode=mode, size=size), tempfile.TemporaryDirectory() as tmp:
                launch = Launch(tmp, mode=mode, size=size)
                try:
                    state = launch.attached()
                    companion = launch.panes()[state['tmux']['keeper']]
                    self.assertEqual(companion['width'] if mode == 'side' else companion['height'], expected)
                    self.assertTrue(link.alive(state['codex']))
                finally:
                    launch.close()

    def test_resize_keeps_attachment_and_scales_the_same_pane(self):
        for mode in ['side', 'top']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                launch = Launch(tmp, mode=mode)
                try:
                    state = launch.attached()
                    key = state['tmux']['keeper']
                    launch.resize(80, 24)
                    field, small = ('width', 23) if mode == 'side' else ('height', 8)
                    launch.wait(lambda: launch.panes()[key][field] == small)
                    self.assertEqual(json.loads(launch.state_path.read_text())['session'], state['session'])
                    launch.resize(160, 60)
                    large = 47 if mode == 'side' else 20
                    launch.wait(lambda: launch.panes()[key][field] == large)
                    self.assertTrue(link.alive(state['codex']))
                finally:
                    launch.close()

    def test_unsplittable_start_runs_codex_then_adds_keeper_when_expanded(self):
        for mode, size in [('side', (2, 24)), ('top', (80, 2))]:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                launch = Launch(tmp, mode=mode, size=size)
                try:
                    launch.wait(lambda: launch.receipt.exists())
                    host = link.process_identity(json.loads(launch.receipt.read_text())['pid'])
                    self.assertTrue(link.alive(host))
                    launch.resize(80, 24)
                    state = launch.attached()
                    self.assertEqual(state['codex'], host)
                    self.assertEqual(len(launch.panes()), 2)
                finally:
                    launch.close()

    def test_tiny_resize_restores_keeper_without_restarting_codex(self):
        for mode, size in [('side', (2, 24)), ('top', (80, 2))]:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                launch = Launch(tmp, mode=mode)
                try:
                    state = launch.attached()
                    first = state['tmux']['keeper']
                    launch.resize(*size)
                    launch.wait(lambda: len(launch.panes()) == 1)
                    self.assertTrue(link.alive(state['codex']))
                    launch.resize(80, 24)
                    launch.wait(lambda: len(launch.panes()) == 2)
                    restored = json.loads(launch.state_path.read_text())
                    self.assertNotEqual(restored['tmux']['keeper'], first)
                    self.assertEqual(restored['session'], state['session'])
                    self.assertEqual(restored['codex'], state['codex'])
                finally:
                    launch.close()

    def test_manual_keeper_close_stays_closed_after_resize(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch = Launch(tmp)
            try:
                state = launch.attached()
                # Pane creation precedes input setup, which flushes early keys.
                launch.wait(lambda: json.loads(launch.state_path.read_text())['tmux']['initial_ready_confirmed'])
                launch.tmux('send-keys', '-t', state['tmux']['keeper'], 'q')
                launch.wait(lambda: len(launch.panes()) == 1)
                launch.resize(160, 60)
                time.sleep(1)
                self.assertEqual(len(launch.panes()), 1)
                self.assertTrue(link.alive(state['codex']))
            finally:
                launch.close()


if __name__ == '__main__':
    unittest.main()
