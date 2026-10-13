import fcntl
import json
import os
import os
from pathlib import Path
import subprocess
import tempfile
import termios
import unittest

from test_tmux_launcher import Launch, ROOT


class RequestedCommands(unittest.TestCase):
    def test_exact_bash_commands_attach_in_the_project_and_keep_two_panes(self):
        for mode in ['top', 'side']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                launch = Launch(tmp, mode=mode, start=False)
                try:
                    def owner():
                        os.setsid()
                        fcntl.ioctl(launch.slave, termios.TIOCSCTTY, 0)
                    launch.child = subprocess.Popen(
                        ['bash', '--noprofile', '--norc', '-c',
                         'source "$1"; shift; codex "$@"', 'bash', str(ROOT / 'plugins/cyclops-keeper/scripts/integration.bash'),
                         '--keeper', mode, 'prompt with spaces'], cwd=launch.project,
                        env=launch.env, stdin=launch.slave, stdout=launch.slave, stderr=launch.slave,
                        preexec_fn=owner)
                    launch.attached()
                    launch.wait(lambda:json.loads(launch.state_path.read_text())['tmux'].get('initial_ready_confirmed'))
                    panes = launch.panes()
                    self.assertTrue(panes[launch.state['tmux']['source']]['active'], 'Keeper stole the normal Codex input focus')
                    os.write(launch.master,b'j')
                    launch.wait(lambda:b'host received j' in launch.data)
                    self.assertEqual(len(panes), 2)
                    pane = panes[launch.state['tmux']['keeper']]
                    self.assertEqual(pane['height'] if mode == 'top' else pane['width'],
                                     14 if mode == 'top' else 35)
                    self.assertEqual(json.loads(launch.receipt.read_text())['argv'], ['prompt with spaces'])
                    self.assertTrue(all(p['cwd'] == str(launch.project) for p in panes.values()))
                finally:
                    launch.close()


if __name__ == '__main__':
    unittest.main()
