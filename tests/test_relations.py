import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'plugins/cyclops-keeper/scripts'
sys.path.insert(0, str(SCRIPTS))
import activity


class RelationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def emit(self, event, **kwargs):
        if True:
            activity.update(self.root, dict(hook_event_name=event, session_id='test',
                                           turn_id='private-turn', **kwargs))
        return json.loads(next((self.root/'activity-face/sessions').glob('*.json')).read_text())

    def test_private_turn_is_hashed_and_public_turn_is_absent(self):
        s = self.emit('UserPromptSubmit')
        self.assertEqual(s['_turn_key'], activity.digest('private-turn'))
        self.assertNotIn('private-turn', json.dumps(s))
        public = activity.public_snapshot(self.root)['sessions'][0]
        self.assertNotIn('turn_id', public)
        self.assertNotIn('_turn_key', public)

    def test_legacy_turn_migrates_without_losing_exact_late_return(self):
        s = self.emit('PreToolUse', tool_use_id='old')
        target = next((self.root/'activity-face/sessions').glob('*.json'))
        s.pop('_turn_key', None); s['turn_id'] = 'private-turn'
        target.write_text(json.dumps(s))
        self.emit('UserPromptSubmit', prompt='not retained')
        s = self.emit('PostToolUse', tool_use_id='old')
        self.assertEqual(s['active_tool_count'], 0)
        self.assertNotIn('turn_id', s)

    def test_relation_overflow_is_explicit_and_retained_returns_still_match(self):
        with patch.object(activity, 'RELATION_LIMIT', 6):
            for i in range(8): s = self.emit('PreToolUse', tool_use_id=str(i))
            self.assertEqual(s['active_tool_count'], 6)
            self.assertTrue(s['relations_incomplete'])
            s = self.emit('PostToolUse', tool_use_id='2')
            self.assertEqual(s['active_tool_count'], 5)
            self.assertTrue(s['relations_incomplete'])
            self.assertNotIn(activity.digest('2'), s['_tools'])

class BoundaryTests(unittest.TestCase):
    def test_snapshot_is_bounded_and_old_pinned_session_is_accessible(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for i in range(132):activity.update(root,dict(hook_event_name='SessionStart',source='startup',session_id=str(i)))
            key=activity.digest('0');os.utime(root/'activity-face/sessions'/(key+'.json'),(1,1))
            result=activity.public_snapshot(root);self.assertEqual(len(result['sessions']),128);self.assertTrue(result['truncated'])
            pinned=activity.public_snapshot(root,session=key);self.assertEqual(pinned['sessions'][0]['session'],key);self.assertFalse(pinned['truncated'])

if __name__=='__main__':unittest.main()
