"""Studio's neutral durable/live feed contract for Keeper's observed events."""
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
import uuid
import feed_state

ENTITY = 'keeper'
SESSION_ID = re.compile(r'^[A-Za-z0-9_-][A-Za-z0-9_.-]{0,79}$')
HASH = re.compile(r'^[0-9a-f]{64}$')
KINDS = {'inspect', 'change', 'execute', 'service', 'other'}
DURABLE_INTERVAL = 1.0
LIVE_INTERVAL = 0.2
HEARTBEAT_INTERVAL = 5.0
LIVE_WINDOW = 60.0
DURABLE_LIMIT = 512
PENDING_LIMIT = 256
LIVE_LIMIT = 256
MAX_FEED_BYTES = 2 * 1024 * 1024

HOST_TYPES = {
    'UserPromptSubmit': 'turn.receive',
    'PreToolUse': 'tool.start',
    'PermissionRequest': 'approval.request',
    'PostToolUse': 'tool.return',
    'Stop': 'turn.stop',
    'Interrupt': 'turn.interrupt',
    'SessionEnd': 'session.end',
    'PreCompact': 'context.fold',
    'PostCompact': 'context.unfold',
    'SubagentStart': 'branch.start',
    'SubagentStop': 'branch.return',
}
START_TYPES = {'startup': 'session.wake', 'resume': 'session.resume',
               'clear': 'session.clear', 'compact': 'session.compact'}
PUBLISHED_TYPES = set(HOST_TYPES.values()) | set(START_TYPES.values())


def studio_target(environ=None):
    """Return (feed root, Studio session id) only for a named Studio-owned session."""
    env = os.environ if environ is None else environ
    session = env.get('CYCLOPS_SESSION_ID')
    home = env.get('HOME')
    if not isinstance(session, str) or not SESSION_ID.fullmatch(session) or not home:
        return None
    override = env.get('CYCLOPS_PRESENCE_ROOT')
    if override:
        root = Path(override)
    else:
        state_home = Path(env.get('XDG_STATE_HOME') or Path(home) / '.local' / 'state')
        root = state_home / 'cyclops-presence'
    if not root.is_absolute():
        return None
    return root, session


def _finite_time(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def event_for_host(payload, sequence, *, at=None, key=None, kind=None, phase=None, incomplete=False):
    """Reduce one actual host hook to Keeper-owned vocabulary and safe scalar fields."""
    host_event = payload.get('hook_event_name') if isinstance(payload, dict) else None
    event_type = START_TYPES.get(payload.get('source')) if host_event == 'SessionStart' else HOST_TYPES.get(host_event)
    if event_type is None or not isinstance(sequence, int) or sequence < 1:
        return None
    stamp = time.time() if at is None else at
    if not _finite_time(stamp):
        return None
    event = {'seq': sequence, 't': float(stamp), 'type': event_type}
    if phase in feed_state.PHASES:event['phase'] = phase
    if incomplete:event['relationsIncomplete'] = True
    if isinstance(key, str) and HASH.fullmatch(key):
        event['key'] = key
    if kind in KINDS:
        event['kind'] = kind
    if host_event == 'SessionStart':
        event['source'] = payload.get('source')
    if host_event in {'PreCompact', 'PostCompact'}:
        trigger = payload.get('trigger')
        if trigger in {'manual', 'auto'}:
            event['trigger'] = trigger
    return event


def new_record(studio_session, *, run=None, started_at=None):
    if not isinstance(studio_session, str) or not SESSION_ID.fullmatch(studio_session):
        raise ValueError('invalid Studio session id')
    now = time.time() if started_at is None else started_at
    if not _finite_time(now):
        raise ValueError('invalid start time')
    return {'owner': hashlib.sha256(studio_session.encode()).hexdigest(),
            'v': 1, 'run': run or uuid.uuid4().hex, 'startedAt': float(now),
            'seq': 0, 'checkpoint': feed_state.empty(), 'pendingEvents': [], 'liveEvents': [], 'ended': False,
            'durableAt': None, 'liveAt': None, 'aliveAt': None,
            'durableDirty': False, 'liveDirty': False}


def _read_regular(path, limit=MAX_FEED_BYTES, *, prefix=False):
    """Never block on a FIFO/device or follow a linked external feed file."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise OSError('unsafe or oversized presence target')
        data = source.read(4096 if prefix else limit + 1)
        if len(data) > limit:
            raise OSError('oversized presence target')
        return data.decode('utf-8')


def binding(root, session):
    return hashlib.sha256((str(Path(root).absolute()) + '\0' + session).encode()).hexdigest()


def _durable_header(path):
    """Read the small fixed header without loading the full durable history."""
    try:
        prefix = _read_regular(path, prefix=True)
    except FileNotFoundError:
        return None
    marker = prefix.find(',"checkpoint":')
    if marker < 0:marker = prefix.find(',"events":[')
    if marker < 0:
        raise ValueError('invalid durable presence header')
    header = json.loads(prefix[:marker] + '}')
    if (not isinstance(header, dict) or header.get('v') != 1
            or not isinstance(header.get('run'), str)
            or not isinstance(header.get('seq'), int) or isinstance(header.get('seq'), bool)
            or header['seq'] < 0):
        raise ValueError('invalid durable presence header')
    return header


def _safe_stored_event(event):
    """Keep only Keeper's safe event fields when reusing a durable snapshot."""
    if (not isinstance(event, dict) or event.get('type') not in PUBLISHED_TYPES
            or not isinstance(event.get('seq'), int) or isinstance(event.get('seq'), bool)
            or event['seq'] < 1 or not _finite_time(event.get('t'))):
        raise ValueError('invalid durable presence event')
    result = {'seq': event['seq'], 't': float(event['t']), 'type': event['type']}
    if event.get('phase') in feed_state.PHASES:result['phase'] = event['phase']
    if event.get('relationsIncomplete') is True:result['relationsIncomplete'] = True
    if isinstance(event.get('key'), str) and HASH.fullmatch(event['key']):
        result['key'] = event['key']
    if event.get('kind') in KINDS:
        result['kind'] = event['kind']
    if event['type'] in set(START_TYPES.values()) and event.get('source') in START_TYPES:
        result['source'] = event['source']
    if event['type'] in {'context.fold', 'context.unfold'} and event.get('trigger') in {'manual', 'auto'}:
        result['trigger'] = event['trigger']
    return result


def reconcile(record, root, *, studio_session):
    """Recover a private feed cursor after a crash between external and private writes."""
    if not isinstance(record, dict) or record.get('v') != 1:
        return record
    if 'pendingEvents' not in record:
        legacy = record.pop('events', [])
        record['pendingEvents'] = legacy if isinstance(legacy, list) else []
    try:
        if (not isinstance(studio_session, str) or not SESSION_ID.fullmatch(studio_session)
                or hashlib.sha256(studio_session.encode()).hexdigest() != record.get('owner')):
            return record
        header = _durable_header(Path(root) / studio_session / 'keeper' / 'durable.json')
        if not header or header.get('run') != record.get('run'):
            return record
        persisted = header['seq']
        if persisted > record.get('publishedCheckpoint',{}).get('seq',0):
            history, _, checkpoint = _existing_durable(Path(root)/studio_session/'keeper/durable.json',record['run'])
            record['publishedCheckpoint'] = feed_state.advance(checkpoint,history)
        pending = [_safe_stored_event(item) for item in record.get('pendingEvents', [])]
        record['pendingEvents'] = [item for item in pending if item['seq'] > persisted]
        record['seq'] = max(record.get('seq', 0), persisted)
        record['durableDirty'] = bool(record['pendingEvents'])
    except (OSError, ValueError, TypeError, KeyError):
        return record
    return record


def append_host_event(record, payload, sequence=None, *, at=None, key=None, kind=None, phase=None, incomplete=False):
    if not isinstance(record, dict) or record.get('v') != 1:
        return record
    if 'pendingEvents' not in record:
        legacy = record.pop('events', [])
        record['pendingEvents'] = legacy if isinstance(legacy, list) else []
    next_sequence = record.get('seq', 0) + 1 if sequence is None else sequence
    event = event_for_host(payload, next_sequence, at=at, key=key, kind=kind, phase=phase, incomplete=incomplete)
    if event is None:
        return record
    record['seq'] = next_sequence
    record.setdefault('checkpoint', feed_state.empty())
    record.setdefault('pendingEvents', []).append(event)
    if len(record['pendingEvents']) > PENDING_LIMIT:
        dropped = record['pendingEvents'][:-PENDING_LIMIT]
        base=record['checkpoint']
        published=record.get('publishedCheckpoint')
        if isinstance(published,dict) and published.get('seq',0)>base.get('seq',0):base=published
        record['checkpoint'] = feed_state.advance(base, dropped)
        record['pendingEvents'] = record['pendingEvents'][-PENDING_LIMIT:]
    record.setdefault('liveEvents', []).append(event)
    stamp = event['t']
    record['liveEvents'] = [item for item in record['liveEvents']
                            if isinstance(item, dict) and _finite_time(item.get('t'))
                            and item['t'] >= stamp - LIVE_WINDOW]
    if not record['liveEvents'] or record['liveEvents'][-1] is not event:
        record['liveEvents'].append(event)
    record['liveEvents'] = record['liveEvents'][-LIVE_LIMIT:]
    record['durableDirty'] = True
    record['liveDirty'] = True
    if event['type'] == 'session.end':
        record['ended'] = True
    return record


def _safe_mkdir(path):
    path = Path(path)
    chain = list(reversed((path, *path.parents)))
    for item in chain:
        if item.exists() and item.is_symlink():
            raise OSError('presence path contains a symbolic link')
        if not item.exists():
            item.mkdir(mode=0o700)


def _atomic_json(path, value):
    if path.is_symlink():
        raise OSError('presence target is a symbolic link')
    fd, temporary = tempfile.mkstemp(prefix='.keeper-', suffix='.tmp', dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(value, output, separators=(',', ':'), ensure_ascii=True)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _durable(record, events):
    return {'v': 1, 'run': record['run'], 'startedAt': record['startedAt'],
            'seq': record['seq'], 'checkpoint': record.get('checkpoint', feed_state.empty()), 'events': events}


def _existing_durable(path, run):
    header = _durable_header(path)
    if not header or header['run'] != run:
        return [], 0, feed_state.empty()
    value = json.loads(_read_regular(path))
    if not isinstance(value, dict) or not isinstance(value.get('events'), list):
        raise ValueError('invalid durable presence snapshot')
    events = [_safe_stored_event(item) for item in value['events']]
    if any(left['seq'] >= right['seq'] for left, right in zip(events, events[1:])):
        raise ValueError('non-monotonic durable presence history')
    if events and events[-1]['seq'] > header['seq']:
        raise ValueError('durable presence sequence is behind its events')
    checkpoint=feed_state.safe(value.get('checkpoint'))
    if checkpoint['seq']>header['seq']:raise ValueError('checkpoint ahead of durable cursor')
    return events, header['seq'], checkpoint


def _live(record, now):
    return {'v': 1, 'run': record['run'], 'startedAt': record['startedAt'],
            'seq': record['seq'], 'checkpoint': record.get('checkpoint', feed_state.empty()),
            'events': record['liveEvents'],
            'aliveAt': float(now), 'ended': bool(record.get('ended'))}


def flush(record, root, *, studio_session, now=None, force=False, force_live=False):
    """Publish complete feed snapshots within the documented write cadences."""
    if not isinstance(record, dict) or record.get('v') != 1:
        return False
    stamp = time.time() if now is None else now
    if not _finite_time(stamp):
        return False
    if not isinstance(studio_session, str) or not SESSION_ID.fullmatch(studio_session):
        return False
    if hashlib.sha256(studio_session.encode()).hexdigest() != record.get('owner'):
        return False
    target = Path(root) / studio_session / 'keeper'
    first = record.get('durableAt') is None or record.get('liveAt') is None
    durable_due = force or first or (record.get('durableDirty') and
                                     stamp - (record.get('durableAt') or -math.inf) >= DURABLE_INTERVAL)
    heartbeat_due = record.get('aliveAt') is None or stamp - (record.get('aliveAt') or -math.inf) >= HEARTBEAT_INTERVAL
    live_due = force or force_live or first or (record.get('liveDirty') and
                                  stamp - (record.get('liveAt') or -math.inf) >= LIVE_INTERVAL)
    live_due = live_due or heartbeat_due
    if not durable_due and not live_due:
        return False
    _safe_mkdir(target)
    if durable_due:
        durable_path = target / 'durable.json'
        try:
            previous, persisted, checkpoint = _existing_durable(durable_path, record['run'])
            pending = [_safe_stored_event(item) for item in record.get('pendingEvents', [])]
        except (OSError, ValueError, TypeError, KeyError):
            return False
        additions = [item for item in pending if item['seq'] > persisted]
        local_checkpoint = record.get('checkpoint', feed_state.empty())
        if local_checkpoint['seq'] >= checkpoint['seq']:checkpoint = local_checkpoint
        events = [ev for ev in previous + additions if ev['seq'] > checkpoint['seq']]
        if len(events) > DURABLE_LIMIT:
            checkpoint = feed_state.advance(checkpoint, events[:-DURABLE_LIMIT])
            events = events[-DURABLE_LIMIT:]
        record['checkpoint'] = checkpoint
        latest_seq = max([record.get('seq', 0), persisted,
                          *(item['seq'] for item in additions)])
        record['seq'] = latest_seq
        try:
            _atomic_json(durable_path, _durable(record, events))
        except OSError:
            return False
        record['publishedCheckpoint'] = feed_state.advance(checkpoint,events)
        record['pendingEvents'] = [item for item in pending if item['seq'] > latest_seq]
        record['durableAt'] = stamp
        record['durableDirty'] = bool(record['pendingEvents'])
    if live_due:
        events = [item for item in record.get('liveEvents', [])
                  if isinstance(item, dict) and _finite_time(item.get('t'))
                  and item['t'] >= stamp - LIVE_WINDOW]
        latest = record.get('liveEvents', [])[-1] if record.get('liveEvents') else None
        if isinstance(latest, dict) and latest not in events:
            events.append(latest)
        record['liveEvents'] = events[-LIVE_LIMIT:]
        _atomic_json(target / 'live.json', _live(record, stamp))
        record['liveAt'] = stamp
        record['aliveAt'] = stamp
        record['liveDirty'] = False
    return True


def process_identity(pid):
    """Private Linux identity, stable across PID reuse; no command text retained."""
    try:
        pid=int(pid)
        fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        if pid<1 or fields[0] in {'Z','X'}:return None
        return {'pid':pid,'startTicks':int(fields[19])}
    except (OSError,ValueError,IndexError,TypeError):return None


def producer_alive(identity):
    return isinstance(identity,dict) and process_identity(identity.get('pid'))==identity


def producer_identity():
    """Nearest actual Codex ancestor; an ephemeral hook is never the producer."""
    pid=os.getppid()
    for _ in range(16):
        try:
            fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
            argv=Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\x00')
            is_codex=Path(os.readlink(f'/proc/{pid}/exe')).name=='codex' or any(
                Path(part.decode(errors='replace')).name=='codex' for part in argv[:2] if part)
            if is_codex:return process_identity(pid)
            parent=int(fields[1])
            if parent<1 or parent==pid:return None
            pid=parent
        except (OSError,ValueError,IndexError):return None
    return None


def start_worker(data_root, state_key, presence_root):
    if not isinstance(state_key, str) or not HASH.fullmatch(state_key):
        return
    try:
        sessions = Path(data_root) / 'activity-face' / 'sessions'
        _safe_mkdir(sessions)
        target = studio_target()
        if not target:return
        bound = binding(presence_root, target[1])
        lock_path = sessions / f'{state_key}.{bound}.presence-worker.lock'
        flags = os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
        probe_fd = os.open(lock_path, flags, 0o600)
        with os.fdopen(probe_fd, 'r+') as probe:
            try:
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            fcntl.flock(probe, fcntl.LOCK_UN)
        child_env = dict(os.environ)
        child_env['CYCLOPS_PRESENCE_ROOT'] = str(Path(presence_root))
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--heartbeat-worker',
                          str(Path(data_root)), state_key, str(Path(presence_root))],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True, start_new_session=True,
                         env=child_env)
    except (OSError, ValueError):
        return


def _worker(data_root, state_key, presence_root):
    sessions = Path(data_root) / 'activity-face' / 'sessions'
    state_path = sessions / f'{state_key}.json'
    lock_path = sessions / f'{state_key}.lock'
    feed_target = studio_target()
    if not feed_target:return
    bound = binding(presence_root, feed_target[1])
    worker_lock_path = sessions / f'{state_key}.{bound}.presence-worker.lock'
    _safe_mkdir(sessions)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
    worker_fd = os.open(worker_lock_path, flags, 0o600)
    with os.fdopen(worker_fd, 'r+') as worker_lock:
        try:
            fcntl.flock(worker_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        while True:
            lock_fd = os.open(lock_path, flags, 0o600)
            with os.fdopen(lock_fd, 'r+') as state_lock:
                try:
                    fcntl.flock(state_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    time.sleep(0.05)
                    continue
                try:
                    if state_path.is_symlink() or state_path.stat().st_size > 16 * 1024 * 1024:
                        return
                    state = json.loads(_read_regular(state_path, 16 * 1024 * 1024))
                    record = state.get('_presence_feed') if isinstance(state, dict) else None
                    if not isinstance(record, dict) or record.get('v') != 1:
                        return
                    feed_target = studio_target()
                    if (not feed_target or Path(feed_target[0]) != Path(presence_root)
                            or state.get('_presence_binding') != bound
                            or record.get('owner') != hashlib.sha256(feed_target[1].encode()).hexdigest()):
                        return
                    if not producer_alive(state.get('_producer')):
                        if record.get('durableDirty'):
                            stamp=record.get('aliveAt') or record.get('startedAt')
                            if flush(record,presence_root,studio_session=feed_target[1],now=stamp,force=True):
                                state['_presence_feed']=record;_atomic_json(state_path,state)
                        return
                    published = flush(record, presence_root, studio_session=feed_target[1])
                    if published:
                        state['_presence_feed'] = record
                        _atomic_json(state_path, state)
                    if record.get('ended') and not record.get('durableDirty'):
                        return
                except (OSError, ValueError, TypeError, KeyError):
                    return
            time.sleep(0.2)


if __name__ == '__main__' and len(sys.argv) == 5 and sys.argv[1] == '--heartbeat-worker':
    _worker(Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]))
