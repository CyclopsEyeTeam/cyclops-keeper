"""Real GNOME/tmux mouse and clipboard acceptance on an isolated X11 display."""
import ctypes as C
from ctypes.util import find_library
import json
import os
import signal
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from test_tmux_launcher import Launch

@unittest.skipUnless(all(shutil.which(x) for x in ['Xvfb','gnome-terminal','xclip','dbus-run-session','xwininfo','gdbus']) and Path('/usr/libexec/gnome-terminal-server').is_file() and find_library('X11') and find_library('Xtst'),
                     'Isolated GNOME clipboard acceptance dependencies unavailable')
class Clipboard(unittest.TestCase):
    def exercise(self,mode):
        with tempfile.TemporaryDirectory(prefix='keeper-clipboard-') as tmp:
            root=Path(tmp);log=root/'input.bin';launch=None;terminal=None;display=None
            evidence=Path(os.environ.get('KEEPER_TEST_EVIDENCE_DIR',str(root)))
            number=next(n for n in range(150,220) if not Path(f'/tmp/.X{n}-lock').exists())
            env={**os.environ,'DISPLAY':':'+str(number),'XDG_CONFIG_HOME':str(root/'config'),
                 'XDG_DATA_HOME':str(root/'data-home'),'XDG_CACHE_HOME':str(root/'cache'),'TMPDIR':tempfile.gettempdir(),'GIO_USE_VFS':'local','GTK_USE_PORTAL':'0','NO_AT_BRIDGE':'1'}
            server=subprocess.Popen(['Xvfb',env['DISPLAY'],'-screen','0','1600x1100x24','-nolisten','tcp','-ac'],
                                    env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                x=C.CDLL('libX11.so.6');xt=C.CDLL('libXtst.so.6')
                x.XOpenDisplay.argtypes=[C.c_char_p];x.XOpenDisplay.restype=C.c_void_p
                deadline=time.monotonic()+5
                while not display and time.monotonic()<deadline:display=x.XOpenDisplay(env['DISPLAY'].encode());time.sleep(.05)
                self.assertTrue(display,'Isolated X display did not start')
                x.XSetInputFocus.argtypes=[C.c_void_p,C.c_ulong,C.c_int,C.c_ulong]
                x.XFlush.argtypes=[C.c_void_p];x.XCloseDisplay.argtypes=[C.c_void_p]
                x.XStringToKeysym.argtypes=[C.c_char_p];x.XStringToKeysym.restype=C.c_ulong
                x.XKeysymToKeycode.argtypes=[C.c_void_p,C.c_ulong];x.XKeysymToKeycode.restype=C.c_uint
                xt.XTestFakeMotionEvent.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_ulong]
                xt.XTestFakeButtonEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
                xt.XTestFakeKeyEvent.argtypes=[C.c_void_p,C.c_uint,C.c_int,C.c_ulong]
                (root/'fixture').mkdir()
                launch=Launch(root/'fixture',mode=mode,label='clipboard-'+mode,size=(140,42),
                              env_update={**{k:env[k] for k in ['DISPLAY','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_CACHE_HOME','GIO_USE_VFS','GTK_USE_PORTAL','NO_AT_BRIDGE']},
                                          'KEEPER_TEST_SCROLL':'1','KEEPER_TEST_INPUT_LOG':str(log)})
                state=launch.attached();meta=state['tmux']
                launch.wait(lambda:json.loads(launch.state_path.read_text())['tmux'].get('focus_requested'))
                bus=root/'dbus.conf'
                bus.write_text('<busconfig><type>session</type><listen>unix:abstract=keeper-clipboard-'+str(os.getpid())+'-'+root.name+'</listen><policy context="default"><allow own="*"/><allow send_destination="*"/><allow receive_sender="*"/></policy></busconfig>')
                runner=root/'terminal.sh'
                runner.write_text("#!/bin/bash\n/usr/libexec/gnome-terminal-server &\nkeeper_fixture_server=$!\nfor ((keeper_wait=0; keeper_wait<50; keeper_wait++)); do gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus --method org.freedesktop.DBus.NameHasOwner org.gnome.Terminal 2>/dev/null | rg -q true && break; sleep .1; done\ntrap 'kill $keeper_fixture_server 2>/dev/null; wait $keeper_fixture_server' EXIT\ngnome-terminal \"$@\"\n")
                terminal_log=open(evidence/('clipboard-gnome-'+mode+'.log'),'wb')
                terminal=subprocess.Popen(['dbus-run-session','--config-file',str(bus),'--','bash',str(runner),
                    '--window','--wait','--hide-menubar','--title=Keeper Clipboard Fixture','--geometry=140x42',
                    '--','tmux','-S',meta['socket'],'attach-session'],env=launch.env,stdout=subprocess.DEVNULL,stderr=terminal_log,start_new_session=True)
                terminal_log.close()
                def window():
                    result=subprocess.run(['xwininfo','-root','-tree'],env=env,capture_output=True,text=True,timeout=2)
                    # Terminal titles may change after tmux starts. Select the
                    # sole GNOME window by its stable application class.
                    match=re.search(r'(0x[0-9a-f]+).*\("gnome-terminal-server" "Gnome-terminal"\)',result.stdout)
                    if not match:match=re.search(r'(0x[0-9a-f]+).*Keeper Clipboard Fixture',result.stdout)
                    return int(match[1],16) if match else None
                handle=launch.wait(window)
                launch.wait(lambda:len(launch.tmux('list-clients').splitlines())==2)
                x.XSetInputFocus(display,handle,2,0);x.XFlush(display)
                time.sleep(.7)
                launch.tmux('select-pane','-t',meta['source'])
                # Scroll the actual terminal with a mouse wheel: it must enter
                # scrollback, not inject Up/Down or escape bytes into the host.
                xt.XTestFakeMotionEvent(display,-1,150,550,0)
                for _ in range(3):
                    xt.XTestFakeButtonEvent(display,4,1,0);xt.XTestFakeButtonEvent(display,4,0,0)
                x.XFlush(display)
                try:
                    launch.wait(lambda:launch.tmux('display-message','-p','-t',meta['source'],'#{pane_in_mode}')=='1')
                except AssertionError:
                    diagnostic=evidence/('clipboard-diagnostic-'+mode+'.txt')
                    diagnostic.write_text(subprocess.run(['xwininfo','-name','Keeper Clipboard Fixture'],env=env,capture_output=True,text=True).stdout+'\n'+launch.tmux('list-clients'))
                    if shutil.which('import'):subprocess.run(['import','-display',env['DISPLAY'],'-window','root',str(diagnostic.with_suffix('.png'))],env=env,capture_output=True,timeout=4)
                    raise
                self.assertFalse(log.exists() and log.read_bytes(),'Mouse wheel became host input')
                # Exercise the normal tmux copy action and its system clipboard
                # backend, selecting one known fixture line from real history.
                for action in ['bottom-line','cursor-up','start-of-line','begin-selection','end-of-line','copy-pipe-and-cancel']:
                    launch.tmux('send-keys','-t',meta['source'],'-X',action)
                def completed_copy():
                    value=subprocess.run(['xclip','-selection','clipboard','-out'],env=env,capture_output=True,timeout=3)
                    return value if value.returncode==0 and value.stdout else None
                copied=launch.wait(completed_copy)
                self.assertEqual(copied.returncode,0,'tmux copy did not reach the isolated clipboard')
                self.assertRegex(copied.stdout.decode(),r'(SCROLL_FIXTURE_\d{3}|COPY_FIXTURE_MARKER)')
                launch.wait(lambda:launch.tmux('display-message','-p','-t',meta['source'],'#{pane_in_mode}')=='0')
                time.sleep(.4) # allow tmux's display redraw to restore bracketed-paste mode
                # GNOME's actual Ctrl+Shift+V shortcut must deliver bracketed
                # paste intact, without submitting or rewriting it.
                def key(name,pressed):
                    code=x.XKeysymToKeycode(display,x.XStringToKeysym(name.encode()))
                    xt.XTestFakeKeyEvent(display,code,pressed,0)
                # Native Shift-selection and GNOME Ctrl+Shift+C must also
                # copy actual terminal text, independently of tmux copy mode.
                geometry=subprocess.run(['xwininfo','-id',hex(handle)],env=env,capture_output=True,text=True,check=True).stdout
                height=int(re.search(r'Height: (\d+)',geometry)[1])
                key('Shift_L',1)
                xt.XTestFakeMotionEvent(display,-1,75,height-36,0)
                for _ in range(2):
                    xt.XTestFakeButtonEvent(display,1,1,0);xt.XTestFakeButtonEvent(display,1,0,0)
                    x.XFlush(display);time.sleep(.06)
                key('Shift_L',0)
                key('Control_L',1);key('Shift_L',1);key('c',1);key('c',0);key('Shift_L',0);key('Control_L',0);x.XFlush(display)
                previous=copied.stdout
                def native_copy():
                    value=subprocess.run(['xclip','-selection','clipboard','-out'],env=env,capture_output=True,timeout=3).stdout
                    return value if value!=previous and re.search(rb'(SCROLL_FIXTURE_\d{3}|COPY_FIXTURE_MARKER)',value) else None
                copied_text=launch.wait(native_copy)
                time.sleep(.2)
                key('Control_L',1);key('Shift_L',1);key('v',1);key('v',0);key('Shift_L',0);key('Control_L',0);x.XFlush(display)
                expected=b'\x1b[200~'+copied_text+b'\x1b[201~'
                try:launch.wait(lambda:log.exists() and expected in log.read_bytes())
                except AssertionError:
                    raise AssertionError('Clipboard paste received '+repr(log.read_bytes() if log.exists() else b'')+'; expected '+repr(expected))
                self.assertNotIn(b'\r',log.read_bytes(),'Paste submitted a prompt')
                self.assertIsNone(launch.child.poll())
                if shutil.which('import'):subprocess.run(['import','-display',env['DISPLAY'],'-window','root',str(evidence/('clipboard-'+mode+'.png'))],env=env,capture_output=True,timeout=4)
            finally:
                if terminal is not None:
                    os.killpg(terminal.pid,signal.SIGTERM)
                    try:terminal.wait(timeout=5)
                    except subprocess.TimeoutExpired:terminal.kill();terminal.wait()
                if launch is not None:launch.close()
                if display:x.XCloseDisplay(display)
                server.terminate();server.wait(timeout=5)

    def test_side_mouse_copy_and_bracketed_paste(self):self.exercise('side')
    def test_top_mouse_copy_and_bracketed_paste(self):self.exercise('top')

if __name__=='__main__':unittest.main()
