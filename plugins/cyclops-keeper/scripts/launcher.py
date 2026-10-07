#!/usr/bin/env python3
"""Run the installed Codex and one independent Keeper window. Linux/GNOME candidate."""
import fcntl
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import termios
import time

sys.dont_write_bytecode = True
import launcher_link as attachment

FLAGS = {'--keeper': 'focus', '--keeper-side': 'side', '--keeper-top': 'top'}
VALUE_OPTIONS = {'-c', '--config', '-C', '--cd', '-m', '--model', '-p', '--profile',
                 '-s', '--sandbox', '-a', '--ask-for-approval', '-i', '--image',
                 '--enable', '--disable', '--remote', '--remote-auth-token-env',
                 '--local-provider', '--add-dir', '--output-last-message', '-o'}


def split_flags(argv):
    mode, forwarded, value, literal = None, [], False, False
    for arg in argv:
        if value or literal:
            forwarded.append(arg)
            value = False
        elif arg == '--':
            literal = True
            forwarded.append(arg)
        elif arg in FLAGS:
            if mode and mode != FLAGS[arg]:
                raise ValueError('Choose one Keeper view per launch.')
            mode = FLAGS[arg]
        else:
            forwarded.append(arg)
            value = arg in VALUE_OPTIONS
    return mode, forwarded


def codex_command():
    # Follow the normal launcher at every launch, including after Codex updates.
    path = os.environ.get('KEEPER_CODEX') or shutil.which('codex')
    if not path:
        raise ValueError('Codex is not on PATH.')
    return path


def installed_plugin():
    override = os.environ.get('KEEPER_PLUGIN_ROOT')
    if override:
        root = Path(override).resolve()
        if not (root/'scripts/terminal.py').is_file():
            raise ValueError('Keeper plugin root has no terminal renderer.')
        return root
    home = Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex')))
    base = home/'plugins/cache/cyclops-keeper/cyclops-keeper'
    available = []
    for root in base.glob('*'):
        try:
            manifest=json.loads((root/'.codex-plugin/plugin.json').read_text())
            version=tuple(int(v) for v in manifest['version'].split('.'))
            if (root/'scripts/launcher_link.py').is_file():
                available.append((version,root))
        except (OSError,ValueError,KeyError):
            pass
    if not available:
        raise ValueError('Installed Keeper has no launch attachment adapter. Install the reviewed Keeper candidate first.')
    return max(available)[1]


def project_directory(argv):
    folder = Path.cwd()
    for index, arg in enumerate(argv):
        if arg == '--': break
        if arg in {'-C','--cd'} and index+1 < len(argv): folder=Path(argv[index+1])
        elif arg.startswith('--cd='): folder=Path(arg.split('=',1)[1])
        elif arg.startswith('-C') and len(arg)>2: folder=Path(arg[2:])
    return folder.resolve()


def safe_runtime():
    root = Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}'))
    st = root.lstat()
    import stat
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise ValueError('Keeper needs a private XDG_RUNTIME_DIR (0700).')
    return root


def child_guard(parent_pid):
    # Linux clears this on fork, so each owned Codex child sets it before exec.
    import ctypes
    if ctypes.CDLL(None,use_errno=True).prctl(1,signal.SIGTERM,0,0,0) != 0:
        raise OSError('Cannot establish Codex launcher lifetime')
    if os.getppid()!=parent_pid: os._exit(125)


def run(mode, argv, real_codex, plugin):
    if not shutil.which('gnome-terminal'):
        raise ValueError('This candidate needs GNOME Terminal.')
    if not os.environ.get('DISPLAY') or os.environ.get('XDG_SESSION_TYPE') == 'wayland':
        raise ValueError('This candidate needs an X11 desktop for verified window focus and placement.')
    runtime = safe_runtime()
    # Duplicate flag requests and concurrent wrappers on the same launching tty
    # cannot create extra companion windows. Other Codex sessions get their own.
    tty = os.ttyname(0) if os.isatty(0) else f'pid-{os.getpid()}'
    import hashlib
    lock_path=runtime/('keeper-tty-'+hashlib.sha256(tty.encode()).hexdigest()[:16]+'.lock')
    lock_fd=os.open(lock_path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(lock_fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(lock_fd)
        raise ValueError('A Keeper launch already owns this terminal.')
    instance = Path(tempfile.mkdtemp(prefix='keeper-', dir=runtime))
    directory_fd=os.open(instance,os.O_RDONLY|os.O_DIRECTORY)
    socket_path=f'/proc/{os.getpid()}/fd/{directory_fd}/session.sock'
    state_path=instance/'attachment.json'
    token=secrets.token_hex(32)
    owner=attachment.process_identity(os.getpid())
    state={'v':1,'owner':owner,'session':None,'project_fd':None,'generation':0}
    attachment.atomic(state_path,state)
    original_tty=termios.tcgetattr(0) if os.isatty(0) else None
    child=window=placement=None
    project_fd=None
    stop=[None]
    previous={}
    for sig in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):
        previous[sig]=signal.getsignal(sig)
        signal.signal(sig,lambda number,_frame: stop.__setitem__(0,number) if number != signal.SIGINT else None)
    try:
        with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as broker:
            broker.setsockopt(socket.SOL_SOCKET,socket.SO_PASSCRED,1)
            broker.bind(socket_path)
            os.chmod(instance/'session.sock',0o600)
            broker.settimeout(.1)
            env=dict(os.environ,KEEPER_LAUNCH_SOCKET=socket_path,KEEPER_LAUNCH_TOKEN=token,
                     KEEPER_LAUNCH_OWNER=json.dumps(owner,separators=(',',':')))
            child=subprocess.Popen([real_codex,*argv],env=env,preexec_fn=lambda:child_guard(owner['pid']))
            state['codex']=attachment.process_identity(child.pid)
            attachment.atomic(state_path,state)
            from keeper_window import Window
            placement=Window()
            role='keeper-'+token[:16]
            command=['gnome-terminal','--window','--wait','--hide-menubar',
                     '--role='+role,'--title=Cyclops Keeper — '+mode,
                     '--working-directory='+str(project_directory(argv)),
                     '--geometry='+({'focus':'100x36','side':'54x36','top':'120x14'}[mode]),
                     '--',sys.executable,str(plugin/'scripts/terminal.py')]
            if mode == 'focus': command.append('focus')
            command += ['--attachment',str(state_path)]
            window=subprocess.Popen(command,stdin=subprocess.DEVNULL,start_new_session=True)
            focus_deadline=time.monotonic()+8
            focused=False
            placed=None
            focus_at=None
            while child.poll() is None and not stop[0]:
                try:
                    received=attachment.receive(broker,token)
                    if received:
                        key,new_fd=received
                        old_fd=project_fd
                        project_fd=new_fd
                        state.update(session=key,project_fd=new_fd,generation=state['generation']+1)
                        attachment.atomic(state_path,state)
                        if old_fd is not None: os.close(old_fd)
                except socket.timeout:
                    pass
                if not focused and time.monotonic()<focus_deadline:
                    handle=placement.find_role(role)
                    if handle and state_path.with_suffix('.ready').exists():
                        if placed is None:
                            placement.place(handle,mode)
                            placed=handle
                            focus_at=time.monotonic()+.35
                        elif time.monotonic()>=focus_at:
                            placement.focus(handle)
                            focused=True
                elif not focused:
                    print('Keeper: window focus was not confirmed. Select its window once.',file=sys.stderr)
                    focused=True
            if stop[0] and child.poll() is None:
                child.send_signal(stop[0])
            # Once Codex ends, close only this launch's Keeper renderer. Never
            # terminate the shared terminal server or a Link heartbeat worker.
            try: return child.wait(timeout=5 if stop[0] else None)
            except subprocess.TimeoutExpired: child.kill(); return child.wait()
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired: child.kill(); child.wait()
        try:
            ready=json.loads(state_path.with_suffix('.ready').read_text())
            if attachment.alive(ready): os.kill(ready['pid'],signal.SIGTERM)
        except (OSError,ValueError,TypeError):
            pass
        if window is not None:
            try: window.wait(timeout=3)
            except subprocess.TimeoutExpired: window.terminate(); window.wait(timeout=3)
        if placement is not None: placement.close()
        for sig,handler in previous.items(): signal.signal(sig,handler)
        if project_fd is not None: os.close(project_fd)
        os.close(directory_fd)
        # Only this newly created runtime directory is owned by this invocation.
        shutil.rmtree(instance)
        os.close(lock_fd)
        if original_tty is not None:
            try:
                termios.tcsetattr(0,termios.TCSANOW,original_tty)
                if os.isatty(1):
                    os.write(1,b'\x1b[0m\x1b[?25h\x1b[?1049l\x1b[?2004l\x1b[?1004l'
                               b'\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1006l\x1b[<u')
            except OSError: pass


def main():
    try:
        mode,argv=split_flags(sys.argv[1:])
        real=codex_command()
        if mode is None:
            os.execvpe(real,[real,*argv],os.environ)
        if os.environ.get('KEEPER_LAUNCH_SOCKET'):
            raise ValueError('Nested Keeper launches are refused; use ordinary Codex for the nested command.')
        if mode in {'side','top'}:
            from launcher_tmux import run as tmux_run
            status=tmux_run(mode,argv,real,installed_plugin())
        else:
            status=run(mode,argv,real,installed_plugin())
        return status if status>=0 else 128-status
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        print('Keeper: '+str(error),file=sys.stderr)
        return 2

if __name__ == '__main__': raise SystemExit(main())
