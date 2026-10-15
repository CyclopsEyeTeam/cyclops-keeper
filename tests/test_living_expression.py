"""Life is decoration; identity, observation and quiet controls stay truthful."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'plugins/cyclops-keeper/scripts'))
import terminal


def body(frame):
    return frame.rsplit('\n',1)[0]


def record(state='working', **extra):
    value=dict(state=state,sequence=1,active_tools=[],active_subagents=[],transitions=[])
    value.update(extra)
    return value


class LivingExpression(unittest.TestCase):
    def test_woven_body_and_small_form_have_visible_life(self):
        for size in [(100,32),(50,20),(24,12)]:
            with self.subTest(size=size):
                original=terminal.render(record(),*size,now=1000.4,lively=False)
                living=terminal.render(record(),*size,now=1000.4)
                later=terminal.render(record(),*size,now=1000.9)
                self.assertNotEqual(body(living),body(original))
                self.assertNotEqual(body(living),body(later))
                self.assertEqual(living.splitlines()[-1],original.splitlines()[-1])
                self.assertEqual(len(living.splitlines()),size[1])
                self.assertEqual(set(map(len,living.splitlines())),{size[0]})

    def test_quiet_controls_and_unavailable_evidence_keep_previous_poses(self):
        for state,options in [('working',{'calm':True}),('working',{'reduced_motion':True}),
                              ('working',{'stale':True}),('unknown',{}),('ended',{})]:
            for size in [(100,32),(24,12)]:
                with self.subTest(state=state,options=options,size=size):
                    new=terminal.render(record(state),*size,now=1000.4,**options)
                    old=terminal.render(record(state),*size,now=1000.4,lively=False,**options)
                    self.assertEqual(new,old)

    def test_observed_arrival_and_return_have_longer_readable_gestures(self):
        for event in ['UserPromptSubmit','PostToolUse','SubagentStop']:
            observation=record(transitions=[{'sequence':2,'event':event,'at':1000,
                                            'key':None if event=='UserPromptSubmit' else 'a'*64,'kind':'execute'}])
            # The previous gesture has expired at 0.95 seconds. The new one
            # is still readable, then settles completely; no event is invented.
            for size in [(100,32)]:
                with self.subTest(event=event):
                    plain=terminal.render(record(),*size,now=1000.95)
                    observed=terminal.render(observation,*size,now=1000.95)
                    self.assertNotEqual(body(plain),body(observed))
                    self.assertEqual(terminal.render(observation,*size,now=1002),
                                     terminal.render(record(),*size,now=1002))

    def test_waiting_has_less_decorative_movement_than_active_work(self):
        def movement(state):
            frames=[body(terminal.render(record(state),100,32,now=1000+i/10)) for i in range(16)]
            return sum(sum(a!=b for a,b in zip(left,right)) for left,right in zip(frames,frames[1:]))
        self.assertGreater(movement('working'),movement('waiting'))
