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


class FaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='keeper-test-')
        self.data = Path(self.tmp.name)
        self.env = {**os.environ, 'PLUGIN_DATA': str(self.data),
                    'PYTHONDONTWRITEBYTECODE': '1'}

    def tearDown(self):
        self.tmp.cleanup()

    def hook(self, event, session='s1', turn='t1', *, extra_env=None, **extra):
        payload = {'hook_event_name': event, 'session_id': session,
                   'turn_id': turn, **extra}
        env = {**self.env, **(extra_env or {})}
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

    def test_every_declared_event_maps_without_claiming_semantic_success(self):
        for event, state, extra in [
            ('SessionStart', 'idle', {'source': 'startup'}),
            ('UserPromptSubmit', 'working', {'prompt': 'private text'}),
            ('PreToolUse', 'tool', {'tool_use_id': 'c1', 'tool_name': 'Bash'}),
            ('PermissionRequest', 'waiting', {'tool_name': 'Bash'}),
            ('PostToolUse', 'working', {'tool_use_id': 'c1', 'tool_name': 'Bash'}),
            ('Stop', 'stopped', {'stop_hook_active': False}),
            ('UserPromptSubmit', 'working', {}),
            ('Interrupt', 'interrupted', {}),
            ('SessionEnd', 'ended', {'reason': 'other'}),
        ]:
            with self.subTest(event=event):
                self.hook(event, **extra)
                self.assertEqual(self.state()['state'], state)
                self.assertEqual(self.state()['event'], event)

    def test_parallel_tool_completion_does_not_clear_other_activity(self):
        self.hook('UserPromptSubmit')
        self.hook('PreToolUse', tool_use_id='one')
        self.hook('PreToolUse', tool_use_id='two')
        self.hook('PreToolUse', tool_use_id='two')
        self.hook('PostToolUse', tool_use_id='one')
        self.assertEqual(self.state()['state'], 'tool')
        self.assertEqual(self.state()['active_tool_count'], 1)
        self.hook('PostToolUse', tool_use_id='two')
        self.assertEqual(self.state()['state'], 'working')

    def test_late_completion_cannot_resurrect_an_interrupted_turn(self):
        self.hook('UserPromptSubmit')
        self.hook('PreToolUse', tool_use_id='old')
        self.hook('Interrupt')
        self.hook('PostToolUse', tool_use_id='old')
        self.assertEqual(self.state()['state'], 'interrupted')
        self.hook('UserPromptSubmit', turn='t2')
        self.hook('PostToolUse', turn='t1', tool_use_id='old')
        self.assertEqual(self.state()['_turn_key'], __import__('hashlib').sha256(b't2').hexdigest())
        self.assertEqual(self.state()['event'], 'UserPromptSubmit')

    def test_session_resume_can_accept_tools_from_an_existing_turn(self):
        self.hook('SessionStart', turn=None, source='resume')
        self.hook('PreToolUse', turn='existing-turn', tool_use_id='c1')
        self.assertEqual(self.state()['state'], 'tool')

    def test_sessions_and_hostile_identifiers_are_isolated(self):
        self.hook('UserPromptSubmit', session='../../outside')
        self.hook('SessionStart', session='different', source='startup')
        self.assertEqual(len(self.states()), 2)
        self.assertEqual({s['state'] for s in self.states()}, {'working', 'idle'})
        self.assertFalse((self.data / 'outside').exists())

    def test_payload_text_is_never_retained(self):
        self.hook('PostToolUse', tool_use_id='x', prompt='SECRET-PROMPT',
                  tool_input={'command': 'SECRET-COMMAND'},
                  tool_response={'isError': True, 'content': 'SECRET-OUTPUT'},
                  transcript_path='/SECRET-TRANSCRIPT', cwd='/SECRET-PATH',
                  last_assistant_message='SECRET-MESSAGE')
        for p in self.data.rglob('*'):
            if p.is_file():
                self.assertNotIn('SECRET-', p.read_text())
        self.assertNotIn(self.state()['state'], ['success', 'error', 'reading'])

    def test_session_resume_reopens_terminal_states_and_preserves_unresolved_relations(self):
        import hashlib
        for prior_state, prior_event in [('stopped', 'Stop'),
                                         ('interrupted', 'Interrupt'),
                                         ('ended', 'SessionEnd')]:
            session = f'resume-{prior_state}'
            with self.subTest(prior_state=prior_state):
                self.hook('UserPromptSubmit', session=session, turn='old-turn')
                self.hook('PreToolUse', session=session, turn='old-turn',
                          tool_use_id='resume-call', tool_name='Read')
                self.hook('SubagentStart', session=session, turn='old-turn',
                          agent_id='resume-branch')
                self.hook(prior_event, session=session, turn='old-turn')
                self.hook('SessionStart', session=session, turn=None, source='resume')

                resumed = self.public_state(session)
                self.assertEqual(resumed['state'], 'idle')
                self.assertEqual(resumed['event'], 'SessionStart')
                self.assertNotIn('turn_id', resumed)
                self.assertNotIn('_turn_key', resumed)
                self.assertEqual({item['key'] for item in resumed['active_tools']},
                                 {hashlib.sha256(b'resume-call').hexdigest()})
                self.assertEqual({item['key'] for item in resumed['active_subagents']},
                                 {hashlib.sha256(b'resume-branch').hexdigest()})

                self.hook('PostToolUse', session=session, turn='old-turn',
                          tool_use_id='resume-call', tool_name='Read')
                after_tool = self.public_state(session)
                self.assertEqual(after_tool['active_tools'], [])
                self.assertEqual(len(after_tool['active_subagents']), 1)
                self.hook('SubagentStop', session=session, turn='old-turn',
                          agent_id='resume-branch')
                after_branch = self.public_state(session)
                self.assertEqual(after_branch['active_subagents'], [])
                self.assertEqual(after_branch['active_tool_count'], 0)

    def test_compaction_session_start_does_not_fabricate_idle(self):
        self.hook('UserPromptSubmit')
        self.hook('SessionStart', source='compact')
        self.assertEqual(self.state()['state'], 'working')

    def public_state(self, session='s1'):
        sys.path.insert(0, str(SCRIPTS))
        import activity
        key = activity.digest(session)
        return next((s for s in activity.public_snapshot(self.data)['sessions']
                     if s['session'] == key), {})

    def test_documented_twelve_events_are_accepted(self):
        for i, (event, extra) in enumerate([
            ('PreCompact', {'trigger': 'manual'}),
            ('PostCompact', {'trigger': 'auto'}),
            ('SubagentStart', {'agent_id': 'agent-a', 'agent_type': 'explorer'}),
            ('SubagentStop', {'agent_id': 'agent-a', 'agent_type': 'explorer',
                              'last_assistant_message': 'PRIVATE-RESULT'}),
        ]):
            session = f'event-{i}'
            with self.subTest(event=event):
                self.hook(event, session=session, **extra)
                self.assertEqual(self.public_state(session).get('event'), event)
        self.hook('SessionStart', session='compact-start', turn=None, source='compact')
        self.assertEqual(self.public_state('compact-start').get('event'), 'SessionStart')

    def test_out_of_order_tool_returns_resolve_only_their_matching_tethers(self):
        import hashlib
        self.hook('UserPromptSubmit')
        self.hook('PreToolUse', tool_use_id='first', tool_name='Read')
        self.hook('PreToolUse', tool_use_id='second', tool_name='Bash')
        snapshot = self.public_state()
        self.assertIn('active_tools', snapshot)
        first = hashlib.sha256(b'first').hexdigest()
        second = hashlib.sha256(b'second').hexdigest()
        self.assertEqual({t['key'] for t in snapshot['active_tools']}, {first, second})
        self.hook('PostToolUse', tool_use_id='second', tool_name='Bash')
        snapshot = self.public_state()
        self.assertEqual([t['key'] for t in snapshot['active_tools']], [first])
        self.assertEqual(snapshot['active_tool_count'], 1)
        self.hook('PostToolUse', tool_use_id='first', tool_name='Read')
        snapshot = self.public_state()
        self.assertEqual(snapshot['active_tools'], [])
        self.assertEqual(snapshot['state'], 'working')

    def test_old_turn_return_retracts_its_tether_without_replacing_new_turn(self):
        import hashlib
        self.hook('UserPromptSubmit', turn='old-turn')
        self.hook('PreToolUse', turn='old-turn', tool_use_id='old-call', tool_name='Bash')
        self.hook('UserPromptSubmit', turn='new-turn')
        self.assertEqual(self.public_state()['active_tool_count'], 1)
        self.hook('PostToolUse', turn='old-turn', tool_use_id='old-call', tool_name='Bash')
        snapshot = self.public_state()
        self.assertNotIn('turn_id', snapshot)
        self.assertNotIn('_turn_key', snapshot)
        self.assertEqual(snapshot['event'], 'UserPromptSubmit')
        self.assertEqual(snapshot['state'], 'working')
        self.assertEqual(snapshot['active_tools'], [])
        self.assertNotIn(hashlib.sha256(b'old-call').hexdigest(),
                         [t['key'] for t in snapshot['active_tools']])

    def test_session_end_keeps_each_unresolved_tool_until_its_own_return(self):
        import hashlib
        self.hook('UserPromptSubmit')
        self.hook('PreToolUse', tool_use_id='slow-a', tool_name='Read')
        self.hook('PreToolUse', tool_use_id='slow-b', tool_name='Bash')
        self.hook('SessionEnd', turn=None)
        ended=self.public_state()
        self.assertEqual(ended['state'],'ended')
        self.assertEqual({item['key'] for item in ended['active_tools']},
                         {hashlib.sha256(x.encode()).hexdigest() for x in ['slow-a','slow-b']})
        self.hook('PostToolUse', tool_use_id='slow-b', tool_name='Bash')
        returned=self.public_state()
        self.assertEqual(returned['state'],'ended')
        self.assertEqual([item['key'] for item in returned['active_tools']],
                         [hashlib.sha256(b'slow-a').hexdigest()])
        self.hook('PostToolUse', tool_use_id='slow-a', tool_name='Read')
        self.assertEqual(self.public_state()['active_tools'],[])

    def test_unmatched_return_has_no_tether_identity(self):
        self.hook('UserPromptSubmit')
        self.hook('PreToolUse', tool_use_id='tracked')
        self.hook('PostToolUse', tool_use_id='unknown')
        snapshot=self.public_state()
        self.assertEqual(snapshot['active_tool_count'],1)
        self.assertIsNone(snapshot['transitions'][-1]['key'])

    def test_fixture_can_build_and_clear_parallel_out_of_order_scenario(self):
        sys.path.insert(0,str(SCRIPTS))
        import activity
        self.hook('UserPromptSubmit',session='unrelated-live-session')
        fixture_data=self.data/'fixture-only'
        fixture_env={**self.env,'KEEPER_FIXTURE_DATA':str(fixture_data)}
        fixture=ROOT/'tools/keeper-fixture.py'
        built=subprocess.run([sys.executable,str(fixture),'overlap','--fixture','visual-review'],
                             env=fixture_env,text=True,capture_output=True,timeout=5)
        self.assertEqual((built.returncode,built.stderr),(0,''),built.stderr)
        snapshot=activity.public_snapshot(fixture_data)['sessions'][0]
        self.assertEqual(snapshot['active_tool_count'],2)
        self.assertEqual(snapshot['active_subagent_count'],2)
        fixture_session=snapshot['session']
        returned=subprocess.run([sys.executable,str(fixture),'PostToolUse','--fixture','visual-review',
                                 '--tool-id','service-c'],env=fixture_env,text=True,
                                capture_output=True,timeout=5)
        self.assertEqual(returned.returncode,0,returned.stderr)
        snapshot=activity.public_snapshot(fixture_data)['sessions'][0]
        self.assertEqual(snapshot['active_tool_count'],1)
        clear=subprocess.run([sys.executable,str(fixture),'clear','--fixture','visual-review'],
                             env=fixture_env,text=True,capture_output=True,timeout=5)
        self.assertEqual(clear.returncode,0,clear.stderr)
        self.assertEqual(activity.public_snapshot(fixture_data)['sessions'],[])
        self.assertTrue(any(item['session']==activity.digest('unrelated-live-session')
                            for item in activity.public_snapshot(self.data)['sessions']))
        self.assertFalse((fixture_data/'activity-face/sessions'/(fixture_session+'.json')).exists())

    def test_parallel_subagents_are_independently_tracked(self):
        import hashlib
        self.hook('UserPromptSubmit')
        self.hook('SubagentStart', agent_id='agent-a', agent_type='explorer')
        self.hook('SubagentStart', agent_id='agent-b', agent_type='reviewer')
        snapshot = self.public_state()
        self.assertIn('active_subagents', snapshot)
        first = hashlib.sha256(b'agent-a').hexdigest()
        second = hashlib.sha256(b'agent-b').hexdigest()
        self.assertEqual({a['key'] for a in snapshot['active_subagents']}, {first, second})
        self.hook('SubagentStop', agent_id='agent-b', agent_type='reviewer')
        self.assertEqual([a['key'] for a in self.public_state()['active_subagents']], [first])
        self.hook('SubagentStop', agent_id='agent-a', agent_type='explorer')
        self.assertEqual(self.public_state()['active_subagents'], [])

    def test_event_ribbon_is_bounded_and_contains_no_payload_or_raw_ids(self):
        self.hook('UserPromptSubmit', prompt='PRIVATE-RIBBON-PROMPT')
        for i in range(39):
            self.hook('PreToolUse', tool_use_id=f'private-id-{i}', tool_name='Bash',
                      tool_input={'command': 'PRIVATE-RIBBON-COMMAND'})
            self.hook('PostToolUse', tool_use_id=f'private-id-{i}', tool_name='Bash',
                      tool_response={'content': 'PRIVATE-RIBBON-OUTPUT'})
        snapshot = self.public_state()
        self.assertIn('transitions', snapshot)
        self.assertEqual(len(snapshot['transitions']), 32)
        self.assertEqual([x['sequence'] for x in snapshot['transitions']],
                         list(range(snapshot['sequence'] - 31, snapshot['sequence'] + 1)))
        public_text = json.dumps(snapshot)
        for secret in ['PRIVATE-RIBBON-', 'private-id-']:
            self.assertNotIn(secret, public_text)
        for path in (self.data / 'activity-face/sessions').glob('*.json'):
            stored_text = path.read_text()
            for secret in ['PRIVATE-RIBBON-', 'private-id-']:
                self.assertNotIn(secret, stored_text)

    def test_tool_names_reduce_to_finite_safe_kinds(self):
        self.hook('UserPromptSubmit')
        samples = [('inspect-tool', 'Read', 'inspect'),
                   ('change-tool', 'apply_patch', 'change'),
                   ('execute-tool', 'Bash', 'execute'),
                   ('service-tool', 'mcp__filesystem__read_file', 'service'),
                   ('other-tool', 'private_internal_name', 'other')]
        for call, name, _kind in samples:
            self.hook('PreToolUse', tool_use_id=call, tool_name=name)
        snapshot = self.public_state()
        self.assertIn('active_tools', snapshot)
        self.assertEqual({t['kind'] for t in snapshot['active_tools']},
                         {'inspect', 'change', 'execute', 'service', 'other'})
        self.assertNotIn('private_internal_name', json.dumps(snapshot))
        self.assertNotIn('mcp__filesystem__read_file', json.dumps(snapshot))

    def test_invalid_unknown_and_unwritable_inputs_are_quiet_and_nonblocking(self):
        oversized = json.dumps({'hook_event_name': 'Stop', 'session_id': 's',
                                'ignored': 'x' * (2 * 1024 * 1024)})
        for payload in ['broken', '[]', '{}', json.dumps({'hook_event_name': 'Fake'}), oversized]:
            p = subprocess.run([sys.executable, str(SCRIPTS / 'hook.py')],
                               input=payload, text=True, capture_output=True,
                               env=self.env, timeout=3)
            self.assertEqual((p.returncode, p.stdout.strip(), p.stderr), (0, '{}', ''))
        self.assertEqual(self.states(), [])
        blocker = self.data / 'file-not-directory'
        blocker.write_text('keep')
        self.env['PLUGIN_DATA'] = str(blocker)
        self.hook('Stop')
        self.assertEqual(blocker.read_text(), 'keep')

    def test_concurrent_writers_keep_all_observed_tool_ids(self):
        self.hook('UserPromptSubmit')
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(lambda i: self.hook('PreToolUse', tool_use_id=str(i)), range(16)))
        self.assertEqual(self.state()['active_tool_count'], 16)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(lambda i: self.hook('PostToolUse', tool_use_id=str(i)), range(16)))
        self.assertEqual(self.state()['active_tool_count'], 0)
        self.assertEqual(self.state()['state'], 'working')

    def test_fresh_unknown_stale_and_private_fields_are_handled_by_viewer(self):
        sys.path.insert(0, str(SCRIPTS))
        spec = importlib.util.find_spec('activity')
        self.assertIsNotNone(spec, 'Activity module must exist')
        import activity
        self.assertEqual(activity.public_snapshot(self.data)['sessions'], [])
        self.hook('PreToolUse', tool_use_id='secret-call-id')
        snapshot = activity.public_snapshot(self.data)
        self.assertFalse(snapshot['sessions'][0]['stale'])
        self.assertNotIn('_tools', snapshot['sessions'][0])
        self.assertNotIn('secret-call-id', json.dumps(snapshot))
        old = activity.public_snapshot(self.data, now=time.time() + 301)
        self.assertTrue(old['sessions'][0]['stale'])
        self.assertEqual(old['sessions'][0]['state'], 'tool')

    def test_viewer_is_read_only_loopback_and_does_not_serve_arbitrary_files(self):
        p = subprocess.Popen([sys.executable, str(SCRIPTS / 'view.py'),
                              '--data', str(self.data), '--port', '0'],
                             text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             env=self.env)
        try:
            url = p.stdout.readline().strip()
            self.assertRegex(url, r'^http://127\.0\.0\.1:\d+/$')
            with urllib.request.urlopen(url, timeout=2) as r:
                page = r.read()
                self.assertIn(b'<canvas', page)
                self.assertIn(b'keeper.js', page)
                self.assertNotIn(b'<select', page)
                self.assertNotIn(b'keeper-iris', page)
            with urllib.request.urlopen(url + 'api/state', timeout=2) as r:
                self.assertEqual(json.load(r)['sessions'], [])
                self.assertEqual(r.headers['Cache-Control'], 'no-store')
            for path, kind in [('keeper.js', 'javascript'), ('keeper.css', 'text/css'),
                               ('keeper.svg', 'image/svg+xml'), ('presence-state.mjs', 'javascript'), ('colour-engine.js', 'javascript')]:
                with urllib.request.urlopen(url + path, timeout=2) as r:
                    self.assertIn(kind, r.headers['Content-Type'])
                    self.assertGreater(len(r.read()), 100)
            for path in ['../README.md', 'scripts/hook.py', 'keeper-art.png']:
                with self.assertRaises(urllib.error.HTTPError) as e:
                    urllib.request.urlopen(url + path, timeout=2)
                self.assertEqual(e.exception.code, 404)
            req = urllib.request.Request(url + 'api/state', headers={'Host': 'evil.example'})
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(req, timeout=2)
            self.assertEqual(e.exception.code, 403)
            req = urllib.request.Request(url + 'api/state', data=b'{}')
            with self.assertRaises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(req, timeout=2)
            self.assertEqual(e.exception.code, 405)
        finally:
            p.terminate()
            p.communicate(timeout=3)

    def test_viewer_accepts_only_explicit_calm_query_value(self):
        p=subprocess.Popen([sys.executable,str(SCRIPTS/'view.py'),'--data',str(self.data),'--port','0'],
                           text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=self.env)
        try:
            url=p.stdout.readline().strip()
            with urllib.request.urlopen(url+'?calm=1',timeout=2) as response:
                self.assertEqual(response.status,200)
                self.assertIn(b'keeper.js',response.read())
            for query in ['?calm=0','?calm=1&calm=1','?calm=1&unexpected=1']:
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(url+query,timeout=2)
                self.assertEqual(error.exception.code,404)
        finally:
            p.terminate();p.communicate(timeout=3)

    def test_test_feed_embeds_only_the_sanitized_fixture_snapshot(self):
        import base64
        self.hook('UserPromptSubmit',tool_use_id='PRIVATE-FIXTURE-ID',prompt='PRIVATE-FIXTURE-PROMPT')
        self.hook('PreToolUse',tool_use_id='PRIVATE-FIXTURE-CALL',tool_name='Read')
        p=subprocess.Popen([sys.executable,str(SCRIPTS/'view.py'),'--data',str(self.data),
                            '--port','0','--test-feed'],text=True,stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,env=self.env)
        try:
            url=p.stdout.readline().strip()
            with urllib.request.urlopen(url,timeout=2) as response:page=response.read().decode()
            match=re.search(r'<meta name="keeper-fixture" content="([A-Za-z0-9+/=]*)">',page)
            self.assertIsNotNone(match)
            snapshot=json.loads(base64.b64decode(match.group(1)))
            self.assertTrue(snapshot['test_feed'])
            self.assertEqual(snapshot['sessions'][0]['active_tool_count'],1)
            self.assertNotIn('PRIVATE-FIXTURE-',page)
            self.assertNotIn('PRIVATE-FIXTURE-',json.dumps(snapshot))
        finally:
            p.terminate();p.communicate(timeout=3)

    def test_browser_session_pin_never_falls_back_to_another_chat(self):
        import hashlib
        pinned = hashlib.sha256(b'this-chat').hexdigest()
        self.hook('UserPromptSubmit', session='this-chat')
        self.hook('PreToolUse', session='other-chat', tool_use_id='unrelated')
        p = subprocess.Popen([sys.executable, str(SCRIPTS / 'view.py'),
                              '--data', str(self.data), '--session', pinned, '--test-feed'],
                             text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=self.env)
        try:
            url = p.stdout.readline().strip()
            self.assertRegex(url, r'^http://127\.0\.0\.1:\d+/$', 'A pinned viewer must start')
            with urllib.request.urlopen(url + 'api/state', timeout=2) as r:
                data = json.load(r)
            self.assertEqual([s['session'] for s in data['sessions']], [pinned])
            self.assertTrue(data['test_feed'])
            self.assertEqual(data['selection'], 'pinned')
            (self.data / 'activity-face/sessions' / (pinned + '.json')).unlink()
            with urllib.request.urlopen(url + 'api/state', timeout=2) as r:
                self.assertEqual(json.load(r)['sessions'], [])
        finally:
            p.terminate()
            p.communicate(timeout=3)

    def test_terminal_face_scales_and_keeps_only_one_status_line(self):
        sys.path.insert(0, str(SCRIPTS))
        self.assertIsNotNone(importlib.util.find_spec('terminal'), 'Full-screen renderer must exist')
        import terminal
        for width, height in [(80, 24), (160, 48), (24, 8)]:
            for state in ['idle', 'working', 'tool', 'waiting', 'stopped', 'interrupted', 'ended', 'unknown']:
                frame = terminal.render(state, width, height, unicode=False)
                lines = frame.split('\n')
                self.assertEqual(len(lines), height)
                self.assertTrue(all(len(line) == width for line in lines))
                self.assertTrue(frame.isascii())
                occupied = [i for i, line in enumerate(lines[:-1]) if line.strip()]
                self.assertGreaterEqual(len(occupied), max(3, height // 2))
                self.assertNotIn('KEEPER', '\n'.join(lines[:-1]))
                self.assertIn('KEEPER', lines[-1])

    def terminal_snapshot(self, state='tool', event='PreToolUse', tools=None, agents=None, transitions=None):
        return {'schema':'activity-face/v1','state':state,'event':event,'updated_at':1000.0,
                'sequence':20,'stale':False,'active_tools':tools or [],
                'active_subagents':agents or [],'active_tool_count':len(tools or []),
                'active_subagent_count':len(agents or []),'transitions':transitions or []}

    def test_balanced_and_focus_are_distinct_responsive_compositions(self):
        sys.path.insert(0,str(SCRIPTS))
        import terminal
        snapshot=self.terminal_snapshot('working','UserPromptSubmit')
        for width,height in [(80,24),(160,48),(24,8),(12,5),(4,2)]:
            balanced=terminal.render(snapshot,width,height,mode='balanced',now=1001)
            focus=terminal.render(snapshot,width,height,mode='focus',now=1001)
            for frame in (balanced,focus):
                lines=frame.split('\n')
                self.assertEqual(len(lines),height)
                self.assertTrue(all(len(line)==width for line in lines))
            if width>=24 and height>=8:self.assertNotEqual(balanced,focus)

    def test_focus_resize_never_exceeds_any_terminal_dimension(self):
        sys.path.insert(0,str(SCRIPTS))
        import terminal
        snapshot=self.terminal_snapshot('tool','PreToolUse')
        for width,height in [(1,1),(2,2),(6,3),(16,6),(240,80),(50,80),(140,12)]:
            frame=terminal.render(snapshot,width,height,mode='focus',now=1001)
            lines=frame.splitlines()
            self.assertEqual((len(lines),set(map(len,lines))),(height,{width}))

    def test_each_active_tool_has_a_stable_bounded_tether(self):
        import hashlib
        sys.path.insert(0,str(SCRIPTS))
        import terminal
        first={'key':hashlib.sha256(b'call-one').hexdigest(),'kind':'inspect','sequence':4}
        second={'key':hashlib.sha256(b'call-two').hexdigest(),'kind':'execute','sequence':7}
        a=terminal.render(self.terminal_snapshot('tool','PreToolUse',[first]),100,28,mode='focus',now=1001)
        b=terminal.render(self.terminal_snapshot('tool','PreToolUse',[second]),100,28,mode='focus',now=1001)
        same_inspect=terminal.render(self.terminal_snapshot('tool','PreToolUse',
            [{'key':first['key'],'kind':'inspect','sequence':4}]),100,28,mode='focus',now=1001)
        same_execute=terminal.render(self.terminal_snapshot('tool','PreToolUse',
            [{'key':first['key'],'kind':'execute','sequence':4}]),100,28,mode='focus',now=1001)
        together=terminal.render(self.terminal_snapshot('tool','PreToolUse',[first,second]),100,28,mode='focus',now=1001)
        self.assertNotEqual(a,b)
        self.assertNotEqual(same_inspect,same_execute)
        self.assertGreater(sum(c!=' ' for c in '\n'.join(together.splitlines()[:-1])),
                           max(sum(c!=' ' for c in '\n'.join(a.splitlines()[:-1])),
                               sum(c!=' ' for c in '\n'.join(b.splitlines()[:-1]))))
        self.assertNotIn(first['key'],together)
        self.assertNotIn(second['key'],together)

    def test_dense_tools_and_satellites_stay_organized(self):
        sys.path.insert(0,str(SCRIPTS))
        import terminal
        tools=[{'key':f'{i:064x}','kind':['inspect','change','execute','service','other'][i%5],
                'sequence':i+1} for i in range(24)]
        agents=[{'key':f'{i+100:064x}','sequence':i+30} for i in range(8)]
        frame=terminal.render(self.terminal_snapshot('branching','SubagentStart',tools,agents),
                              120,32,mode='focus',now=1001)
        self.assertEqual(len(frame.splitlines()),32)
        self.assertGreater(sum(c!=' ' for c in '\n'.join(frame.splitlines()[:-1])),50)
        self.assertNotIn('×',frame)  # density is individually routed, not an intensity badge

    def test_calm_and_reduced_motion_keep_semantics_and_freeze_decoration(self):
        sys.path.insert(0,str(SCRIPTS))
        import terminal
        snapshot=self.terminal_snapshot('tool','PreToolUse',[
            {'key':f'{i:064x}','kind':'change','sequence':i+1} for i in range(3)])
        calm=terminal.render(snapshot,100,28,mode='focus',now=1001,calm=True)
        reduced_a=terminal.render(snapshot,100,28,mode='focus',now=1001,reduced_motion=True)
        reduced_b=terminal.render(snapshot,100,28,mode='focus',now=1080,reduced_motion=True)
        self.assertEqual(reduced_a,reduced_b)
        self.assertEqual(len(calm.splitlines()),28)
        self.assertGreater(sum(c!=' ' for c in '\n'.join(calm.splitlines()[:-1])),20)

    def test_tool_and_branch_returns_render_after_relations_leave_in_both_modes(self):
        import hashlib
        import terminal
        tool_a = hashlib.sha256(b'return-call-a').hexdigest()
        tool_b = hashlib.sha256(b'return-call-b').hexdigest()
        branch_a = hashlib.sha256(b'return-branch-a').hexdigest()
        branch_b = hashlib.sha256(b'return-branch-b').hexdigest()
        transitions = [
            {'sequence':21,'event':'PostToolUse','at':1000.0,'key':tool_b,'kind':'execute'},
            {'sequence':22,'event':'SubagentStop','at':1000.2,'key':branch_a,'kind':None},
            {'sequence':23,'event':'PostToolUse','at':1000.3,'key':tool_a,'kind':'inspect'},
            {'sequence':24,'event':'SubagentStop','at':1000.4,'key':branch_b,'kind':None},
        ]
        empty = self.terminal_snapshot('working','SessionStart')
        now = 1000.55
        for mode in ('balanced','focus'):
            with self.subTest(mode=mode):
                baseline = terminal.render(empty,100,28,mode=mode,now=now,calm=True)
                returned = terminal.render(self.terminal_snapshot(
                    'working','SessionStart',transitions=transitions),
                    100,28,mode=mode,now=now,calm=True)
                self.assertNotEqual(returned,baseline)
                for transition in transitions:
                    single = terminal.render(self.terminal_snapshot(
                        'working','SessionStart',transitions=[transition]),
                        100,28,mode=mode,now=now,calm=True)
                    self.assertNotEqual(single,baseline)
                    self.assertNotEqual(single,returned)
                expired = terminal.render(self.terminal_snapshot(
                    'working','SessionStart',transitions=transitions),
                    100,28,mode=mode,now=1002.0,calm=True)
                expired_baseline = terminal.render(empty,100,28,mode=mode,now=1002.0,calm=True)
                self.assertEqual(expired,expired_baseline)
                reduced = terminal.render(self.terminal_snapshot(
                    'working','SessionStart',transitions=transitions),
                    100,28,mode=mode,now=now,calm=True,reduced_motion=True)
                reduced_baseline = terminal.render(empty,100,28,mode=mode,now=now,
                                                   calm=True,reduced_motion=True)
                self.assertEqual(reduced,reduced_baseline)

    def test_ascii_fallback_and_status_fit_narrow_viewports(self):
        sys.path.insert(0,str(SCRIPTS))
        import terminal
        frame=terminal.render(self.terminal_snapshot('interrupted','Interrupt'),16,6,
                              mode='focus',unicode=False)
        self.assertTrue(frame.isascii())
        self.assertTrue(all(len(line)==16 for line in frame.splitlines()))
        self.assertIn('KEEPER',frame.splitlines()[-1])

    def test_focus_escape_restores_terminal_state(self):
        master,slave=pty.openpty()
        process=subprocess.Popen([str(ROOT/'keeper'),'focus','--data',str(self.data)],
                                 stdin=slave,stdout=slave,stderr=slave,
                                 env={**self.env,'TERM':'xterm-256color'})
        os.close(slave);output=b''
        try:
            deadline=time.monotonic()+3
            while time.monotonic()<deadline and b'\x1b[?25l' not in output:
                if select.select([master],[],[],.1)[0]:
                    try: output+=os.read(master,65536)
                    except OSError: break
            self.assertIn(b'\x1b[?1049h',output)
            os.write(master,b'\x1b')
            process.wait(timeout=3)
            if select.select([master],[],[],.2)[0]: output+=os.read(master,65536)
            self.assertEqual(process.returncode,0)
            self.assertIn(b'\x1b[?25h\x1b[?1049l',output)
        finally:
            if process.poll() is None: process.kill();process.wait()
            os.close(master)

    def test_focus_ctrl_c_restores_terminal_state(self):
        master,slave=pty.openpty()
        process=subprocess.Popen([str(ROOT/'keeper'),'focus','--data',str(self.data),'--no-colour'],
                                 stdin=slave,stdout=slave,stderr=slave,
                                 env={**self.env,'TERM':'xterm-256color'})
        os.close(slave);output=b''
        try:
            deadline=time.monotonic()+3
            while time.monotonic()<deadline and b'\x1b[?25l' not in output:
                if select.select([master],[],[],.1)[0]:
                    try:output+=os.read(master,65536)
                    except OSError:break
            self.assertIn(b'\x1b[?1049h',output)
            process.send_signal(signal.SIGINT)
            process.wait(timeout=3)
            if select.select([master],[],[],.2)[0]:output+=os.read(master,65536)
            self.assertEqual(process.returncode,0)
            self.assertIn(b'\x1b[?25h\x1b[?1049l',output)
        finally:
            if process.poll() is None:process.kill();process.wait()
            os.close(master)

    def test_focus_calms_and_reduces_motion_from_keyboard(self):
        master,slave=pty.openpty()
        process=subprocess.Popen([str(ROOT/'keeper'),'focus','--data',str(self.data),'--no-colour'],
                                 stdin=slave,stdout=slave,stderr=slave,
                                 env={**self.env,'TERM':'xterm-256color'})
        os.close(slave);output=b''
        def collect_until(token,seconds=3):
            nonlocal output
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline and token not in output:
                if select.select([master],[],[],.1)[0]:
                    try:output+=os.read(master,65536)
                    except OSError:break
            return token in output
        try:
            self.assertTrue(collect_until(b'\x1b[?25l'))
            os.write(master,b'c');self.assertTrue(collect_until(b'CALM'))
            os.write(master,b'r');self.assertTrue(collect_until(b'CALM REDUCED'))
            os.write(master,b'q');process.wait(timeout=3)
            if select.select([master],[],[],.2)[0]:output+=os.read(master,65536)
            self.assertIn(b'\x1b[?25h\x1b[?1049l',output)
        finally:
            if process.poll() is None:process.kill();process.wait()
            os.close(master)

    def test_focus_resize_while_active_redraws_with_new_terminal_bounds(self):
        self.hook('UserPromptSubmit')
        self.hook('PreToolUse',tool_use_id='resize-call',tool_name='Bash')
        master,slave=pty.openpty()
        fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',24,80,0,0))
        process=subprocess.Popen([str(ROOT/'keeper'),'focus','--data',str(self.data),'--no-colour'],
                                 stdin=slave,stdout=slave,stderr=slave,
                                 env={**self.env,'TERM':'xterm-256color'})
        os.close(slave);output=b''
        try:
            deadline=time.monotonic()+3
            while time.monotonic()<deadline and output.count(b'\x1b[H')<1:
                if select.select([master],[],[],.1)[0]:
                    try:output+=os.read(master,65536)
                    except OSError:break
            self.assertGreaterEqual(output.count(b'\x1b[H'),1)
            before=output.count(b'\x1b[H')
            fcntl.ioctl(master,termios.TIOCSWINSZ,struct.pack('HHHH',9,30,0,0))
            deadline=time.monotonic()+3
            while time.monotonic()<deadline and output.count(b'\x1b[H')<=before:
                if select.select([master],[],[],.1)[0]:
                    try:output+=os.read(master,65536)
                    except OSError:break
            frames=output.rsplit(b'\x1b[H',1)[-1].split(b'\x1b[0m',1)[0]
            rows=[part.strip(b'\r\n').decode('utf-8') for part in frames.split(b'\x1b[K')[:-1]]
            self.assertEqual(len(rows),9)
            self.assertTrue(all(len(row)==29 for row in rows),[len(row) for row in rows])
        finally:
            if process.poll() is None:
                os.write(master,b'q');process.wait(timeout=3)
            os.close(master)

    def test_complete_json_does_not_wait_for_stdin_eof(self):
        p = subprocess.Popen([sys.executable, str(SCRIPTS / 'hook.py')],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, env=self.env)
        try:
            p.stdin.write(b'{"hook_event_name":"Stop","session_id":"s","turn_id":"t"}')
            p.stdin.flush()
            try:
                code = p.wait(timeout=.7)
            except subprocess.TimeoutExpired:
                self.fail('A complete JSON event must not wait for an EOF')
            self.assertEqual(code, 0)
            self.assertEqual(p.stdout.read().strip(), b'{}')
            self.assertEqual(self.state()['state'], 'stopped')
        finally:
            if p.poll() is None:
                p.terminate()
                p.wait(timeout=2)
            p.stdin.close()
            p.stdout.close()
            p.stderr.close()

    def test_keeper_writes_only_its_own_data_whatever_the_environment_says(self):
        outside = self.data / 'outside'
        env = {'CYCLOPS_SESSION_ID': 'pane-1', 'CYCLOPS_PRESENCE_ROOT': str(outside),
               'XDG_STATE_HOME': str(outside / 'state')}
        for event in ('SessionStart', 'UserPromptSubmit', 'Stop', 'SessionEnd'):
            self.hook(event, extra_env=env, **({'source': 'startup'} if event == 'SessionStart' else {}))
        self.assertFalse(outside.exists())
        written = {p.relative_to(self.data).parts[0] for p in self.data.rglob('*') if p.is_file()}
        self.assertEqual(written, {'activity-face'})

    def test_terminal_quit_restores_screen_and_cursor(self):
        master, slave = pty.openpty()
        p = subprocess.Popen([sys.executable, str(SCRIPTS / 'terminal.py'),
                              '--data', str(self.data)], stdin=slave, stdout=slave,
                             stderr=slave, env={**self.env, 'TERM': 'xterm-256color'})
        os.close(slave)
        content = b''
        try:
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and b'\x1b[?25l' not in content:
                if select.select([master], [], [], .1)[0]:
                    try:
                        content += os.read(master, 65536)
                    except OSError:
                        break
            self.assertIn(b'\x1b[?1049h', content)
            os.write(master, b'q')
            self.assertEqual(p.wait(timeout=3), 0)
            while select.select([master], [], [], .1)[0]:
                try:
                    content += os.read(master, 65536)
                except OSError:
                    break
            self.assertIn(b'\x1b[?25h', content)
            self.assertIn(b'\x1b[?1049l', content)
        finally:
            if p.poll() is None:
                p.terminate()
                p.wait(timeout=3)
            os.close(master)


if __name__ == '__main__':
    unittest.main()
