#!/usr/bin/env python3
"""Keeper's side of Cyclops Link: his semantic adapter, his heartbeat worker, his switch.

  hook.py  -> observe(data, payload)   after Keeper's own activity record is written
  worker   -> keeper_link.py beat <data> <session-key>   one per Codex session, detached
  person   -> ./keeper link on | off | status

The adapter turns Codex hook facts into the few things Link may carry: Keeper's coarse
state and how many tools and branches are in flight. Nothing else leaves it: no command,
prompt, path, tool name, call id or session id is written anywhere.

Reach is a second, separate choice. It never authorizes reading tool arguments.
The current Codex hook adapter supplies no permitted outgoing-target evidence;
Keeper therefore publishes no inferred outgoing calls. Incoming threads remain
owned by the peers that reported them.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.dont_write_bytecode = True
import link  # noqa: E402  Keeper's own Link V1

# Keeper's own states, in Link's vocabulary. 'unknown' says nothing, so it is never published.
STATE = {'idle': 'idle', 'working': 'working', 'tool': 'tool', 'branching': 'working',
         'compacting': 'compacting', 'waiting': 'waiting', 'stopped': 'stopped',
         'interrupted': 'interrupted', 'ended': 'ended'}
POLL = .25
NO_HOST_LINGER = 20.0


def reach_path(environ=None):
    return link.config_path(environ).with_name('link-reach')


def reach_enabled(environ=None):
    """The separate consent switch; it never grants tool-argument observation."""
    env = os.environ if environ is None else environ
    override = env.get('KEEPER_LINK_REACH', '').strip().lower()
    if override in {'1', 'on', 'true', 'yes'}:
        return True
    if override in {'0', 'off', 'false', 'no'}:
        return False
    try:
        return reach_path(env).read_text().strip() == 'on'
    except OSError:
        return False


def _digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def reaching_for(_tool_input):
    """Legacy adapter entry: tool arguments are never permitted target evidence."""
    return None


# ---------------------------------------------------------------- where Keeper keeps his own Link facts

def private_dir(data):
    path = Path(data) / 'link'
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or (path.stat().st_mode & 0o077):
        raise OSError('Keeper link directory is not private')
    return path


def read_private(data, key):
    try:
        path = private_dir(data) / (key + '.json')
        if path.is_symlink() or path.stat().st_size > 65536:
            return None
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) and value.get('v') == 1 else None
    except (OSError, ValueError):
        return None


def write_private(data, key, value):
    directory = private_dir(data)
    fd, name = tempfile.mkstemp(prefix=key + '-', suffix='.tmp', dir=directory)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, separators=(',', ':'))
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, directory / (key + '.json'))
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


# ---------------------------------------------------------------- is Codex still there

def _proc_parent(pid):
    try:
        stat = Path(f'/proc/{pid}/stat').read_text()
        fields = stat[stat.rindex(')') + 2:].split()
        return int(fields[1]), Path(f'/proc/{pid}/comm').read_text().strip(), fields[19]
    except (OSError, ValueError, IndexError):
        pass
    try:
        out = subprocess.run(['ps', '-o', 'ppid=', '-o', 'lstart=', '-o', 'comm=', '-p', str(pid)],
                             capture_output=True, text=True, timeout=2).stdout.split()
        return int(out[0]), os.path.basename(out[-1]), ' '.join(out[1:-1])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


def find_host():
    """The Codex process this hook runs under: its pid and start stamp, or None when it can't be told."""
    pid = os.getppid()
    for _ in range(12):
        if pid <= 1:
            return None
        info = _proc_parent(pid)
        if info is None:
            return None
        parent, comm, start = info
        if comm.startswith('codex'):
            return {'pid': pid, 'start': start}
        pid = parent
    return None


def host_alive(host):
    """True / False when Keeper can tell, None when he can't (then he never claims an end)."""
    if not isinstance(host, dict) or not isinstance(host.get('pid'), int):
        return None
    info = _proc_parent(host['pid'])
    if info is None:
        return False
    return info[1].startswith('codex') and info[2] == host.get('start')


# ---------------------------------------------------------------- the adapter (from hook.py)

def observe(data, payload, environ=None):
    """After Keeper's own record for this event is written: update his Link facts, wake his worker."""
    env = os.environ if environ is None else environ
    session = payload.get('session_id')
    event = payload.get('hook_event_name')
    if not isinstance(session, str) or not session or len(session) > 256:
        return
    key = _digest(session)
    if not link.enabled(env):
        return  # the worker notices the switch and ends what it published
    directory = private_dir(data)
    with open(directory / (key + '.lock'), 'a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        mine = read_private(data, key) or {'v': 1, 'reach_calls': {}}
        if 'instance' not in mine:
            link_root = link.prepare_dir(link.link_dir(env), create=True)
            salt = link.load_salt(link_root, create=True) if link_root else None
            if salt is None:
                return  # an unsafe Link directory is refused, quietly
            folder = payload.get('cwd') if isinstance(payload.get('cwd'), str) else os.getcwd()
            mine['instance'] = link.instance_for(salt, session)
            mine['room'] = link.room_for(salt, folder)
        if event == 'SessionStart' or 'host' not in mine:
            mine['host'] = find_host()
        try:
            record = json.loads((Path(data) / 'activity-face/sessions' / (key + '.json')).read_text())
        except (OSError, ValueError):
            record = {}
        # Discard legacy inferred calls, including previously persisted facts.
        # This adapter has no permitted host-level outgoing target evidence.
        calls = {}
        state = STATE.get(record.get('state'))
        mine.update({'state': state, 'reach_calls': calls,
                     'tools': int(record.get('active_tool_count') or 0),
                     'branches': int(record.get('active_subagent_count') or 0),
                     'reaching': sorted(set(calls.values())) if state not in {'stopped', 'interrupted', 'ended'} else [],
                     'changed_at': time.time()})
        write_private(data, key, mine)
    if state:
        start_worker(data, key, env)


def start_worker(data, key, environ=None):
    env = os.environ if environ is None else environ
    if env.get('KEEPER_LINK_NO_WORKER'):
        return  # tests drive the worker themselves
    try:
        with open(private_dir(data) / (key + '.beat'), 'a+') as probe:
            try:
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return  # already beating
            fcntl.flock(probe, fcntl.LOCK_UN)
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'beat', str(data), key],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         close_fds=True, start_new_session=True, cwd='/', env=dict(env))
    except OSError:
        pass


# ---------------------------------------------------------------- the worker

def beat(data, key, environ=None, *, poll=POLL, clock=time.time, sleep=time.sleep, max_seconds=None):
    """Publish Keeper's state for one Codex session while Codex lives; end truthfully; tidy after."""
    env = os.environ if environ is None else environ
    started = clock()
    with open(private_dir(data) / (key + '.beat'), 'a+') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 'busy'
        writer, published, checked, on, quiet_since = None, None, -1e9, True, clock()
        while max_seconds is None or clock() - started < max_seconds:
            mine = read_private(data, key)
            if not mine or not mine.get('instance'):
                return 'gone'
            if writer is None:
                writer = link.Writer(mine['instance'], mine['room'], env)
            now = clock()
            if now - checked >= 1:
                checked, on = now, link.enabled(env)
            alive = host_alive(mine.get('host'))
            if not on or mine.get('state') == 'ended' or alive is False:
                if published is not None:
                    writer.end(now=now)
                    return _linger(writer, data, key, clock, sleep, env)
                return 'off' if not on else 'ended'
            facts = (mine.get('state'), mine.get('tools', 0), mine.get('branches', 0), ())
            if facts[0] and facts != published:
                writer.publish(facts[0], tools=facts[1], branches=facts[2], reaching=facts[3], now=now)
                published, quiet_since = facts, now
            elif alive is True:
                writer.heartbeat(now=now)
            elif now - quiet_since > NO_HOST_LINGER:
                return 'no-host'  # can't tell whether Codex lives: let the record go stale, claim no end
            if writer.failures >= link.MAX_FAILURES or writer.refused:
                return 'refused'
            sleep(poll)
        return 'timeout'


def _linger(writer, data, key, clock, sleep, env):
    """Keep the ended record for the grace period, then remove Keeper's own file. A resumed session revives."""
    while clock() - (writer.ended_at or clock()) < link.END_GRACE_SECONDS:
        mine = read_private(data, key)
        if mine and mine.get('state') not in {None, 'ended'} and link.enabled(env) and host_alive(mine.get('host')) is not False \
                and mine.get('changed_at', 0) > (writer.ended_at or 0):
            return 'revived'
        sleep(1)
    writer.cleanup(now=clock())
    try:
        (private_dir(data) / (key + '.json')).unlink()
    except OSError:
        pass
    return 'ended'


# ---------------------------------------------------------------- ./keeper link on | off | status

def cli(argv, data, environ=None):
    env = os.environ if environ is None else environ
    word = argv[0] if argv else 'status'
    if word == 'reach' and len(argv) > 1 and argv[1] in {'on', 'off'}:
        path = reach_path(env)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(argv[1] + '\n')
        if argv[1] == 'on':
            print('Keeper reach on: outgoing threads require permitted host evidence.')
            print('This Codex adapter supplies no outgoing target evidence; tool arguments are never read.')
        else:
            print('Keeper reach off: he never looks at tool arguments, and never says whom he is reaching.')
        return 0
    if word in {'on', 'off'}:
        path = link.set_enabled(word == 'on', env)
        if word == 'on':
            print('Keeper Link on: he shares his coarse state and sees Spark and Prism working in the same folder.')
            print('Nothing else is shared: no prompts, commands, paths or names. Off again: ./keeper link off')
        else:
            print('Keeper Link off. His records say he has ended and are removed a minute later.')
        print(f'  (switch: {path})')
        return 0
    if word != 'status':
        print('usage: keeper link [on | off | status | reach on | reach off]')
        return 2
    on = link.enabled(env)
    print(f"Keeper Link: {'on' if on else 'off'}" + ('  (KEEPER_LINK overrides the switch)' if env.get('KEEPER_LINK') else '')
          + f"  · reach {'on' if reach_enabled(env) else 'off'}")
    if not on:
        print('  Turn on: ./keeper link on')
        return 0
    import link_view
    from activity import public_snapshot
    try:
        latest = next(iter(public_snapshot(data)['sessions']), None)
    except Exception:
        latest = None
    view = link_view.Watch(data, env).view(latest['session'] if latest else None)
    print('  ' + link_view.status(view))
    for peer in (view or {}).get('peers', []):
        print(f"  · {peer['presence']} {peer['state']}  tools {peer['tools']}  branches {peer['branches']}")
    for thread in (view or {}).get('threads', []):
        print(f"  · thread {thread['from']} → {thread['to']}")
    return 0


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'beat':
        try:
            beat(sys.argv[2], sys.argv[3])
        except Exception:
            pass
