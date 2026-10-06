#!/usr/bin/env python3
"""Write visibly disposable host-event fixtures under tools/fixture-data/ only."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

root=Path(__file__).resolve().parents[1]
default_data=root/'tools/fixture-data'
script=root/'plugins/cyclops-keeper/scripts/hook.py'
events=['SessionStart','UserPromptSubmit','PreToolUse','PermissionRequest',
        'PostToolUse','Stop','Interrupt','SessionEnd','PreCompact','PostCompact',
        'SubagentStart','SubagentStop']
parser=argparse.ArgumentParser(description='Build clearly disposable Keeper host-event examples.')
parser.add_argument('event',choices=[*events,'stale','overlap','clear'])
parser.add_argument('--fixture',default='default',help='Disposable fixture namespace, letters, digits, dash, underscore only')
parser.add_argument('--count',type=int,default=1,help='Number of distinct calls or satellites to start (1-32)')
parser.add_argument('--tool-id',default='fixture-call',help='Disposable correlation id used only for matching this fixture')
parser.add_argument('--tool-name',choices=['Read','Glob','Grep','Bash','apply_patch','mcp__filesystem__read_file','FixtureOther'],default='Read')
parser.add_argument('--agent-id',default='fixture-agent',help='Disposable satellite correlation id')
parser.add_argument('--source',choices=['startup','resume','clear','compact'],default='startup')
parser.add_argument('--trigger',choices=['manual','auto'],default='auto')
args=parser.parse_args()
for label,value in [('fixture',args.fixture),('tool-id',args.tool_id),('agent-id',args.agent_id)]:
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,48}',value):parser.error(f'--{label} must use 1-48 safe fixture characters')
if not 1<=args.count<=32:parser.error('--count must be from 1 through 32')

# The environment override exists for isolated acceptance tests. Ordinary
# invocations always stay in the product's clearly named disposable directory.
data=Path(os.environ.get('KEEPER_FIXTURE_DATA',str(default_data))).resolve()
session='keeper-disposable-'+args.fixture
from hashlib import sha256
session_key=sha256(session.encode()).hexdigest()
target=data/'activity-face/sessions'/(session_key+'.json')
env={**os.environ,'PLUGIN_DATA':str(data),'PYTHONDONTWRITEBYTECODE':'1'}

def emit(event,tool_id=None,agent_id=None):
    payload={'hook_event_name':event,'session_id':session,'turn_id':'fixture-turn'}
    if event=='SessionStart':payload['source']=args.source
    if event in {'PreCompact','PostCompact'}:payload['trigger']=args.trigger
    if event=='PreToolUse':payload.update(tool_use_id=tool_id,tool_name=args.tool_name)
    if event=='PostToolUse':payload.update(tool_use_id=tool_id,tool_name=args.tool_name)
    if event=='PermissionRequest':payload.update(tool_use_id=tool_id,tool_name=args.tool_name)
    if event=='SubagentStart':payload.update(agent_id=agent_id,agent_type='fixture')
    if event=='SubagentStop':payload.update(agent_id=agent_id,agent_type='fixture')
    if event=='SessionEnd':payload['reason']='other'
    if event=='Stop':payload['stop_hook_active']=False
    result=subprocess.run([sys.executable,str(script)],input=json.dumps(payload),text=True,
                          capture_output=True,env=env,timeout=3)
    if (result.returncode,result.stdout.strip(),result.stderr)!=(0,'{}',''):
        raise RuntimeError(f'{event} fixture hook failed: {result.stderr or result.stdout}')

if args.event=='clear':
    target.unlink(missing_ok=True)
    print(f'Cleared fixture {args.fixture}')
elif args.event=='stale':
    if not target.is_file():parser.error('create fixture events before marking the fixture stale')
    record=json.loads(target.read_text());record['updated_at']=time.time()-301
    target.write_text(json.dumps(record,separators=(',',':')))
    print(f'Marked fixture {args.fixture} stale')
elif args.event=='overlap':
    target.unlink(missing_ok=True)
    emit('UserPromptSubmit')
    for tool_id,tool_name in [('inspect-a','Read'),('shell-b','Bash'),('service-c','mcp__filesystem__read_file')]:
        args.tool_name=tool_name;emit('PreToolUse',tool_id=tool_id)
    emit('SubagentStart',agent_id='branch-a');emit('SubagentStart',agent_id='branch-b')
    # Resolve the middle-started call first. The inspect and service tethers
    # stay independently visible until their own matching PostToolUse events.
    args.tool_name='Bash';emit('PostToolUse',tool_id='shell-b')
    print('Built fixture overlap: 2 active tool tethers, 2 active satellites; shell-b returned out of order')
else:
    if not target.is_file() and args.event not in {'SessionStart','UserPromptSubmit'}:
        emit('UserPromptSubmit')
    ids=[args.tool_id] if args.count==1 else [f'{args.tool_id}-{index+1}' for index in range(args.count)]
    if args.event=='PreToolUse':
        for tool_id in ids:emit(args.event,tool_id=tool_id)
    elif args.event=='SubagentStart':
        agents=[args.agent_id] if args.count==1 else [f'{args.agent_id}-{index+1}' for index in range(args.count)]
        for agent_id in agents:emit(args.event,agent_id=agent_id)
    else:
        tool_id=args.tool_id if args.event in {'PermissionRequest','PostToolUse'} else None
        agent_id=args.agent_id if args.event=='SubagentStop' else None
        emit(args.event,tool_id=tool_id,agent_id=agent_id)
    print(f'Added fixture event {args.event} to {args.fixture}')
