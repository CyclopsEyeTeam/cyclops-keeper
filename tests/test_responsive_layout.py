import json
import tempfile
import time
import unittest
from test_tmux_launcher import Launch, link

class ResponsiveLayout(unittest.TestCase):
    def test_codex_priority_collapse_and_stable_return(self):
        for mode,small,resumed in [('side',(51,24),(54,24)),('top',(80,13),(80,15))]:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                launch=Launch(tmp,mode=mode)
                try:
                    state=launch.attached();pane=state['tmux']['keeper']
                    launch.resize(*small)
                    launch.wait(lambda:len(launch.panes())==1)
                    self.assertTrue(link.alive(state['codex']))
                    # Oscillation inside the resume margin must not recreate.
                    boundary=(53,24) if mode=='side' else (80,14)
                    for _ in range(4):
                        launch.resize(*boundary);time.sleep(.18)
                        self.assertEqual(len(launch.panes()),1)
                        launch.resize(*small);time.sleep(.18)
                    launch.resize(*resumed)
                    launch.wait(lambda:len(launch.panes())==2)
                    fresh=json.loads(launch.state_path.read_text())
                    self.assertEqual(fresh['codex'],state['codex'])
                    self.assertEqual(fresh['session'],state['session'])
                    self.assertEqual(fresh['generation'],state['generation'])
                    self.assertNotEqual(fresh['tmux']['keeper'],pane)
                    source=launch.panes()[fresh['tmux']['source']]
                    self.assertGreaterEqual(source['width'],48)
                    self.assertGreaterEqual(source['height'],12)
                finally:launch.close()

    def test_return_does_not_steal_focus_from_codex(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch=Launch(tmp)
            try:
                state=launch.attached();source=state['tmux']['source']
                launch.wait(lambda:json.loads(launch.state_path.read_text())['tmux']['initial_ready_confirmed'])
                launch.tmux('select-pane','-t',source)
                launch.resize(51,24);launch.wait(lambda:len(launch.panes())==1)
                launch.resize(120,42);launch.wait(lambda:len(launch.panes())==2)
                time.sleep(.4)
                self.assertTrue(launch.panes()[source]['active'])
            finally:launch.close()

if __name__=='__main__':unittest.main()
