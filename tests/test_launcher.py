import array
import hashlib
import importlib.util
import types
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'plugins/cyclops-keeper/scripts'
sys.path.insert(0,str(SCRIPTS))

class AttachmentTests(unittest.TestCase):
    def test_session_start_supplies_only_hash_and_actual_project_handle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            directory_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            socket_path = f'/proc/{os.getpid()}/fd/{directory_fd}/link.sock'
            sock.bind(socket_path)
            sock.settimeout(.3)
            env = {**os.environ, 'PLUGIN_DATA':str(root/'data'),
                   'KEEPER_LAUNCH_SOCKET':socket_path,
                   'KEEPER_LAUNCH_TOKEN':'ab'*32, 'KEEPER_LINK':'0'}
            payload = {'hook_event_name':'SessionStart', 'source':'startup',
                       'session_id':'private-session', 'cwd':str(root),
                       'prompt':'secret prompt', 'tool_input':{'command':'secret command'}}
            result = subprocess.run([sys.executable,str(SCRIPTS/'hook.py')],
                 input=json.dumps(payload),text=True,env=env,capture_output=True)
            self.assertEqual((result.returncode,result.stdout,result.stderr),(0,'{}\n',''))
            try:
                raw, extra, flags, _ = sock.recvmsg(1024,socket.CMSG_SPACE(4))
            except socket.timeout:
                self.fail('SessionStart did not establish the private launcher link')
            message = json.loads(raw)
            self.assertEqual(message,{'v':1,'token':'ab'*32,
                 'session':hashlib.sha256(b'private-session').hexdigest()})
            self.assertNotIn(b'secret',raw)
            self.assertNotIn(b'private-session',raw)
            self.assertNotIn(str(root).encode(),raw)
            fds = array.array('i')
            for level, kind, value in extra:
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    fds.frombytes(value)
            self.assertEqual(len(fds),1)
            try:
                self.assertEqual(os.fstat(fds[0]).st_ino,root.stat().st_ino)
            finally:
                for fd in fds: os.close(fd)
            self.assertFalse((root/'data/link').exists(), 'Link consent changed')
            sock.close()
            os.close(directory_fd)

class LauncherTests(unittest.TestCase):
    def launcher(self):
        path = SCRIPTS/'launcher.py'
        self.assertTrue(path.is_file(), 'Keeper flag launcher is missing')
        spec=importlib.util.spec_from_file_location('keeper_launcher',path)
        module=importlib.util.module_from_spec(spec)
        sys.path.insert(0,str(SCRIPTS))
        spec.loader.exec_module(module)
        return module

    def test_flags_do_not_rewrite_normal_arguments_or_option_values(self):
        launch=self.launcher()
        mode, args=launch.split_flags(['--keeper-side','-C','a project','-c','x="a b"',
                                      '-m','--keeper','--','--keeper-top'])
        self.assertEqual(mode,'side')
        self.assertEqual(args,['-C','a project','-c','x="a b"','-m','--keeper','--','--keeper-top'])
        self.assertEqual(launch.split_flags(['--keeper','--keeper']),('focus',[]))
        with self.assertRaises(ValueError): launch.split_flags(['--keeper-side','--keeper-top'])
        self.assertEqual(launch.split_flags(['update']), (None,['update']))

    def test_wrong_launch_cannot_attach_or_leak_received_descriptors(self):
        import launcher_link as link
        with tempfile.TemporaryDirectory() as tmp:
            fd=os.open(tmp,os.O_RDONLY|os.O_DIRECTORY)
            path=f'/proc/{os.getpid()}/fd/{fd}/link.sock'
            with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as receiver:
                receiver.setsockopt(socket.SOL_SOCKET,socket.SO_PASSCRED,1)
                receiver.bind(path)
                receiver.settimeout(.3)
                for message in [{'v':1,'token':'wrong','session':'ab'*32},
                                {'v':1,'token':'cd'*32,'session':'not-a-session'},
                                {'v':1,'token':'cd'*32,'session':'ab'*32,'prompt':'secret'}]:
                    with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as sender:
                        sender.sendmsg([json.dumps(message).encode()],
                          [(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[fd]))],0,path)
                    self.assertIsNone(link.receive(receiver,'cd'*32))
            os.close(fd)


class PanelTests(unittest.TestCase):
    def test_unattached_panel_never_follows_latest_and_owner_death_is_visible(self):
        import launcher_link as link
        import terminal
        self.assertTrue(callable(getattr(terminal,'launch_selection',None)),
                        'Renderer has no verified launcher selection')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'attachment.json'
            owner=link.process_identity(os.getpid())
            link.atomic(path,{'v':1,'owner':owner,'session':None,'project_fd':None})
            self.assertEqual(terminal.launch_selection(path),('0'*64,False))
            fd=os.open(tmp,os.O_RDONLY|os.O_DIRECTORY)
            before=os.open('.',os.O_RDONLY|os.O_DIRECTORY)
            try:
                link.atomic(path,{'v':1,'owner':owner,'session':'ab'*32,'project_fd':fd})
                self.assertEqual(terminal.launch_selection(path),('ab'*32,True))
                self.assertEqual(os.stat('.').st_ino,Path(tmp).stat().st_ino)
                link.atomic(path,{'v':1,'owner':{'pid':owner['pid'],'start':'wrong'},'session':'cd'*32})
                with self.assertRaises(ValueError): terminal.launch_selection(path)
            finally:
                os.fchdir(before); os.close(before); os.close(fd)

class TerminalLifecycleTests(unittest.TestCase):
    def test_real_renderer_resize_pin_and_shutdown_restore_the_terminal(self):
        import launcher_link as link
        import pty, select, struct, termios, time, fcntl
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'attachment.json'
            owner=link.process_identity(os.getpid())
            link.atomic(path,{'v':1,'owner':owner,'session':None,'project_fd':None})
            master,slave=pty.openpty()
            original=termios.tcgetattr(slave)
            fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',24,80,0,0))
            env={**os.environ,'TERM':'xterm-256color','NO_COLOR':'1','KEEPER_LINK':'0'}
            child=subprocess.Popen([sys.executable,str(SCRIPTS/'terminal.py'),'--attachment',str(path),
                                    '--data',str(Path(tmp)/'data')],stdin=slave,stdout=slave,stderr=slave,env=env)
            def output_until(needle):
                result=b'';deadline=time.monotonic()+4
                while needle not in result and time.monotonic()<deadline:
                    if select.select([master],[],[],.1)[0]: result+=os.read(master,1000000)
                self.assertIn(needle,result)
                return result
            try:
                output_until(b'Session: unattached')
                self.assertNotEqual(termios.tcgetattr(slave),original)
                fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',10,40,0,0))
                output_until(b'Session: unattached')
                link.atomic(path,{'v':1,'owner':owner,'session':'ab'*32,'project_fd':None})
                frame=output_until(b'Session: attached')
                last=frame.decode().split('\x1b[H')[-1].split('\x1b[0m')[0]
                self.assertEqual(len(last.split('\n')),10)
                self.assertTrue(all(len(row.replace('\x1b[K','').replace('\r',''))<=39 for row in last.split('\n')))
                link.atomic(path,{'v':1,'owner':{'pid':owner['pid'],'start':'gone'},'session':'ab'*32})
                child.wait(timeout=3)
                output_until(b'\x1b[?1049l')
                self.assertEqual(child.returncode,0)
                self.assertEqual(termios.tcgetattr(slave),original)
            finally:
                if child.poll() is None: child.terminate();child.wait(timeout=3)
                os.close(master);os.close(slave)

class ReviewRegressionTests(unittest.TestCase):
    def test_old_project_handle_does_not_permanently_close_panel(self):
        import launcher_link as link
        import terminal
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'attachment.json';owner=link.process_identity(os.getpid())
            old=os.open(tmp,os.O_RDONLY|os.O_DIRECTORY);os.close(old)
            link.atomic(path,{'v':1,'owner':owner,'session':'ab'*32,'project_fd':old})
            self.assertEqual(terminal.launch_selection(path),('0'*64,False))

    def test_reused_handle_cannot_pair_old_session_with_new_project(self):
        import launcher_link as link
        import terminal
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); first=root/'first'; second=root/'second'
            first.mkdir(); second.mkdir()
            path=root/'attachment.json'; owner=link.process_identity(os.getpid())
            fd=os.open(first,os.O_RDONLY|os.O_DIRECTORY)
            before=os.open('.',os.O_RDONLY|os.O_DIRECTORY)
            link.atomic(path,{'v':1,'owner':owner,'session':'ab'*32,'project_fd':fd,'generation':1})
            original_read=link.read_attachment
            reads=0
            def switch_after_snapshot(location):
                nonlocal reads
                snapshot=original_read(location)
                reads+=1
                if reads==1:
                    os.close(fd)
                    replacement=os.open(second,os.O_RDONLY|os.O_DIRECTORY)
                    if replacement!=fd:
                        os.dup2(replacement,fd); os.close(replacement)
                    link.atomic(path,{'v':1,'owner':owner,'session':'cd'*32,'project_fd':fd,'generation':2})
                return snapshot
            try:
                with patch.object(link,'read_attachment',side_effect=switch_after_snapshot):
                    self.assertEqual(terminal.launch_selection(path),('cd'*32,True))
                self.assertEqual(os.stat('.').st_ino,second.stat().st_ino)
            finally:
                os.fchdir(before); os.close(before); os.close(fd)

    def test_wrapper_refuses_to_overwrite_an_existing_codex_function(self):
        result=subprocess.run(['bash','--noprofile','--norc','-c',
             'codex() { printf original; }; source "$1/keeper-shell.sh"; codex',
             '_',str(ROOT)],capture_output=True,text=True)
        self.assertEqual(result.stdout,'original')

    @unittest.skipUnless(os.environ.get('DISPLAY'),'X11 desktop check')
    def test_disappearing_window_is_a_safe_absence(self):
        result=subprocess.run([sys.executable,'-c',
             "from keeper_window import Window; w=Window(); assert w.prop(0xDEADBEEF,'WM_WINDOW_ROLE') is None; w.close()"],
             env={**os.environ,'PYTHONPATH':str(SCRIPTS)},capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_dead_launcher_removes_only_its_private_runtime_instance(self):
        import launcher_link as link
        self.assertTrue(callable(getattr(link,'cleanup_dead_launcher',None)), 'Dead-launcher cleanup missing')
        with tempfile.TemporaryDirectory(prefix='keeper-') as tmp:
            path=Path(tmp)/'attachment.json'
            link.atomic(path,{'v':1,'owner':{'pid':999999999,'start':'gone'},'session':None})
            self.assertTrue(link.cleanup_dead_launcher(path))
            self.assertFalse(path.parent.exists())

class SupervisorTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('DISPLAY'),'X11 launcher boundary check')
    def test_codex_exit_restores_original_tty_and_exact_arguments(self):
        self.exercise(False)

    @unittest.skipUnless(os.environ.get('DISPLAY'),'X11 launcher boundary check')
    def test_launcher_death_does_not_leave_codex_running(self):
        self.exercise(True)

    @unittest.skipUnless(os.environ.get('DISPLAY'),'X11 launcher boundary check')
    def test_codex_signal_exit_keeps_normal_shell_status(self):
        self.exercise(False,signal_child=True)

    def exercise(self,kill_owner,signal_child=False):
        import launcher_link as link
        import pty,select,termios,time,signal
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); fake=root/'fake-codex';terminal=root/'gnome-terminal'
            fake.write_text('#!/usr/bin/python3\nimport json,os,sys,tty\n'
                            'tty.setraw(0)\nprint(json.dumps(sys.argv[1:]),flush=True)\n'
                            'os.read(0,1)\n')
            terminal.write_text('#!/bin/sh\nexit 0\n')
            fake.chmod(0o700);terminal.chmod(0o700)
            env={**os.environ,'KEEPER_CODEX':str(fake),'KEEPER_PLUGIN_ROOT':str(SCRIPTS.parent),
                 'XDG_RUNTIME_DIR':str(root),'PATH':str(root)+os.pathsep+os.environ['PATH']}
            master,slave=pty.openpty();original=termios.tcgetattr(slave)
            child=subprocess.Popen([str(ROOT/'codex-keeper'),'--keeper','-m','a model','--','--keeper-top'],
                                   stdin=slave,stdout=slave,stderr=slave,env=env)
            data=b'';deadline=time.monotonic()+4
            try:
                while b'["-m"' not in data and time.monotonic()<deadline:
                    if select.select([master],[],[],.1)[0]: data+=os.read(master,100000)
                self.assertIn(b'["-m", "a model", "--", "--keeper-top"]',data)
                path=next(root.glob('keeper-*/attachment.json'));state=json.loads(path.read_text())
                codex=state['codex']
                if kill_owner:
                    self.assertTrue(link.alive(codex),'Codex must be alive before killing its launcher')
                    child.kill();child.wait(timeout=3)
                    until=time.monotonic()+2
                    while link.alive(codex) and time.monotonic()<until:time.sleep(.05)
                    self.assertFalse(link.alive(codex),'Codex became an orphan after launcher death')
                else:
                    duplicate=subprocess.run([str(ROOT/'codex-keeper'),'--keeper'],stdin=slave,
                                             capture_output=True,env=env,timeout=3)
                    self.assertEqual(duplicate.returncode,2)
                    self.assertIn(b'already owns this terminal',duplicate.stderr)
                    if signal_child:os.kill(codex['pid'],signal.SIGTERM)
                    else:os.write(master,b'x')
                    child.wait(timeout=4)
                    self.assertEqual(child.returncode,143 if signal_child else 0)
                    self.assertEqual(termios.tcgetattr(slave),original)
                    self.assertFalse(path.parent.exists())
            finally:
                if child.poll() is None:child.terminate();child.wait(timeout=4)
                if 'codex' in locals() and link.alive(codex):os.kill(codex['pid'],signal.SIGTERM)
                termios.tcsetattr(slave,termios.TCSANOW,original)
                os.close(master);os.close(slave)

if __name__=='__main__': unittest.main()
