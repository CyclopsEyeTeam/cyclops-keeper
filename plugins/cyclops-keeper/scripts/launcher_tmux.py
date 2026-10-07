"""Owned tmux layouts. Codex executes unchanged; Keeper attaches through its host hook."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import signal
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import termios
import time

sys.dont_write_bytecode=True
import launcher_link as attachment
from launcher import child_guard,project_directory,safe_runtime

MIN_COLUMNS=60
MIN_ROWS=20
FORWARD_ENV=('CODEX_HOME','PLUGIN_DATA','KEEPER_DATA','XDG_CONFIG_HOME','XDG_STATE_HOME',
             'CYCLOPS_LINK_DIR','KEEPER_LINK','KEEPER_LINK_REACH','NO_COLOR','COLORTERM','LANG','LC_ALL')


def validate_size(mode,columns,rows):
    needed=(96,20) if mode=='side' else (60,35)
    if columns<needed[0] or rows<needed[1]:
        raise ValueError(f'Keeper {mode} needs at least {needed[0]} columns and {needed[1]} rows; use --keeper for a separate window.')


def tty_lock(runtime):
    tty=os.ttyname(0)
    path=runtime/('keeper-tty-'+hashlib.sha256(tty.encode()).hexdigest()[:16]+'.lock')
    fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd);raise ValueError('A Keeper launch already owns this terminal.')
    return fd


class Context:
    """An inspected server and source pane; no implicit default tmux target."""
    def __init__(self,binary,sock,server,pane,window,env):
        self.binary,self.socket,self.server,self.source,self.window,self.env=binary,sock,server,pane,window,env

    def call(self,*args,check=True):
        if not attachment.alive(self.server):raise ValueError('The inspected tmux server ended.')
        result=subprocess.run([self.binary,'-S',self.socket,*args],env=self.env,
                              capture_output=True,text=True,timeout=3)
        if check and result.returncode:raise ValueError('tmux could not complete the owned-pane operation: '+result.stderr.strip())
        return result.stdout.strip()

    @classmethod
    def inspect(cls,env=None):
        env=dict(os.environ if env is None else env)
        binary=env.get('KEEPER_TMUX') or shutil.which('tmux')
        if not binary:raise ValueError('tmux is required for Keeper side/top; use --keeper for a separate window.')
        pane=env.get('TMUX_PANE','')
        try:sock,advertised,_=env['TMUX'].rsplit(',',2);advertised=int(advertised)
        except (KeyError,ValueError):raise ValueError('Cannot verify the launching tmux session.')
        if not re.fullmatch(r'%[0-9]+',pane):raise ValueError('Cannot verify the launching tmux pane.')
        st=Path(sock).lstat()
        if not stat.S_ISSOCK(st.st_mode) or st.st_uid!=os.getuid():raise ValueError('Unsafe tmux socket.')
        server=attachment.process_identity(advertised)
        if not server:raise ValueError('The advertised tmux server ended.')
        ctx=cls(binary,sock,server,pane,None,env)
        raw=ctx.call('display-message','-p','-t',pane,'#{pid}|#{pane_tty}|#{window_id}')
        values=raw.split('|')
        if len(values)!=3 or values[0]!=str(advertised) or values[1]!=os.ttyname(0):
            raise ValueError('tmux does not identify this launching terminal; no pane was changed.')
        if not re.fullmatch(r'@[0-9]+',values[2]):raise ValueError('Cannot verify the launching tmux window.')
        ctx.window=values[2]
        return ctx

    def panes(self):
        rows=self.call('list-panes','-t',self.window,'-F',
                      '#{pane_id}|#{pane_pid}|#{pane_width}|#{pane_height}|#{@keeper_owner}')
        result={}
        for row in rows.splitlines():
            key,pid,width,height,owner=row.split('|')
            result[key]={'pid':int(pid),'width':int(width),'height':int(height),'owner':owner}
        return result

    def pane(self,key):
        raw=self.call('display-message','-p','-t',key,'#{pane_id}|#{pane_pid}|#{@keeper_owner}',check=False)
        if not raw:return None
        fields=raw.split('|')
        if len(fields)!=3 or fields[0]!=key:return None
        return {'pid':int(fields[1]),'owner':fields[2]}

    def owned(self,key,identity,token):
        try:
            value=self.pane(key)
            return value and value['owner']==token and value['pid']==identity['pid'] and attachment.alive(identity)
        except (ValueError,OSError,subprocess.SubprocessError):return False


def close_companion(ctx,key,identity,token,ready):
    if not key or not identity or not ctx.owned(key,identity,token):return
    try:
        panel=json.loads(ready.read_text())
        if panel==identity and attachment.alive(panel):os.kill(panel['pid'],signal.SIGTERM)
    except (OSError,ValueError):pass
    deadline=time.monotonic()+.7
    while ctx.owned(key,identity,token) and time.monotonic()<deadline:time.sleep(.05)
    if ctx.owned(key,identity,token):ctx.call('kill-pane','-t',key,check=False)


def restore_tty(attrs):
    try:
        termios.tcsetattr(0,termios.TCSANOW,attrs)
        os.write(1,b'\x1b[0m\x1b[?25h\x1b[?1049l\x1b[?2004l\x1b[?1004l'
                   b'\x1b[?1000l\x1b[?1002l\x1b[?1003l\x1b[?1006l\x1b[<u')
    except OSError:pass


def supervise(mode,argv,real_codex,plugin,parent=None):
    ctx=Context.inspect()
    source=ctx.panes()[ctx.source]
    validate_size(mode,source['width'],source['height'])
    runtime=safe_runtime();lock=tty_lock(runtime)
    instance=Path(tempfile.mkdtemp(prefix='keeper-',dir=runtime))
    directory=os.open(instance,os.O_RDONLY|os.O_DIRECTORY)
    address=f'/proc/{os.getpid()}/fd/{directory}/session.sock'
    path=instance/'attachment.json';token=secrets.token_hex(32)
    owner=attachment.process_identity(os.getpid())
    state={'v':1,'owner':owner,'session':None,'project_fd':None,'generation':0,
           'tmux':{'socket':ctx.socket,'server':ctx.server,'source':ctx.source,'window':ctx.window,'keeper':None,'focus_requested':False}}
    attachment.atomic(path,state)
    attrs=termios.tcgetattr(0);old_handlers={};stop=[None]
    for sig in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):
        old_handlers[sig]=signal.getsignal(sig)
        signal.signal(sig,lambda number,_:stop.__setitem__(0,number) if number!=signal.SIGINT else None)
    child=None;project_fd=None;pane=None;pane_identity=None
    try:
        with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as broker:
            broker.setsockopt(socket.SOL_SOCKET,socket.SO_PASSCRED,1);broker.bind(address)
            os.chmod(instance/'session.sock',0o600);broker.settimeout(.1)
            env=dict(os.environ,KEEPER_LAUNCH_SOCKET=address,KEEPER_LAUNCH_TOKEN=token,
                     KEEPER_LAUNCH_OWNER=json.dumps(owner,separators=(',',':')))
            child=subprocess.Popen([real_codex,*argv],env=env,preexec_fn=lambda:child_guard(owner['pid']))
            state['codex']=attachment.process_identity(child.pid);attachment.atomic(path,state)
            unset=[item for key in FORWARD_ENV if key not in os.environ for item in ['-u',key]]
            command='exec '+shlex.join(['/usr/bin/env',*unset,sys.executable,str(plugin/'scripts/terminal.py'),'--attachment',str(path)])
            options=['-b','-v','-l','14'] if mode=='top' else ['-h','-l','35']
            environment=[]
            for key in FORWARD_ENV:
                # Avoid inheriting an old server's different consent or data root.
                if key in os.environ:environment+=['-e',key+'='+os.environ[key]]
            pane=ctx.call('split-window','-d','-t',ctx.source,*options,'-c',str(project_directory(argv)),
                          *environment,'-P','-F','#{pane_id}',command)
            info=ctx.pane(pane);pane_identity=attachment.process_identity(info['pid']) if info else None
            if not pane_identity:raise ValueError('Keeper pane did not start.')
            ctx.call('set-option','-p','-t',pane,'@keeper_owner',token)
            ctx.call('set-option','-p','-t',pane,'remain-on-exit','off')
            state['tmux']['keeper']=pane;attachment.atomic(path,state)
            focused=False;focus_deadline=time.monotonic()+8;next_layout=0
            while child.poll() is None and not stop[0]:
                if parent and not attachment.alive(parent):stop[0]=signal.SIGTERM;break
                try:
                    receipt=attachment.receive(broker,token)
                    if receipt:
                        key,new_fd=receipt;old_fd=project_fd;project_fd=new_fd
                        state.update(session=key,project_fd=new_fd,generation=state['generation']+1)
                        attachment.atomic(path,state)
                        if old_fd is not None:os.close(old_fd)
                except socket.timeout:pass
                now=time.monotonic()
                if not focused and path.with_suffix('.ready').exists():
                    if ctx.owned(pane,pane_identity,token):ctx.call('select-pane','-t',pane)
                    state['tmux']['focus_requested']=True;attachment.atomic(path,state)
                    focused=True
                elif not focused and now>focus_deadline:focused=True
                if now>=next_layout:
                    next_layout=now+.5
                    if not ctx.owned(pane,pane_identity,token):continue
                    panes=ctx.panes();host=panes.get(ctx.source);companion=panes.get(pane)
                    if not host or not companion:continue
                    width=host['width']+(companion['width']+1 if mode=='side' else 0)
                    height=host['height']+(companion['height']+1 if mode=='top' else 0)
                    try:validate_size(mode,width,height)
                    except ValueError:
                        close_companion(ctx,pane,pane_identity,token,path.with_suffix('.ready'))
                        print('Keeper: companion closed after resize; Codex continues. Use --keeper for a separate window.',file=sys.stderr)
                        continue
                    # A shared multi-pane window owns its native resizing policy.
                    # Only two explicitly owned panes may be resized to fixed bounds.
                    if set(panes)=={ctx.source,pane}:
                        flag,desired=('-x','35') if mode=='side' else ('-y','14')
                        current=companion['width'] if mode=='side' else companion['height']
                        if current!=int(desired):ctx.call('resize-pane','-t',pane,flag,desired)
                    elif host['width']<MIN_COLUMNS or host['height']<MIN_ROWS:
                        close_companion(ctx,pane,pane_identity,token,path.with_suffix('.ready'))
            if stop[0] and child.poll() is None:child.send_signal(stop[0])
            try:return child.wait(timeout=5 if stop[0] else None)
            except subprocess.TimeoutExpired:child.kill();return child.wait()
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        close_companion(ctx,pane,pane_identity,token,path.with_suffix('.ready'))
        for sig,handler in old_handlers.items():signal.signal(sig,handler)
        if project_fd is not None:os.close(project_fd)
        os.close(directory);shutil.rmtree(instance,ignore_errors=True);os.close(lock)
        restore_tty(attrs)


def exchange(stream,value=None):
    if value is not None:
        stream.sendall(json.dumps(value,separators=(',',':')).encode()+b'\n');return
    raw=bytearray()
    limit=6*os.sysconf('SC_ARG_MAX')+65536 # JSON can escape each valid argv byte sixfold.
    while b'\n' not in raw:
        chunk=stream.recv(65536)
        if not chunk:raise ValueError('Keeper bootstrap ended before its request.')
        raw.extend(chunk)
        if len(raw)>limit:raise ValueError('Keeper bootstrap request exceeds process argument bounds.')
    return json.loads(raw.split(b'\n',1)[0])


def private(mode,argv,real_codex,plugin):
    binary=os.environ.get('KEEPER_TMUX') or shutil.which('tmux')
    if not binary:raise ValueError('tmux is required for Keeper side/top; use --keeper for a separate window.')
    width,height=os.get_terminal_size(0);validate_size(mode,width,height)
    runtime=safe_runtime();lock=tty_lock(runtime);attrs=termios.tcgetattr(0)
    instance=Path(tempfile.mkdtemp(prefix='keeper-tmux-',dir=runtime))
    directory=os.open(instance,os.O_RDONLY|os.O_DIRECTORY)
    physical_socket=str(instance/'tmux.sock')
    sock=physical_socket if len(os.fsencode(physical_socket))<100 else f'/proc/{os.getpid()}/fd/{directory}/tmux.sock'
    bootstrap=f'/proc/{os.getpid()}/fd/{directory}/bootstrap.sock'
    token=secrets.token_hex(32);owner=attachment.process_identity(os.getpid())
    attachment.atomic(instance/'owner.json',owner)
    config=instance/'tmux.conf';config.write_text('set -g status off\nset -g mouse on\nset -g history-limit 10000\nset -s set-clipboard external\n');config.chmod(0o600)
    session='keeper-'+token[:16]
    command='exec '+shlex.join([sys.executable,str(Path(__file__).resolve()),'--worker',bootstrap,token,str(instance),json.dumps(owner,separators=(',',':'))])
    child=None;server=None;owned_worker=None;stop=[None];old_handlers={}
    for sig in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):
        old_handlers[sig]=signal.getsignal(sig)
        signal.signal(sig,lambda number,_:stop.__setitem__(0,number) if number!=signal.SIGINT else None)
    try:
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as listener:
            listener.bind(bootstrap);os.chmod(instance/'bootstrap.sock',0o600);listener.listen(1);listener.settimeout(.1)
            env=dict(os.environ);env.pop('TMUX',None);env.pop('TMUX_PANE',None)
            child=subprocess.Popen([binary,'-S',sock,'-f',str(config),'new-session','-s',session,
                                    '-c',str(project_directory(argv)),'-x',str(width),'-y',str(height),command],
                                   env=env,preexec_fn=lambda:child_guard(owner['pid']))
            deadline=time.monotonic()+10;sent=False
            while child.poll() is None and not stop[0]:
                if not sent:
                    if time.monotonic()>deadline:raise ValueError('Keeper private tmux startup timed out.')
                    try:stream,_=listener.accept()
                    except socket.timeout:continue
                    with stream:
                        stream.settimeout(3)
                        pid,uid,_=struct.unpack('3i',stream.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
                        request=exchange(stream)
                        if uid!=os.getuid() or request.get('token')!=token or request.get('worker')!=attachment.process_identity(pid):
                            continue
                        owned_worker=request['worker']
                        server=attachment.process_identity(request.get('server'))
                        if not server:raise ValueError('Keeper private server ended during startup.')
                        exchange(stream,{'mode':mode,'argv':argv,'codex':real_codex,'plugin':str(plugin),
                                         'parent':owner,'outcome':str(instance/'outcome.json')})
                        sent=True
                else:time.sleep(.1)
            if stop[0] and child.poll() is None:child.send_signal(stop[0])
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait()
            try:return json.loads((instance/'outcome.json').read_text())['status']
            except (OSError,ValueError,KeyError):return 128+stop[0] if stop[0] else 2
    finally:
        if owned_worker and attachment.alive(owned_worker):
            os.kill(owned_worker['pid'],signal.SIGTERM)
            until=time.monotonic()+6
            while attachment.alive(owned_worker) and time.monotonic()<until:time.sleep(.05)
            if attachment.alive(owned_worker):os.kill(owned_worker['pid'],signal.SIGKILL)
        if child is not None and child.poll() is None:
            child.terminate()
            try:child.wait(timeout=3)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        # An owned server may acquire user-created panes. Never kill those.
        # The default exit-empty policy closes an empty private server itself.
        until=time.monotonic()+1
        while server and attachment.alive(server) and time.monotonic()<until:time.sleep(.05)
        preserve=bool(server and attachment.alive(server))
        if preserve:
            print('Keeper: additional panes remain on the private server; its runtime was preserved.',file=sys.stderr)
        for sig,handler in old_handlers.items():signal.signal(sig,handler)
        os.close(directory)
        if not preserve:shutil.rmtree(instance,ignore_errors=True)
        os.close(lock);restore_tty(attrs)


def worker(address,token,private_root,parent_json):
    root=Path(private_root);parent=json.loads(parent_json);outcome=root/'outcome.json'
    ctx=None;directory=None
    try:
        info=root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o700:
            raise ValueError('Unsafe private Keeper runtime.')
        if json.loads((root/'owner.json').read_text())!=parent:
            raise ValueError('Keeper runtime owner does not match its launch.')
        directory=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        # Keep our own socket handle valid if the outer process dies before
        # bootstrap. This also supports long HDD test-runtime paths.
        _,server,index=os.environ['TMUX'].rsplit(',',2)
        physical=str(root/'tmux.sock')
        sock=physical if len(os.fsencode(physical))<100 else f'/proc/{os.getpid()}/fd/{directory}/tmux.sock'
        os.environ['TMUX']=f'{sock},{server},{index}'
        ctx=Context.inspect()
        if not attachment.alive(parent):raise ValueError('Keeper launching process ended.')
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as stream:
            stream.settimeout(8);stream.connect(address)
            exchange(stream,{'token':token,'worker':attachment.process_identity(os.getpid()),'server':ctx.server['pid']})
            request=exchange(stream)
        if request.get('parent')!=parent or request.get('outcome')!=str(outcome):
            raise ValueError('Keeper bootstrap owner does not match its runtime.')
        # Only the owned private server gets an explicit clipboard backend.
        clipboard=None
        if os.environ.get('WAYLAND_DISPLAY') and shutil.which('wl-copy'):
            clipboard=shlex.join([shutil.which('wl-copy')])
        elif os.environ.get('DISPLAY') and shutil.which('xclip'):
            clipboard=shlex.join([shutil.which('xclip'),'-selection','clipboard','-in'])
        if clipboard:ctx.call('set-option','-g','copy-command',clipboard)
        if not attachment.alive(parent):raise ValueError('Keeper launching process ended.')
        status=supervise(request['mode'],request['argv'],request['codex'],Path(request['plugin']),parent)
        attachment.atomic(outcome,{'status':status})
        return status
    finally:
        if not attachment.alive(parent) and directory is not None:
            try:
                panes=ctx.call('list-panes','-a','-F','#{pane_id}').splitlines() if ctx else None
                if panes==[ctx.source] and json.loads((root/'owner.json').read_text())==parent:
                    shutil.rmtree(root)
            except (OSError,ValueError,subprocess.SubprocessError):pass
        if directory is not None:os.close(directory)


def run(mode,argv,real_codex,plugin):
    if not os.isatty(0) or not os.isatty(1):raise ValueError('Keeper side/top needs an interactive terminal; ordinary codex is unchanged.')
    if os.environ.get('TMUX'):return supervise(mode,argv,real_codex,plugin)
    return private(mode,argv,real_codex,plugin)


if __name__=='__main__':
    try:
        status=worker(*sys.argv[2:]) if sys.argv[1:2]==['--worker'] else 2
        raise SystemExit(status if status>=0 else 128-status)
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        print('Keeper: '+str(error),file=sys.stderr);raise SystemExit(2)
