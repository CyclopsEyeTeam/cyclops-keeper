"""Bounded, content-free state checkpoints; restoring one is not an event."""
import copy
import math
import re

RELATION_LIMIT = 256
HASH = re.compile(r'^[a-f0-9]{64}$')
PHASES = {'unobserved', 'resting', 'receiving', 'working', 'tool', 'branching',
          'waiting', 'compacting', 'stopped', 'interrupted', 'ended'}
PHASE = {'unknown':'unobserved', 'idle':'resting', 'working':'working',
         'tool':'tool', 'branching':'branching', 'waiting':'waiting',
         'compacting':'compacting', 'stopped':'stopped',
         'interrupted':'interrupted', 'ended':'ended'}


def empty():
    return dict(seq=0, phase='unobserved', phaseBeforeFold='unobserved',
                lastEventAt=0, tools=[], branches=[], relationsIncomplete=False)


def safe(value):
    if value is None:return empty()
    if not isinstance(value,dict):raise ValueError('invalid checkpoint')
    state=empty()
    seq=value.get('seq',0)
    if not isinstance(seq,int) or isinstance(seq,bool) or seq<0:raise ValueError('invalid checkpoint sequence')
    state['seq']=seq
    for field in ['phase','phaseBeforeFold']:
        phase=value.get(field,'unobserved')
        if phase not in PHASES:raise ValueError('invalid checkpoint phase')
        state[field]=phase
    stamp=value.get('lastEventAt',0)
    if not isinstance(stamp,(int,float)) or isinstance(stamp,bool) or not math.isfinite(stamp):raise ValueError('invalid checkpoint time')
    state['lastEventAt']=stamp;state['relationsIncomplete']=value.get('relationsIncomplete') is True
    for field in ['tools','branches']:
        rows=value.get(field,[])
        if not isinstance(rows,list) or len(rows)>RELATION_LIMIT:raise ValueError('invalid checkpoint relations')
        seen=set()
        for row in rows:
            if not isinstance(row,dict) or not isinstance(row.get('key'),str) or not HASH.fullmatch(row['key']) or row['key'] in seen:raise ValueError('invalid checkpoint key')
            seen.add(row['key']);entry={'key':row['key']}
            if field=='tools':entry['kind']=row.get('kind') if row.get('kind') in {'inspect','change','execute','service','other'} else 'other'
            for scalar in ['seq','t']:
                v=row.get(scalar)
                if isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v):entry[scalar]=v
            state[field].append(entry)
    return state


def from_activity(record):
    result = empty()
    result.update(phase=PHASE.get(record.get('state'), 'unobserved'),
                  phaseBeforeFold=PHASE.get(record.get('_state_before_compaction'), 'working'),
                  lastEventAt=record.get('updated_at', 0),
                  relationsIncomplete=bool(record.get('relations_incomplete')))
    for field, source in [('tools', '_tools'), ('branches', '_subagents')]:
        for key, value in list(record.get(source, {}).items())[:RELATION_LIMIT]:
            if not HASH.fullmatch(key) or not isinstance(value, dict):continue
            entry = dict(key=key, seq=0, t=result['lastEventAt'])
            if field == 'tools':entry['kind'] = value.get('kind', 'other')
            result[field].append(entry)
    return result


def advance(checkpoint, events):
    state = safe(checkpoint)
    for ev in events:
        if ev['seq'] <= state['seq']:continue
        typ, key = ev['type'], ev.get('key')
        terminal = state['phase'] in {'waiting','stopped','interrupted','ended'}
        if typ in {'tool.start','branch.start'} and key:
            field = 'tools' if typ == 'tool.start' else 'branches'
            rows = {r['key']:r for r in state[field]}
            if key in rows or len(rows) < RELATION_LIMIT:
                rows[key] = dict(key=key, kind=ev.get('kind','other'), t=ev['t'], seq=ev['seq'])
            else:state['relationsIncomplete'] = True
            state[field] = list(rows.values())
            if not terminal:state['phase'] = 'tool' if field == 'tools' else 'branching'
        elif typ in {'tool.return','branch.return'} and key:
            field = 'tools' if typ == 'tool.return' else 'branches'
            state[field] = [r for r in state[field] if r['key'] != key]
            if not terminal:state['phase'] = 'tool' if state['tools'] else 'branching' if state['branches'] else 'working'
        elif typ in {'session.wake','session.resume','session.clear'}:state['phase'] = 'resting'
        elif typ == 'turn.receive':state['phase'] = 'receiving'
        elif typ == 'approval.request':state['phase'] = 'waiting'
        elif typ == 'turn.stop':state['phase'] = 'stopped'
        elif typ == 'turn.interrupt':state['phase'] = 'interrupted'
        elif typ == 'session.end':state['phase'] = 'ended'
        elif typ == 'context.fold':
            state['phaseBeforeFold'] = state['phase'];state['phase'] = 'compacting'
        elif typ == 'context.unfold':state['phase'] = state['phaseBeforeFold']
        if ev.get('phase') in PHASES:state['phase'] = ev['phase']
        if ev.get('relationsIncomplete'):state['relationsIncomplete'] = True
        state['seq'], state['lastEventAt'] = ev['seq'], ev['t']
    return state
