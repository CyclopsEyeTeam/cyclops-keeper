import json
import os
from pathlib import Path
import pty
import fcntl
import select
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'plugins/cyclops-keeper/scripts'
sys.path.insert(0,str(SCRIPTS))
import terminal
import launcher_link as link

class ResponsiveRendering(unittest.TestCase):
    def test_micro_has_eye_and_distinct_states_even_without_colour_or_motion(self):
        frames={state:terminal.render(state,6,1,now=1000,reduced_motion=True)
                for state in ['unknown','idle','working','tool','branching','waiting','compacting','stopped','interrupted','ended']}
        self.assertTrue(all('◎' in frame for frame in frames.values()))
        self.assertEqual(len(set(frames.values())),10)
        self.assertTrue(all(len(frame)==6 for frame in frames.values()))

    def test_micro_clock_motion_and_unavailable_freezing(self):
        self.assertNotEqual(terminal.render('working',6,1,now=1000),terminal.render('working',6,1,now=1000.8))
        self.assertEqual(terminal.render('working',6,1,now=1000,stale=True),terminal.render('working',6,1,now=1000.8,stale=True))

    def test_miniature_contains_a_canonical_eye_and_distinct_observed_poses(self):
        frames=[terminal.render(state,24,12,reduced_motion=True) for state in ['working','waiting','compacting','unknown']]
        self.assertTrue(all('◎' in frame for frame in frames))
        self.assertEqual(len(set(frames)),4)

    def test_all_size_neighbours_have_exact_grid_bounds(self):
        import re
        for width in range(1,101):
            for height in [1,2,3,4,7,8,11,12,19,20,31,32]:
                for unicode in [True,False]:
                    frame=terminal.render('tool',width,height,unicode=unicode,reduced_motion=True)
                    rows=frame.split('\n')
                    self.assertEqual(len(rows),height)
                    self.assertTrue(all(len(row)==width for row in rows),(width,height,rows))

    def test_tiny_attached_view_is_not_overwritten_by_a_status_sentence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'attachment.json'
            link.atomic(path,{'v':1,'owner':link.process_identity(os.getpid()),'session':None,'project_fd':None})
            master,slave=pty.openpty()
            fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',1,6,0,0))
            process=subprocess.Popen([sys.executable,str(SCRIPTS/'terminal.py'),'--attachment',str(path),'--data',tmp,'--no-colour'],
                                     stdin=slave,stdout=slave,stderr=slave,env=dict(os.environ,TERM='xterm-256color',KEEPER_LINK='0'))
            try:
                data=b'';deadline=time.monotonic()+4
                while '◎'.encode() not in data and time.monotonic()<deadline:
                    if select.select([master],[],[],.1)[0]:data+=os.read(master,65536)
                self.assertIn('◎'.encode(),data)
                self.assertNotIn(b'Sessi',data)
            finally:
                process.terminate();process.wait(timeout=4);os.close(master);os.close(slave)

if __name__=='__main__':unittest.main()
