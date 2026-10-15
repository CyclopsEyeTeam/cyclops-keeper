import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(os.environ.get('KEEPER_TEST_ROOT', str(Path(__file__).resolve().parents[1])))
sys.path.insert(0, str(ROOT / 'plugins/cyclops-keeper/scripts'))
import launcher


class NormalTerminalCommands(unittest.TestCase):
    def test_removed_aliases_are_refused(self):
        for flag in ['--keeper-side', '--keeper-top']:
            with self.assertRaises(ValueError):
                launcher.split_flags([flag])

    def test_top_and_side_are_consumed_as_the_keeper_layout(self):
        self.assertEqual(launcher.split_flags(['--keeper', 'top', '-C', 'my project']),
                         ('top', ['-C', 'my project']))
        self.assertEqual(launcher.split_flags(['--keeper', 'side', '-m', 'a-model']),
                         ('side', ['-m', 'a-model']))

    def test_no_layout_keeps_separate_window_and_prompt(self):
        self.assertEqual(launcher.split_flags(['--keeper', 'hello']), ('focus', ['hello']))
        self.assertEqual(launcher.split_flags(['--keeper']), ('focus', []))

    def test_option_values_and_literal_arguments_are_untouched(self):
        self.assertEqual(launcher.split_flags(['-m', '--keeper', 'top']),
                         (None, ['-m', '--keeper', 'top']))
        self.assertEqual(launcher.split_flags(['--', '--keeper', 'top']),
                         (None, ['--', '--keeper', 'top']))

    def test_keeper_launches_use_a_private_codex_process(self):
        for mode in ['side', 'top', 'focus']:
            prefix = ['--keeper'] + ([] if mode == 'focus' else [mode])
            with self.subTest(mode=mode), \
                 patch.object(sys, 'argv', ['launcher', *prefix, '--', 'literal']), \
                 patch.object(launcher, 'codex_command', return_value='codex'), \
                 patch.object(launcher, 'installed_plugin', return_value=ROOT), \
                 patch.dict(os.environ, {}, clear=True), \
                 patch('launcher_tmux.run', return_value=0) as tmux_run, \
                 patch.object(launcher, 'run', return_value=0) as window_run:
                self.assertEqual(launcher.main(), 0)
                selected = window_run if mode == 'focus' else tmux_run
                self.assertEqual(selected.call_args.args[1], ['--no-daemon', '--', 'literal'])

    def test_separate_keeper_window_requests_desktop_fullscreen(self):
        self.assertTrue(hasattr(launcher, 'window_options'), 'window launch options are not explicit yet')
        self.assertIn('--full-screen', launcher.window_options('focus'))
        self.assertFalse(any(arg.startswith('--geometry') for arg in launcher.window_options('focus')))


if __name__ == '__main__':
    unittest.main()
