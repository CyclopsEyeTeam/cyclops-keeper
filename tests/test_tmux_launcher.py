"""Hybrid launcher contracts: real tmux, disposable host, no user server or model."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pty
import select
import shlex
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest
import fcntl

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'plugins/cyclops-keeper/scripts'
sys.path.insert(0,str(SCRIPTS))
import launcher_link as link

class Contracts(unittest.TestCase):
    def module(self):
        path=SCRIPTS/'launcher_tmux.py'
        self.assertTrue(path.is_file(),'Owned tmux launcher is missing')
        spec=importlib.util.spec_from_file_location('launcher_tmux',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_small_terminal_refuses_before_it_can_hide_codex(self):
        module=self.module()
        for mode,w,h in [('side',95,40),('side',120,19),('top',120,34),('top',59,40)]:
            with self.subTest(mode=mode,w=w,h=h):
                with self.assertRaisesRegex(ValueError,'--keeper'):
                    module.validate_size(mode,w,h)
        module.validate_size('side',96,20)
        module.validate_size('top',60,35)

    def test_strict_reach_does_not_inspect_tool_arguments_even_when_on(self):
        import activity,keeper_link
        class Payload(dict):
            def get(self,key,*args):
                if key=='tool_input':raise AssertionError('Reach inspected tool arguments')
                return super().get(key,*args)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            env={**os.environ,'KEEPER_LINK':'1','KEEPER_LINK_REACH':'1','KEEPER_LINK_NO_WORKER':'1',
                 'CYCLOPS_LINK_DIR':str(root/'link'),'XDG_CONFIG_HOME':str(root/'config')}
            payload=Payload(session_id='session',cwd=tmp,hook_event_name='PreToolUse',
                            tool_use_id='call',tool_name='Bash',tool_input={'command':'claude secret'})
            activity.update(root/'data',payload)
            keeper_link.observe(root/'data',payload,env)
            mine=keeper_link.read_private(root/'data',hashlib.sha256(b'session').hexdigest())
            self.assertEqual(mine['reaching'],[])

class Launch:
    def __init__(self,root,mode='side',argv=(),label='session',size=(120,42),project=None,env_update=None,start=True):
        self.root=Path(root);self.label=label;self.runtime=self.root/'runtime';self.runtime.mkdir(mode=0o700)
        self.project=Path(project) if project else self.root/'project';self.project.mkdir(exist_ok=True)
        self.receipt=self.root/'receipt.json'
        fake=self.root/'codex-fixture'
        fake.write_text('''#!/usr/bin/python3
import ctypes,json,os,subprocess,sys,termios,tty
from pathlib import Path
ctypes.CDLL(None).prctl(15,b'codex-fixture',0,0,0)
args=sys.argv[1:]
if '-C' in args:os.chdir(args[args.index('-C')+1])
Path(os.environ['KEEPER_TEST_RECEIPT']).write_text(json.dumps({'pid':os.getpid(),'argv':args}))
payload={'hook_event_name':'SessionStart','source':'startup','session_id':os.environ['KEEPER_TEST_SESSION'],'cwd':os.getcwd()}
subprocess.run([sys.executable,os.environ['KEEPER_TEST_HOOK']],input=json.dumps(payload),text=True,check=True)
if os.environ.get('KEEPER_TEST_SCROLL'):
    for index in range(180):print('SCROLL_FIXTURE_%03d'%index,flush=True)
    print('COPY_FIXTURE_MARKER',flush=True)
    print('\\x1b[?2004h',end='',flush=True)
original=termios.tcgetattr(0)
try:
    tty.setraw(0)
    while True:
        key=os.read(0,1)
        if os.environ.get('KEEPER_TEST_INPUT_LOG'):
            with open(os.environ['KEEPER_TEST_INPUT_LOG'],'ab') as log:log.write(key)
        if not key or (key==b'x' and not os.environ.get('KEEPER_TEST_SCROLL')):break
        if not os.environ.get('KEEPER_TEST_INPUT_LOG'):print('host received '+key.decode(errors='replace'),flush=True)
finally:termios.tcsetattr(0,termios.TCSANOW,original)
''');fake.chmod(0o700)
        self.env={**os.environ,'KEEPER_CODEX':str(fake),'KEEPER_PLUGIN_ROOT':str(SCRIPTS.parent),
                  'XDG_RUNTIME_DIR':str(self.runtime),'TMPDIR':os.environ.get('TMPDIR',str(self.runtime)),'PLUGIN_DATA':str(self.root/'data'),
                  'KEEPER_LINK':'0','KEEPER_TEST_RECEIPT':str(self.receipt),'KEEPER_TEST_SESSION':label,
                  'KEEPER_TEST_HOOK':str(SCRIPTS/'hook.py'),'TERM':'xterm-256color','NO_COLOR':'1',
                  'PYTHONDONTWRITEBYTECODE':'1'}
        for key in ['DISPLAY','WAYLAND_DISPLAY','TMUX','TMUX_PANE','KEEPER_LAUNCH_SOCKET','KEEPER_LAUNCH_TOKEN']:
            self.env.pop(key,None)
        self.env.update({k:v for k,v in (env_update or {}).items() if v is not None})
        for key,value in (env_update or {}).items():
            if value is None:self.env.pop(key,None)
        self.master,self.slave=pty.openpty();self.original=termios.tcgetattr(self.slave);self.data=b''
        self.resize(*size)
        def terminal_owner():
            os.setsid();fcntl.ioctl(self.slave,termios.TIOCSCTTY,0)
        self.child=subprocess.Popen([str(ROOT/'codex-keeper'),'--keeper-'+mode,'-C',str(self.project),*argv],
            stdin=self.slave,stdout=self.slave,stderr=self.slave,env=self.env,preexec_fn=terminal_owner) if start else None
        self.state_path=None;self.state=None

    def resize(self,columns,rows):
        fcntl.ioctl(self.slave,termios.TIOCSWINSZ,struct.pack('HHHH',rows,columns,0,0))
        if hasattr(self,'child') and self.child.poll() is None:
            os.kill(self.child.pid,signal.SIGWINCH)

    def drain(self):
        while select.select([self.master],[],[],0)[0]:
            try:self.data=(self.data+os.read(self.master,65536))[-200000:]
            except OSError:break

    def wait(self,predicate,seconds=12):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            self.drain()
            try:result=predicate()
            except (OSError,KeyError,ValueError):result=None
            if result:return result
            if self.child is not None and self.child.poll() is not None:break
            time.sleep(.05)
        self.drain()
        raise AssertionError('Condition failed; launcher status '+str(self.child.poll() if self.child else None)+'; '+repr(self.data[-2000:]))

    def attached(self):
        expected=hashlib.sha256(self.label.encode()).hexdigest()
        def found():
            for path in self.runtime.glob('keeper-*/attachment.json'):
                value=json.loads(path.read_text())
                if value.get('session')==expected and value.get('tmux',{}).get('keeper'):
                    self.state_path,self.state=path,value
                    return value
        return self.wait(found)

    def tmux(self,*args):
        meta=self.state['tmux']
        return subprocess.run(['tmux','-S',meta['socket'],*args],env=self.env,
                              capture_output=True,text=True,timeout=5,check=True).stdout.strip()

    def panes(self):
        raw=self.tmux('list-panes','-t',self.state['tmux']['window'],'-F',
                      '#{pane_id}|#{pane_width}|#{pane_height}|#{pane_active}|#{pane_current_path}')
        return {parts[0]:{'width':int(parts[1]),'height':int(parts[2]),'active':parts[3]=='1','cwd':parts[4]}
                for parts in (line.split('|') for line in raw.splitlines())}

    def close(self):
        if self.child is not None and self.child.poll() is None:
            self.child.terminate()
            deadline=time.monotonic()+8
            while self.child.poll() is None and time.monotonic()<deadline:self.drain();time.sleep(.05)
            if self.child.poll() is None:self.child.kill()
        if self.child is not None:self.child.wait(timeout=3)
        termios.tcsetattr(self.slave,termios.TCSANOW,self.original)
        os.close(self.master);os.close(self.slave)

class Layouts(unittest.TestCase):
    def test_headless_side_launch_keeps_exact_arguments_and_separate_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch=Launch(tmp,argv=['-m','model with spaces','-c','x="a b"','--','--keeper-top','literal $(touch nope)'],label='side-session')
            try:
                state=launch.attached();meta=state['tmux']
                panes=launch.panes()
                self.assertEqual(panes[meta['keeper']]['width'],35)
                self.assertGreaterEqual(panes[meta['source']]['width'],60)
                launch.wait(lambda:json.loads(launch.state_path.read_text())['tmux'].get('focus_requested') and launch.panes()[meta['keeper']]['active'])
                self.assertEqual(os.readlink(f"/proc/{json.loads(launch.state_path.with_suffix('.ready').read_text())['pid']}/cwd"),str(launch.project))
                receipt=json.loads(launch.receipt.read_text())
                self.assertEqual(receipt['argv'],['-C',str(launch.project),'-m','model with spaces','-c','x="a b"','--','--keeper-top','literal $(touch nope)'])
                launch.tmux('select-pane','-t',meta['source'])
                launch.tmux('send-keys','-t',meta['source'],'a')
                launch.wait(lambda:b'host received a' in launch.data)
                time.sleep(.8);self.assertTrue(launch.panes()[meta['source']]['active'])
                launch.tmux('send-keys','-t',meta['keeper'],'q')
                launch.wait(lambda:len(launch.panes())==1)
                self.assertTrue(link.alive(state['codex']))
                launch.tmux('send-keys','-t',meta['source'],'x')
                deadline=time.monotonic()+8
                while launch.child.poll() is None and time.monotonic()<deadline:launch.drain();time.sleep(.05)
                self.assertEqual(launch.child.poll(),0)
                self.assertEqual(termios.tcgetattr(launch.slave),launch.original)
                self.assertFalse(list(launch.runtime.glob('keeper-*/*attachment*')))
            finally:launch.close()

class MoreLayouts(unittest.TestCase):
    def test_private_mouse_and_history_support_scrolling_without_shared_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch=Launch(tmp,label='mouse-config')
            try:
                launch.attached()
                self.assertEqual(launch.tmux('show-option','-gqv','mouse'),'on')
                self.assertGreaterEqual(int(launch.tmux('show-option','-gqv','history-limit')),10000)
            finally:launch.close()

    def test_missing_environment_variables_stay_absent_in_the_owned_pane(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch=Launch(tmp,label='absent-env',env_update={'CODEX_HOME':None,'NO_COLOR':None})
            try:
                launch.attached()
                ready=launch.wait(lambda:json.loads(launch.state_path.with_suffix('.ready').read_text()))
                variables=Path('/proc/'+str(ready['pid'])+'/environ').read_bytes().split(b'\0')
                self.assertFalse(any(x.startswith(b'CODEX_HOME=') or x.startswith(b'NO_COLOR=') for x in variables))
            finally:launch.close()

    def test_top_resize_keeps_banner_then_reclaims_space_when_too_small(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch=Launch(tmp,mode='top',label='top-resize')
            try:
                state=launch.attached();meta=state['tmux']
                self.assertEqual(launch.panes()[meta['keeper']]['height'],14)
                launch.resize(140,36)
                launch.wait(lambda:launch.panes()[meta['keeper']]['height']==14 and launch.panes()[meta['source']]['height']==21)
                self.assertTrue(link.alive(state['codex']))
                launch.resize(100,24)
                launch.wait(lambda:len(launch.panes())==1)
                self.assertGreaterEqual(launch.panes()[meta['source']]['height'],20)
                self.assertTrue(link.alive(state['codex']))
            finally:launch.close()

    def test_small_terminal_starts_no_host_or_server(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch=Launch(tmp,size=(80,24))
            try:
                launch.child.wait(timeout=4);launch.drain()
                self.assertEqual(launch.child.returncode,2)
                self.assertIn(b'use --keeper',launch.data)
                self.assertFalse(launch.receipt.exists())
                self.assertFalse(list(launch.runtime.glob('keeper-tmux-*')))
            finally:launch.close()

    def test_outer_kill_before_worker_bootstrap_leaves_no_owned_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            wrapper=Path(tmp)/'tmux-delay'
            wrapper.write_text('#!/usr/bin/python3\nimport os,sys\nargs=sys.argv[1:]\nif "new-session" in args:args[-1]="sleep .7; "+args[-1]\nos.execv('+repr(shutil.which('tmux'))+',["tmux",*args])\n')
            wrapper.chmod(0o700)
            launch=Launch(tmp,label='before-bootstrap',env_update={'KEEPER_TMUX':str(wrapper)})
            try:
                launch.wait(lambda:list(launch.runtime.glob('keeper-tmux-*/tmux.sock')))
                launch.child.kill();launch.child.wait(timeout=3)
                deadline=time.monotonic()+8
                while any(p.is_dir() for p in launch.runtime.glob('keeper-*')) and time.monotonic()<deadline:time.sleep(.05)
                self.assertFalse([p for p in launch.runtime.glob('keeper-*') if p.is_dir()])
                self.assertFalse(launch.receipt.exists())
            finally:launch.close()

    def test_split_failure_cleans_up_its_started_host_and_private_server(self):
        with tempfile.TemporaryDirectory() as tmp:
            wrapper=Path(tmp)/'tmux-fail'
            wrapper.write_text('#!/usr/bin/python3\nimport os,sys\nif "split-window" in sys.argv[1:]:sys.exit(2)\nos.execv('+repr(shutil.which('tmux'))+',["tmux",*sys.argv[1:]])\n')
            wrapper.chmod(0o700)
            launch=Launch(tmp,label='split-failure',env_update={'KEEPER_TMUX':str(wrapper)})
            try:
                deadline=time.monotonic()+8
                while launch.child.poll() is None and time.monotonic()<deadline:launch.drain();time.sleep(.05)
                self.assertEqual(launch.child.poll(),2)
                if launch.receipt.exists():self.assertFalse(link.process_identity(json.loads(launch.receipt.read_text())['pid']))
                self.assertFalse([p for p in launch.runtime.glob('keeper-*') if p.is_dir()])
            finally:launch.close()

    @unittest.skipUnless(os.sysconf('SC_ARG_MAX')>=1800000,'Small process argument budget')
    def test_valid_large_unicode_and_control_arguments_are_forwarded_exactly(self):
        args=['--',*(['\x01雪'*17000]*24)]
        with tempfile.TemporaryDirectory() as tmp:
            launch=Launch(tmp,label='large-argv',argv=args)
            try:
                launch.attached()
                self.assertEqual(json.loads(launch.receipt.read_text())['argv'],['-C',str(launch.project),*args])
            finally:launch.close()

    def test_duplicate_launch_on_one_terminal_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch=Launch(tmp,label='only-one')
            try:
                state=launch.attached()
                other=subprocess.Popen([str(ROOT/'codex-keeper'),'--keeper-side'],stdin=launch.slave,stdout=launch.slave,stderr=launch.slave,env=launch.env)
                self.assertEqual(other.wait(timeout=5),2)
                launch.drain();self.assertIn(b'already owns this terminal',launch.data)
                self.assertTrue(link.alive(state['codex']))
                self.assertEqual(len(launch.panes()),2)
            finally:launch.close()

    def test_same_project_sessions_never_cross_attach(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);project=root/'shared';project.mkdir();a=root/'one';b=root/'two';a.mkdir();b.mkdir()
            first=Launch(a,label='same-folder-one',project=project)
            second=Launch(b,mode='top',label='same-folder-two',project=project)
            try:
                one=first.attached();two=second.attached()
                self.assertNotEqual(one['session'],two['session'])
                self.assertEqual(one['session'],hashlib.sha256(b'same-folder-one').hexdigest())
                self.assertEqual(two['session'],hashlib.sha256(b'same-folder-two').hexdigest())
                self.assertNotEqual(one['tmux']['server'],two['tmux']['server'])
                first.tmux('send-keys','-t',one['tmux']['source'],'x')
                first.wait(lambda:first.child.poll() is not None)
                self.assertTrue(link.alive(two['codex']))
                self.assertEqual(json.loads(second.state_path.read_text())['session'],two['session'])
            finally:first.close();second.close()

    def test_outer_launcher_kill_leaves_no_owned_processes(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch=Launch(tmp,label='outer-kill')
            try:
                state=launch.attached();ready=launch.wait(lambda:json.loads(launch.state_path.with_suffix('.ready').read_text()))
                launch.child.kill();launch.child.wait(timeout=3)
                deadline=time.monotonic()+8
                while any(link.alive(x) for x in [state['codex'],state['owner'],state['tmux']['server'],ready]) and time.monotonic()<deadline:
                    launch.drain();time.sleep(.1)
                self.assertFalse(any(link.alive(x) for x in [state['codex'],state['owner'],state['tmux']['server'],ready]))
                self.assertFalse(list(launch.runtime.glob('keeper-*')) and list(launch.runtime.glob('keeper-*/attachment.json')))
            finally:launch.close()

    def test_user_created_private_pane_survives_outer_shutdown_and_kill(self):
        for abrupt in [False,True]:
            with self.subTest(abrupt=abrupt),tempfile.TemporaryDirectory() as tmp:
                launch=Launch(tmp,label='private-extra-pane')
                directory=None;foreign=None
                try:
                    state=launch.attached()
                    root=next(launch.runtime.glob('keeper-tmux-*'))
                    directory=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
                    alias=f'/proc/{os.getpid()}/fd/{directory}/tmux.sock'
                    def tmux(*args):
                        return subprocess.run(['tmux','-S',alias,*args],env=launch.env,capture_output=True,text=True,check=True,timeout=4).stdout.strip()
                    key=tmux('new-window','-d','-P','-F','#{pane_id}','exec sleep 60')
                    foreign=link.process_identity(int(tmux('display-message','-p','-t',key,'#{pane_pid}')))
                    if abrupt:launch.child.kill()
                    else:launch.child.terminate()
                    launch.child.wait(timeout=10)
                    deadline=time.monotonic()+8
                    while link.alive(state['codex']) and time.monotonic()<deadline:time.sleep(.05)
                    self.assertFalse(link.alive(state['codex']))
                    self.assertTrue(link.alive(foreign),'User-created pane was terminated')
                    self.assertTrue(root.exists(),'Additional pane lost its private runtime')
                    self.assertEqual(tmux('display-message','-p','-t',key,'#{pane_pid}'),str(foreign['pid']))
                finally:
                    if directory is not None:
                        subprocess.run(['tmux','-S',alias,'kill-server'],env=launch.env,capture_output=True,timeout=4)
                        os.close(directory)
                    launch.close()

    def test_pane_supervisor_kill_leaves_no_owned_host_or_keeper(self):
        with tempfile.TemporaryDirectory() as tmp:
            launch=Launch(tmp,label='supervisor-kill')
            try:
                state=launch.attached();ready=launch.wait(lambda:json.loads(launch.state_path.with_suffix('.ready').read_text()))
                os.kill(state['owner']['pid'],signal.SIGKILL)
                deadline=time.monotonic()+8
                while launch.child.poll() is None and time.monotonic()<deadline:launch.drain();time.sleep(.1)
                self.assertIsNotNone(launch.child.poll())
                self.assertFalse(link.alive(state['codex']))
                self.assertFalse(link.alive(ready))
                self.assertFalse(launch.state_path.parent.exists())
            finally:launch.close()

class ExistingSessions(unittest.TestCase):
    def exercise(self,replace=False,wrong=False):
        with tempfile.TemporaryDirectory() as tmp:
            fixture=Launch(tmp,label='existing-session',start=False)
            fd=os.open(fixture.runtime,os.O_RDONLY|os.O_DIRECTORY)
            sock=f'/proc/{os.getpid()}/fd/{fd}/existing.sock'
            def tmux(*args):
                return subprocess.run(['tmux','-S',sock,'-f','/dev/null',*args],env=fixture.env,
                                      capture_output=True,text=True,timeout=5,check=True).stdout.strip()
            try:
                tmux('new-session','-d','-s','existing','-x','200','-y','45','-c',str(fixture.project),'/bin/bash --noprofile --norc')
                source=tmux('display-message','-p','-t','existing','#{pane_id}')
                foreign=tmux('split-window','-d','-h','-l','60','-t',source,'-P','-F','#{pane_id}','exec sleep 60')
                tmux('set-option','-g','mouse','off');tmux('set-option','-s','escape-time','37')
                tmux('set-option','-t','existing','prefix','C-a')
                tmux('set-option','-w','-t','existing','remain-on-exit','on')
                def settings():
                    return [tmux('show-options','-g'),tmux('show-options','-s'),tmux('show-options','-t','existing'),tmux('show-options','-w','-t','existing')]
                before=settings()
                geometry=tmux('display-message','-p','-t',foreign,'#{pane_pid}|#{pane_width}|#{pane_height}|#{pane_left}|#{pane_top}')
                args=[str(ROOT/'codex-keeper'),'--keeper-side','-C',str(fixture.project)]
                if wrong:args=['env','TMUX_PANE='+foreign,*args]
                tmux('send-keys','-t',source,shlex.join(args),'Enter')
                if wrong:
                    fixture.wait(lambda:'no pane was changed' in tmux('capture-pane','-p','-t',source))
                    self.assertFalse(fixture.receipt.exists())
                else:
                    state=fixture.attached();meta=state['tmux']
                    fixture.wait(lambda:json.loads(fixture.state_path.read_text())['tmux'].get('focus_requested'))
                    self.assertEqual(fixture.panes()[meta['keeper']]['width'],35)
                    self.assertEqual(settings(),before)
                    self.assertEqual(tmux('display-message','-p','-t',foreign,'#{pane_pid}|#{pane_width}|#{pane_height}|#{pane_left}|#{pane_top}'),geometry)
                    replacement=None
                    if replace:
                        tmux('respawn-pane','-k','-t',meta['keeper'],'exec sleep 60')
                        replacement=tmux('display-message','-p','-t',meta['keeper'],'#{pane_pid}')
                    tmux('send-keys','-t',meta['source'],'x')
                    fixture.wait(lambda:not fixture.state_path.parent.exists())
                    self.assertEqual(settings(),before)
                    self.assertEqual(tmux('display-message','-p','-t',foreign,'#{pane_pid}|#{pane_width}|#{pane_height}|#{pane_left}|#{pane_top}'),geometry)
                    if not replace:self.assertEqual(set(tmux('list-panes','-t','existing','-F','#{pane_id}').splitlines()),{source,foreign})
                    if replace:self.assertEqual(tmux('display-message','-p','-t',meta['keeper'],'#{pane_pid}'),replacement)
            finally:
                subprocess.run(['tmux','-S',sock,'kill-server'],env=fixture.env,capture_output=True,timeout=4)
                os.close(fd);fixture.close()

    def test_existing_settings_and_unrelated_pane_remain_unchanged(self):self.exercise()
    def test_replaced_companion_is_not_killed_as_owned(self):self.exercise(replace=True)
    def test_unrelated_tmux_pane_environment_is_refused_before_host_start(self):self.exercise(wrong=True)

if __name__=='__main__':unittest.main()
