import concurrent.futures
import fcntl
import importlib.util
import json
import os
import pty
import re
import select
import signal
import struct
import termios
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'plugins/cyclops-keeper/scripts'


class StudioFeedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='codex-face-test-')
        self.data = Path(self.tmp.name)
        self.env = {**os.environ, 'PLUGIN_DATA': str(self.data),
                    'PYTHONDONTWRITEBYTECODE': '1'}

    def tearDown(self):
        self.tmp.cleanup()

    def hook(self, event, session='s1', turn='t1', *, studio_session=None,
             presence_root=None, **extra):
        payload = {'hook_event_name': event, 'session_id': session,
                   'turn_id': turn, **extra}
        env = dict(self.env)
        env.pop('CYCLOPS_SESSION_ID', None)
        env.pop('CYCLOPS_PRESENCE_ROOT', None)
        if studio_session is not None:
            env['CYCLOPS_SESSION_ID'] = studio_session
            env['CYCLOPS_PRESENCE_ROOT'] = str(presence_root or self.data / 'presence-root')
        p = subprocess.run([sys.executable, str(SCRIPTS / 'hook.py')],
                           input=json.dumps(payload), text=True, env=env,
                           capture_output=True, timeout=3)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.strip(), '{}')
        self.assertEqual(p.stderr, '')
        return payload

    def states(self):
        return [json.loads(p.read_text()) for p in
                (self.data / 'activity-face/sessions').glob('*.json')]

    def state(self):
        self.assertEqual(len(self.states()), 1)
        return self.states()[0]

    def public_state(self, session='s1'):
        sys.path.insert(0, str(SCRIPTS))
        import activity
        key = activity.digest(session)
        return next((s for s in activity.public_snapshot(self.data)['sessions']
                     if s['session'] == key), {})

    def test_studio_feed_write_failure_does_not_discard_local_host_event(self):
        blocked_root = self.data / 'not-a-directory'
        blocked_root.write_text('fixture blocker')
        self.hook('UserPromptSubmit', studio_session='studio-blocked',
                  presence_root=blocked_root, prompt='private prompt')
        snapshot = self.public_state()
        self.assertEqual(snapshot['state'], 'working')
        self.assertEqual(snapshot['event'], 'UserPromptSubmit')
        self.assertEqual(len(snapshot['transitions']), 1)
        self.assertFalse((blocked_root / 'studio-blocked').exists())

        # Once the optional destination is usable, the next event retries the
        # pending event together with its own, then ends the worker cleanly.
        blocked_root.unlink()
        blocked_root.mkdir()
        self.hook('SessionEnd', studio_session='studio-blocked',
                  presence_root=blocked_root, turn=None)
        durable = json.loads((blocked_root/'studio-blocked'/'keeper'/'durable.json').read_text())
        self.assertEqual([event['type'] for event in durable['events']],
                         ['turn.receive','session.end'])
        live = json.loads((blocked_root/'studio-blocked'/'keeper'/'live.json').read_text())
        self.assertTrue(live['ended'])

    def test_studio_presence_is_absent_without_explicit_studio_session_ownership(self):
        root=self.data/'presence-root'
        self.hook('SessionStart',source='startup')
        self.hook('UserPromptSubmit')
        self.assertFalse(root.exists())

    def test_studio_feed_uses_keeper_vocabulary_and_hashed_correlated_keys(self):
        import hashlib
        root=self.data/'presence-root'
        kwargs={'studio_session':'studio-safe_1.2','presence_root':root}
        self.hook('SessionStart',source='startup',**kwargs)
        self.hook('UserPromptSubmit',**kwargs)
        self.hook('PreToolUse',tool_use_id='call-alpha',tool_name='Read',**kwargs)
        self.hook('PreToolUse',tool_use_id='call-beta',tool_name='Bash',**kwargs)
        self.hook('PostToolUse',tool_use_id='call-beta',tool_name='Bash',**kwargs)
        self.hook('SessionEnd',turn=None,reason='other',**kwargs)
        folder=root/'studio-safe_1.2'/'keeper'
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            try:
                candidate=json.loads((folder/'durable.json').read_text())
                if candidate.get('seq')==6:break
            except (OSError,ValueError):
                pass
            time.sleep(.04)
        durable=json.loads((folder/'durable.json').read_text())
        live=json.loads((folder/'live.json').read_text())
        self.assertEqual(durable['v'],1)
        self.assertTrue(durable['run'])
        self.assertEqual(durable['seq'],6)
        self.assertEqual([e['type'] for e in durable['events']],
                         ['session.wake','turn.receive','tool.start','tool.start','tool.return','session.end'])
        starts=[e for e in durable['events'] if e['type']=='tool.start']
        returned=next(e for e in durable['events'] if e['type']=='tool.return')
        self.assertEqual(returned['key'],hashlib.sha256(b'call-beta').hexdigest())
        self.assertEqual({e['key'] for e in starts},
                         {hashlib.sha256(x).hexdigest() for x in [b'call-alpha',b'call-beta']})
        self.assertEqual(live['seq'],6)
        self.assertTrue(live['ended'])
        self.assertEqual(live['run'],durable['run'])
        serialized=json.dumps([durable,live])
        for private in ('call-alpha','call-beta','SECRET','tool_name','studio-safe_1.2'):
            self.assertNotIn(private,serialized)
        private_state=json.dumps(self.state())
        self.assertNotIn('studio-safe_1.2',private_state)

    def test_studio_feed_maps_all_host_events_without_copying_raw_payloads(self):
        sys.path.insert(0,str(SCRIPTS))
        import presence_feed
        cases=[
            ({'hook_event_name':'SessionStart','source':'resume'},'session.resume'),
            ({'hook_event_name':'SessionStart','source':'clear'},'session.clear'),
            ({'hook_event_name':'SessionStart','source':'compact'},'session.compact'),
            ({'hook_event_name':'PermissionRequest','tool_name':'Bash'},'approval.request'),
            ({'hook_event_name':'PreCompact','trigger':'manual'},'context.fold'),
            ({'hook_event_name':'PostCompact','trigger':'auto'},'context.unfold'),
            ({'hook_event_name':'SubagentStart','agent_id':'private-agent'},'branch.start'),
            ({'hook_event_name':'SubagentStop','agent_id':'private-agent'},'branch.return'),
            ({'hook_event_name':'Interrupt'},'turn.interrupt'),
            ({'hook_event_name':'Stop'},'turn.stop'),
        ]
        for index,(payload,expected) in enumerate(cases,1):
            with self.subTest(event=payload['hook_event_name']):
                result=presence_feed.event_for_host(payload,index,at=1000+index,
                    key='a'*64 if 'agent_id' in payload else None,
                    kind='execute' if payload.get('tool_name') else None)
                self.assertEqual(result['type'],expected)
                self.assertNotIn('private-agent',json.dumps(result))
                self.assertNotIn('Bash',json.dumps(result))

    def test_studio_presence_flush_cadences_and_heartbeat_shape(self):
        sys.path.insert(0,str(SCRIPTS))
        import presence_feed
        root=self.data/'presence-root'
        record=presence_feed.new_record('studio-1',run='run-1',started_at=100.0)
        record=presence_feed.append_host_event(record,{'hook_event_name':'UserPromptSubmit'},
                                               1,at=100.0)
        self.assertTrue(presence_feed.flush(record,root,studio_session='studio-1',now=100.0,force=True))
        live_path=root/'studio-1'/'keeper'/'live.json'
        before=json.loads(live_path.read_text())
        self.assertEqual(before['aliveAt'],100.0)
        self.assertFalse(presence_feed.flush(record,root,studio_session='studio-1',now=100.2))
        self.assertTrue(presence_feed.flush(record,root,studio_session='studio-1',now=105.0))
        after=json.loads(live_path.read_text())
        self.assertEqual(after['aliveAt'],105.0)
        self.assertEqual(after['seq'],1)
        self.assertFalse(after['ended'])

    def test_studio_live_heartbeat_prunes_old_events_but_keeps_latest(self):
        sys.path.insert(0,str(SCRIPTS))
        import presence_feed
        root=self.data/'presence-root'
        record=presence_feed.new_record('studio-window',run='run-window',started_at=100.0)
        record=presence_feed.append_host_event(record,{'hook_event_name':'SessionStart','source':'startup'},1,at=100.0)
        self.assertTrue(presence_feed.flush(record,root,studio_session='studio-window',now=100.0,force=True))
        record=presence_feed.append_host_event(record,{'hook_event_name':'UserPromptSubmit'},2,at=140.0)
        self.assertTrue(presence_feed.flush(record,root,studio_session='studio-window',now=140.0))
        record=presence_feed.append_host_event(record,{'hook_event_name':'PreToolUse'},3,at=200.0)
        self.assertTrue(presence_feed.flush(record,root,studio_session='studio-window',now=200.0))

        # An idle heartbeat prunes the live minute window even without another host event.
        self.assertTrue(presence_feed.flush(record,root,studio_session='studio-window',now=261.0))
        folder=root/'studio-window'/'keeper'
        live=json.loads((folder/'live.json').read_text())
        durable=json.loads((folder/'durable.json').read_text())
        self.assertEqual([event['type'] for event in live['events']],['tool.start'])
        self.assertEqual([event['type'] for event in durable['events']],
                         ['session.wake','turn.receive','tool.start'])

    def test_studio_full_durable_history_is_not_duplicated_in_private_record(self):
        sys.path.insert(0,str(SCRIPTS))
        import presence_feed
        root=self.data/'presence-root'
        record=presence_feed.new_record('studio-history',run='run-history',started_at=100.0)
        record=presence_feed.append_host_event(record,{'hook_event_name':'SessionStart','source':'startup'},1,at=100.0)
        self.assertTrue(presence_feed.flush(record,root,studio_session='studio-history',now=100.0,force=True))
        self.assertNotIn('events',record)
        self.assertEqual(record['pendingEvents'],[])

        record=presence_feed.append_host_event(record,{'hook_event_name':'UserPromptSubmit'},2,at=102.0)
        self.assertTrue(presence_feed.flush(record,root,studio_session='studio-history',now=102.0))
        self.assertNotIn('events',record)
        durable=json.loads((root/'studio-history'/'keeper'/'durable.json').read_text())
        self.assertEqual([event['type'] for event in durable['events']],
                         ['session.wake','turn.receive'])

    def test_studio_feed_resume_reconciles_sequence_after_durable_commit(self):
        sys.path.insert(0,str(SCRIPTS))
        import presence_feed
        root=self.data/'presence-root'
        record=presence_feed.new_record('studio-recover',run='run-recover',started_at=100.0)
        record=presence_feed.append_host_event(record,{'hook_event_name':'SessionStart','source':'startup'},1,at=100.0)
        self.assertTrue(presence_feed.flush(record,root,studio_session='studio-recover',now=100.0,force=True))

        # A process may stop after publishing the durable snapshot but before its
        # private activity record is replaced; recovery must skip that old seq.
        recovered=presence_feed.new_record('studio-recover',run='run-recover',started_at=100.0)
        presence_feed.reconcile(recovered,root,studio_session='studio-recover')
        self.assertEqual(recovered['seq'],1)
        recovered=presence_feed.append_host_event(recovered,{'hook_event_name':'UserPromptSubmit'},2,at=101.0)
        self.assertTrue(presence_feed.flush(recovered,root,studio_session='studio-recover',now=101.0))
        durable=json.loads((root/'studio-recover'/'keeper'/'durable.json').read_text())
        self.assertEqual([event['seq'] for event in durable['events']],[1,2])
        self.assertEqual([event['type'] for event in durable['events']],['session.wake','turn.receive'])

    def test_studio_worker_only_refreshes_an_identified_producer_and_end_is_recorded(self):
        root=self.data/'presence-root'
        kwargs={'studio_session':'studio-heartbeat','presence_root':root}
        self.hook('SessionStart',source='startup',**kwargs)
        feed=root/'studio-heartbeat'/'keeper'/'live.json'
        before=json.loads(feed.read_text())
        time.sleep(5.25)
        after=json.loads(feed.read_text())
        if self.state().get('_producer'):
            self.assertGreater(after['aliveAt'],before['aliveAt'])
        else:self.assertEqual(after['aliveAt'],before['aliveAt'])
        self.assertEqual(after['seq'],before['seq'])
        self.assertFalse(after['ended'])
        self.hook('SessionEnd',turn=None,**kwargs)
        ended=json.loads(feed.read_text())
        self.assertTrue(ended['ended'])

    def test_external_fifo_is_refused_without_losing_local_activity(self):
        root = self.data / 'feeds'
        folder = root / 'studio-fifo' / 'keeper'
        folder.mkdir(parents=True)
        os.mkfifo(folder / 'durable.json')
        self.hook('UserPromptSubmit', studio_session='studio-fifo', presence_root=root)
        self.assertEqual(self.public_state()['state'], 'working')
        self.assertEqual(self.state()['_presence_feed']['pendingEvents'][0]['type'], 'turn.receive')

    def test_destination_change_revokes_previous_binding(self):
        self.hook('SessionStart', source='startup', studio_session='studio-a')
        before = self.state()
        self.hook('UserPromptSubmit', studio_session='studio-a', presence_root=self.data/'other-root')
        after = self.state()
        self.assertNotEqual(before['_presence_binding'], after['_presence_binding'])
        self.assertNotEqual(before['_presence_feed']['run'], after['_presence_feed']['run'])
        self.hook('UserPromptSubmit', studio_session='studio-b', presence_root=self.data/'other-root')
        self.assertNotEqual(after['_presence_binding'], self.state()['_presence_binding'])
