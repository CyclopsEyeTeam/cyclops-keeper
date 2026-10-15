import contextlib,io,json,os,tempfile,time,unittest
from unittest.mock import patch
from test_tmux_launcher import Launch
import terminal

class ComposedFrames(unittest.TestCase):
    def frame(self,state,width,height,peers=False,relations=False):
        record={'session':'test','state':state,'stale':False,'active_tools':[],'active_subagents':[]}
        class UTFOutput(io.StringIO):
            encoding='UTF-8'
        if relations:
            record['active_tools']=[{'key':format(i,'064x'),'kind':'shell','sequence':i} for i in range(3)]
            record['active_subagents']=[{'key':format(i+10,'064x'),'sequence':i} for i in range(3)]
        output=UTFOutput()
        with patch('sys.argv',['keeper','--once','--attachment','fixture','--no-colour','--reduced-motion']),patch.object(terminal,'launch_selection',return_value=('test',True,('fixture-owner',1))),patch.object(terminal.presentation_state,'load',return_value={}),patch.object(terminal,'public_snapshot',return_value={'sessions':[record]}),patch.object(terminal.shutil,'get_terminal_size',return_value=os.terminal_size((width+1,height))),patch.dict(os.environ,{'TERM':'xterm-256color'}),contextlib.redirect_stdout(output):
            terminal.main()
        return output.getvalue()

    def test_responsive_eye_remains_visible(self):
        for size in [(20,3),(24,12),(19,8)]:
            self.assertIn('◎',self.frame('working',*size),size)

    def test_attached_small_excess_relations_are_counted(self):
        for size in [(19,8),(24,12)]:
            frame=self.frame('interrupted',*size,relations=True)
            self.assertIn('T:3+',frame)
            self.assertIn('B:3+',frame)

    def test_small_attached_states_remain_distinct(self):
        for size in [(19,8),(20,8),(24,12)]:
            frames=[self.frame(state,*size) for state in ['unknown','idle','working','stopped','ended','tool','branching','waiting','compacting','interrupted']]
            self.assertEqual(len(set(frames)),10,size)

class ForeignPanes(unittest.TestCase):
    def test_foreign_panes_cannot_leave_codex_squeezed_by_keeper(self):
        for mode,args in [('side',['-h','-l','45']),('top',['-v','-l','20'])]:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as tmp:
                launch=Launch(tmp,mode=mode)
                try:
                    state=launch.attached();source=state['tmux']['source']
                    foreign=launch.tmux('split-window','-d','-t',source,*args,'-P','-F','#{pane_id}','sleep 60').strip()
                    original=launch.tmux('display-message','-p','-t',foreign,'#{pane_pid}').strip()
                    launch.wait(lambda:json.loads(launch.state_path.read_text())['tmux']['keeper'] is None or (launch.panes()[source]['width']>=48 and launch.panes()[source]['height']>=12))
                    time.sleep(1.5)
                    panes=launch.panes()
                    self.assertEqual(launch.tmux('display-message','-p','-t',foreign,'#{pane_pid}').strip(),original)
                    fresh=json.loads(launch.state_path.read_text())
                    if fresh['tmux']['keeper'] is not None:
                        self.assertGreaterEqual(panes[source]['width'],48)
                        self.assertGreaterEqual(panes[source]['height'],12)
                    else:
                        self.assertEqual(len(panes),2)
                    self.assertEqual(fresh['generation'],state['generation'])
                    self.assertEqual(fresh['session'],state['session'])
                    self.assertEqual(fresh['codex'],state['codex'])
                finally:launch.close()

    def test_presentation_preferences_survive_suspension(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch=Launch(tmp)
            try:
                state=launch.attached();pane=state['tmux']['keeper']
                launch.wait(lambda:launch.state_path.with_suffix('.ready').exists())
                launch.tmux('send-keys','-t',pane,'c','r')
                preference=launch.state_path.parent/'.keeper-view.json'
                launch.wait(lambda:preference.exists() and json.loads(preference.read_text()).get('reduced_motion'))
                before=json.loads(preference.read_text())
                self.assertTrue(before['calm']);self.assertTrue(before['reduced_motion'])
                launch.resize(51,24);launch.wait(lambda:len(launch.panes())==1)
                launch.resize(120,42);launch.wait(lambda:len(launch.panes())==2)
                launch.wait(lambda:launch.state_path.with_suffix('.ready').exists())
                self.assertEqual(json.loads(preference.read_text()),before)
            finally:launch.close()
