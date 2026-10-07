"""Private, per-launch session attachment. No activity, Link consent or host decisions."""
import array
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import socket
import stat
import struct
import tempfile

HEX = re.compile(r'^[0-9a-f]{64}$')


def process_identity(pid):
    try:
        raw = Path(f'/proc/{pid}/stat').read_text()
        fields = raw[raw.rindex(')') + 2:].split()
        if fields[0] == 'Z':
            return None
        return {'pid': int(pid), 'start': fields[19]}
    except (OSError, ValueError, IndexError):
        return None


def alive(identity):
    return (isinstance(identity, dict) and type(identity.get('pid')) is int
            and process_identity(identity['pid']) == identity)


def descendant(pid, owner):
    if not alive(owner):
        return False
    for _ in range(64):
        if pid == owner['pid']:
            return True
        if pid <= 1:
            break
        try:
            raw = Path(f'/proc/{pid}/stat').read_text()
            pid = int(raw[raw.rindex(')') + 2:].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return False


def observe(payload, environ=None):
    env = os.environ if environ is None else environ
    path, token = env.get('KEEPER_LAUNCH_SOCKET'), env.get('KEEPER_LAUNCH_TOKEN', '')
    session = payload.get('session_id')
    if (not path or not HEX.fullmatch(token) or payload.get('hook_event_name') != 'SessionStart'
            or payload.get('source') not in {'startup', 'resume', 'clear', 'compact'}
            or payload.get('agent_id') or payload.get('agent_type')
            or not isinstance(session, str) or not 0 < len(session) <= 256):
        return
    owner_text=env.get('KEEPER_LAUNCH_OWNER')
    if owner_text:
        try:
            owner=json.loads(owner_text)
            if not alive(owner): return
            pid=os.getppid()
            while pid>1:
                raw=Path(f'/proc/{pid}/stat').read_text()
                parent=int(raw[raw.rindex(')')+2:].split()[1])
                comm=Path(f'/proc/{pid}/comm').read_text().strip()
                if comm.startswith('codex'):
                    if parent != owner['pid']: return
                    break
                pid=parent
            else: return
        except (OSError,ValueError,KeyError,TypeError): return
    directory = payload.get('cwd')
    if not isinstance(directory, str) or not os.path.isabs(directory):
        return
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.settimeout(.1)
            message = {'v': 1, 'token': token,
                       'session': hashlib.sha256(session.encode()).hexdigest()}
            sock.sendmsg([json.dumps(message, separators=(',', ':')).encode()],
                         [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [fd]))], 0, path)
    finally:
        os.close(fd)


def receive(sock, token):
    """Accept one local receipt; return (session hash, owned directory fd), or None.

    The random nonce is the per-launch capability. SO_PASSCRED pins it to this user;
    no shared-directory/session-recency inference participates in attachment.
    """
    raw, extra, flags, _ = sock.recvmsg(1024, socket.CMSG_SPACE(64) + socket.CMSG_SPACE(12))
    fds, credentials = array.array('i'), None
    try:
        for level, kind, value in extra:
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                fds.frombytes(value[:len(value) - len(value) % fds.itemsize])
            elif level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS:
                credentials = struct.unpack('3i', value[:12])
        value = json.loads(raw)
        if (flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC) or len(fds) != 1
                or not credentials or credentials[1] != os.getuid()
                or not isinstance(value, dict) or set(value) != {'v', 'token', 'session'}
                or type(value['v']) is not int or value['v'] != 1
                or not isinstance(value['token'], str) or not hmac.compare_digest(value['token'], token)
                or not isinstance(value['session'], str) or not HEX.fullmatch(value['session'])
                or not stat.S_ISDIR(os.fstat(fds[0]).st_mode)):
            return None
        os.set_inheritable(fds[0], False)
        return value['session'], fds.pop()
    except (ValueError, TypeError, OSError, KeyError, struct.error):
        return None
    finally:
        for fd in fds:
            os.close(fd)


def atomic(path, value):
    path = Path(path)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.keeper-')
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(value, out, separators=(',', ':'))
        os.replace(temporary, path)
    finally:
        try: os.unlink(temporary)
        except FileNotFoundError: pass


def read_attachment(path):
    path = Path(path)
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077 or st.st_size > 4096:
        raise ValueError('Unsafe Keeper attachment')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as stream:
        value = json.load(stream)
    if not isinstance(value, dict) or value.get('v') != 1 or not alive(value.get('owner')):
        raise ValueError('Keeper launcher ended')
    generation=value.get('generation',0)
    if type(generation) is not int or generation<0:
        raise ValueError('Invalid Keeper attachment generation')
    session = value.get('session')
    if session is not None and (not isinstance(session, str) or not HEX.fullmatch(session)):
        raise ValueError('Invalid Keeper attachment')
    return value


def cleanup_dead_launcher(path):
    """Remove this launch's small private runtime files after its owner has died."""
    path=Path(path)
    try:
        st=path.parent.lstat()
        if (not path.parent.name.startswith('keeper-') or not stat.S_ISDIR(st.st_mode)
                or st.st_uid!=os.getuid() or st.st_mode & 0o077): return False
        value=json.loads(path.read_text())
        owner=value.get('owner')
        if not isinstance(owner,dict) or type(owner.get('pid')) is not int or alive(owner): return False
        files=list(path.parent.iterdir())
        allowed={path.name,path.with_suffix('.ready').name,'session.sock'}
        if any(p.name not in allowed and not p.name.startswith('.keeper-') for p in files): return False
        for item in files: item.unlink(missing_ok=True)
        path.parent.rmdir()
        return True
    except (OSError,ValueError,TypeError,AttributeError): return False
