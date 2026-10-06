"""Small observational activity-face/v1 protocol. Python standard library only."""
import fcntl
import hashlib
import heapq
import json
import math
import os
from pathlib import Path
import tempfile
import time

PROTOCOL = 'activity-face/v1'
RIBBON_LIMIT = 32
RELATION_LIMIT = 256
MAX_RECORD_BYTES = 4 * 1024 * 1024
EVENTS = {'SessionStart', 'UserPromptSubmit', 'PreToolUse', 'PermissionRequest',
          'PostToolUse', 'Stop', 'Interrupt', 'SessionEnd', 'PreCompact',
          'PostCompact', 'SubagentStart', 'SubagentStop'}
TURN_EVENTS = {'UserPromptSubmit', 'PreToolUse', 'PermissionRequest', 'PostToolUse',
               'Stop', 'Interrupt', 'PreCompact', 'PostCompact',
               'SubagentStart', 'SubagentStop'}
TERMINAL = {'stopped', 'interrupted', 'ended'}
STATES = {'unknown', 'idle', 'working', 'tool', 'branching', 'compacting',
          'waiting', *TERMINAL}
TOOL_KINDS = {'inspect', 'change', 'execute', 'service', 'other'}
LABELS = {'unknown': 'NO SIGNAL YET', 'idle': 'SESSION READY', 'working': 'WORKING',
          'tool': 'TOOL ACTIVITY', 'branching': 'PARALLEL WORK', 'compacting': 'CONTEXT FOLD',
          'waiting': 'APPROVAL REQUESTED', 'stopped': 'TURN STOPPED',
          'interrupted': 'INTERRUPTED', 'ended': 'SESSION ENDED'}


def digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _turn_key(value):
    return digest(value) if isinstance(value, str) and value else None


def _tool_kind(name):
    """Reduce an observed host tool name to a deliberately small visual class."""
    if not isinstance(name, str) or len(name) > 256:
        return 'other'
    lowered = name.casefold()
    if lowered.startswith('mcp__'):
        return 'service'
    if lowered in {'apply_patch', 'edit', 'write', 'file_change'}:
        return 'change'
    if lowered in {'bash', 'shell', 'terminal', 'exec_command', 'command'}:
        return 'execute'
    if lowered in {'read', 'read_file', 'open', 'grep', 'glob', 'list',
                   'search', 'find', 'file_search', 'ripgrep'}:
        return 'inspect'
    return 'other'


def _valid_key(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _load_active(old, field, kind_field=None):
    raw = old.get(field, {})
    if not isinstance(raw, dict):
        return {}
    active = {}
    prior_turn = old.get('_turn_key') if _valid_key(old.get('_turn_key')) else _turn_key(old.get('turn_id'))
    for key, value in raw.items():
        if not _valid_key(key):
            continue
        if isinstance(value, dict):
            sequence = value.get('sequence', old.get('sequence', 0))
            if not isinstance(sequence, int) or sequence < 0:
                sequence = 0
            entry = {'turn_key': value.get('turn_key') if _valid_key(value.get('turn_key')) else prior_turn,
                     'sequence': sequence}
            if kind_field:
                entry['kind'] = value.get('kind') if value.get('kind') in TOOL_KINDS else 'other'
            active[key] = entry
        elif value is True:  # Upgrade the original v1 Boolean call map without losing it.
            entry = {'turn_key': prior_turn, 'sequence': old.get('sequence', 0)}
            if kind_field:
                entry['kind'] = 'other'
            active[key] = entry
    return active


def _load_ribbon(old):
    raw = old.get('_transitions', [])
    if not isinstance(raw, list):
        return []
    ribbon = []
    for item in raw[-RIBBON_LIMIT:]:
        if not isinstance(item, dict) or item.get('event') not in EVENTS:
            continue
        sequence, at = item.get('sequence'), item.get('at')
        if not isinstance(sequence, int) or sequence < 1 or not isinstance(at, (int, float)) or not math.isfinite(at):
            continue
        key = item.get('key') if _valid_key(item.get('key')) else None
        kind = item.get('kind') if item.get('kind') in TOOL_KINDS else None
        ribbon.append({'sequence': sequence, 'event': item['event'], 'at': at,
                       'kind': kind, 'key': key})
    return ribbon


def _active_state(tools, agents, current_turn_key):
    if current_turn_key and any(x.get('turn_key') == current_turn_key for x in tools.values()):
        return 'tool'
    if current_turn_key and any(x.get('turn_key') == current_turn_key for x in agents.values()):
        return 'branching'
    return 'working'


def update(data, payload):
    event = payload.get('hook_event_name')
    session = payload.get('session_id')
    turn = payload.get('turn_id')
    if (event not in EVENTS or not isinstance(session, str) or not session
            or len(session) > 256):
        return
    if turn is not None and (not isinstance(turn, str) or len(turn) > 256):
        return
    if event == 'SessionStart' and payload.get('source') not in {'startup', 'resume', 'clear', 'compact'}:
        return
    if event in {'PreCompact', 'PostCompact'} and payload.get('trigger') not in {'manual', 'auto'}:
        return

    key = digest(session)
    directory = Path(data) / 'activity-face/sessions'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = directory / (key + '.lock')
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        deadline = time.monotonic() + 0.8
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    return
                time.sleep(0.005)
        target = directory / (key + '.json')
        try:
            if target.is_symlink() or target.stat().st_size > MAX_RECORD_BYTES:
                return
            old = json.loads(target.read_text())
            if not isinstance(old, dict) or old.get('schema') != PROTOCOL:
                old = {}
        except (OSError, ValueError):
            old = {}

        sequence = old.get('sequence', 0)
        if not isinstance(sequence, int) or sequence < 0:
            sequence = 0
        sequence += 1
        old_state = old.get('state') if old.get('state') in STATES else 'unknown'
        old_turn = old.get('_turn_key') if _valid_key(old.get('_turn_key')) else _turn_key(old.get('turn_id'))
        old_turn_key = old_turn
        turn_key = _turn_key(turn)
        late = bool(event in TURN_EVENTS and event != 'UserPromptSubmit'
                    and old_turn_key and turn_key and turn_key != old_turn_key)

        tools = _load_active(old, '_tools', kind_field='kind')
        incomplete = bool(old.get('relations_incomplete'))
        if len(tools) > RELATION_LIMIT:
            tools = dict(list(tools.items())[:RELATION_LIMIT]); incomplete = True
        agents = _load_active(old, '_subagents')
        if len(agents) > RELATION_LIMIT:
            agents = dict(list(agents.items())[:RELATION_LIMIT]); incomplete = True
        ribbon = _load_ribbon(old)
        call_id = payload.get('tool_use_id')
        call_key = digest(call_id) if isinstance(call_id, str) and 0 < len(call_id) <= 256 else None
        agent_id = payload.get('agent_id')
        agent_key = digest(agent_id) if isinstance(agent_id, str) and 0 < len(agent_id) <= 256 else None
        kind = _tool_kind(payload.get('tool_name')) if event in {'PreToolUse', 'PostToolUse', 'PermissionRequest'} else None
        matched_tool_key = None
        matched_agent_key = None
        at = time.time()
        current_turn_key = turn_key if event == 'UserPromptSubmit' and turn_key else (turn_key or old_turn_key)
        state = old_state
        event_for_state = not late
        current_record_event = old.get('event') if isinstance(old.get('event'), str) else None

        if event == 'SessionStart':
            source = payload.get('source')
            if source in {'startup', 'clear'}:
                state = 'idle'
                current_record_event = event
                old_turn = turn_key
                current_turn_key = turn_key
            elif source == 'resume':
                # Resume is an observed session transition even after the prior
                # run stopped. Keep unresolved exact calls and the old turn when
                # the host does not supply a replacement turn id.
                state = 'idle'
                current_record_event = event
                if turn is not None:
                    old_turn = turn_key
                    current_turn_key = turn_key
            # A compact-origin start is accepted but does not invent ready/working.
            elif source == 'compact' and old_state == 'unknown':
                state = 'unknown'
                current_record_event = event
                old_turn = turn_key
                current_turn_key = turn_key
        elif event == 'UserPromptSubmit':
            state = 'working'
            current_record_event = event
            old_turn = turn_key
            current_turn_key = turn_key
        elif event == 'PreToolUse':
            if call_key and (call_key in tools or len(tools) < RELATION_LIMIT):
                tools[call_key] = {'turn_key': turn_key, 'kind': kind, 'sequence': sequence}
            if call_key and call_key not in tools:incomplete = True
            if event_for_state and state not in TERMINAL:
                state = 'tool'
                current_record_event = event
                old_turn = turn_key if turn is not None else old_turn
                current_turn_key = turn_key or old_turn_key
        elif event == 'PostToolUse':
            active = tools.get(call_key) if call_key else None
            if active and (not turn_key or not active.get('turn_key') or active['turn_key'] == turn_key):
                matched_tool_key = call_key
                tools.pop(call_key, None)
            if event_for_state and state not in TERMINAL:
                state = _active_state(tools, agents, current_turn_key)
                current_record_event = event
                old_turn = turn_key if turn is not None else old_turn
        elif event == 'PermissionRequest':
            if event_for_state and state not in TERMINAL:
                state = 'waiting'
                current_record_event = event
                old_turn = turn_key if turn is not None else old_turn
                current_turn_key = turn_key or old_turn_key
        elif event == 'SubagentStart':
            if agent_key and (agent_key in agents or len(agents) < RELATION_LIMIT):
                agents[agent_key] = {'turn_key': turn_key, 'sequence': sequence}
            if agent_key and agent_key not in agents:incomplete = True
            if event_for_state and state not in TERMINAL:
                state = 'branching'
                current_record_event = event
                old_turn = turn_key if turn is not None else old_turn
                current_turn_key = turn_key or old_turn_key
        elif event == 'SubagentStop':
            active = agents.get(agent_key) if agent_key else None
            if active and (not turn_key or not active.get('turn_key') or active['turn_key'] == turn_key):
                matched_agent_key = agent_key
                agents.pop(agent_key, None)
            if event_for_state and state not in TERMINAL:
                state = _active_state(tools, agents, current_turn_key)
                current_record_event = event
                old_turn = turn_key if turn is not None else old_turn
        elif event == 'PreCompact':
            if event_for_state and state not in TERMINAL:
                old['_state_before_compaction'] = state
                state = 'compacting'
                current_record_event = event
                old_turn = turn_key if turn is not None else old_turn
                current_turn_key = turn_key or old_turn_key
        elif event == 'PostCompact':
            if event_for_state and state not in TERMINAL:
                before = old.pop('_state_before_compaction', None)
                state = before if before in STATES and before != 'compacting' else _active_state(tools, agents, current_turn_key)
                current_record_event = event
                old_turn = turn_key if turn is not None else old_turn
        elif event == 'Stop':
            if event_for_state:
                state = 'stopped'
                current_record_event = event
                old_turn = turn_key if turn is not None else old_turn
                current_turn_key = turn_key or old_turn_key
        elif event == 'Interrupt':
            if event_for_state:
                state = 'interrupted'
                current_record_event = event
                old_turn = turn_key if turn is not None else old_turn
                current_turn_key = turn_key or old_turn_key
        elif event == 'SessionEnd':
            state = 'ended'
            current_record_event = event
            # Keep outstanding exact IDs until their own return hook arrives.

        transition_key = (call_key if event == 'PreToolUse' else matched_tool_key
                          if event == 'PostToolUse' else agent_key
                          if event == 'SubagentStart' else matched_agent_key
                          if event == 'SubagentStop' else None)
        transition = {'sequence': sequence, 'event': event, 'at': at,
                      'kind': kind, 'key': transition_key}
        ribbon.append(transition)
        ribbon = ribbon[-RIBBON_LIMIT:]
        record = {'schema': PROTOCOL, 'provider': 'codex', 'session': key,
                  '_turn_key': old_turn, 'relations_incomplete': incomplete, 'state': state, 'event': current_record_event,
                  'updated_at': at, 'sequence': sequence,
                  'active_tool_count': len(tools), '_tools': tools,
                  'active_subagent_count': len(agents), '_subagents': agents,
                  '_transitions': ribbon}
        if '_state_before_compaction' in old:
            record['_state_before_compaction'] = old['_state_before_compaction']
        fd, name = tempfile.mkstemp(prefix=key + '-', suffix='.tmp', dir=directory)
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(record, f, separators=(',', ':'))
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, target)
        finally:
            try:
                os.unlink(name)
            except FileNotFoundError:
                pass


def _public_active(raw, with_kind=False):
    if not isinstance(raw, dict):
        return []
    result = []
    for key, value in raw.items():
        if not _valid_key(key) or not isinstance(value, dict):
            continue
        sequence = value.get('sequence')
        if not isinstance(sequence, int) or sequence < 0:
            continue
        entry = {'key': key, 'sequence': sequence}
        if with_kind:
            entry['kind'] = value.get('kind') if value.get('kind') in TOOL_KINDS else 'other'
        result.append(entry)
    result.sort(key=lambda item: (item['sequence'], item['key']))
    return result


def public_snapshot(data, now=None, *, session=None, limit=128):
    now = time.time() if now is None else now
    sessions = []
    directory=Path(data)/'activity-face/sessions';count=0;cap=max(1,min(128,limit))
    def candidates():
        nonlocal count
        for path in directory.glob('*.json'):
            if not _valid_key(path.stem) or path.is_symlink():continue
            try:stamp=path.stat().st_mtime
            except OSError:continue
            count+=1;yield (stamp,str(path))
    if session is not None:
        selected=[directory/(session+'.json')] if _valid_key(session) else []
    else:selected=[Path(name) for _,name in heapq.nlargest(cap,candidates())]
    for path in selected:
        try:
            if path.is_symlink() or path.stat().st_size > MAX_RECORD_BYTES:
                continue
            s = json.loads(path.read_text())
            if (s.get('schema') != PROTOCOL or s.get('state') not in STATES
                    or not isinstance(s.get('updated_at'), (float, int))):
                continue
            entry = {k: s[k] for k in ['schema', 'provider', 'session', 'relations_incomplete',
                                      'state', 'event', 'updated_at', 'sequence'] if k in s}
            entry['active_tools'] = _public_active(s.get('_tools'), with_kind=True)
            entry['active_subagents'] = _public_active(s.get('_subagents'))
            entry['active_tool_count'] = len(entry['active_tools'])
            entry['active_subagent_count'] = len(entry['active_subagents'])
            entry['transitions'] = _load_ribbon(s)
            entry['stale'] = now - s['updated_at'] > 300
            sessions.append(entry)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
    sessions.sort(key=lambda s: s['updated_at'], reverse=True)
    return {'schema':PROTOCOL,'sessions':sessions,'truncated':session is None and count>cap}


def default_data():
    """Codex's installed data path, verified by the runtime smoke test."""
    if os.environ.get('PLUGIN_DATA'):
        return Path(os.environ['PLUGIN_DATA'])
    home = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
    return home / ('plugins/data/cyclops-keeper-' + os.environ.get('KEEPER_MARKETPLACE', 'cyclops-keeper'))
