#!/usr/bin/env python3
"""Small stdio MCP server. Blocks on stdin; no worker, watcher or model loop."""
import json
import sys
from pathlib import Path
sys.dont_write_bytecode=True
from expression import publish, PALETTE
import painting_mcp

DESCRIPTION=('Author a small expression for this launch\'s Keeper. This is creative display, '
 'not telemetry or hidden thought. Never copy prompts, private reasoning, tool arguments/results, '
 'credentials, paths or transcript text. Use sparingly alongside real work; never spawn an agent '
 'just to keep this space active. When the user has invited Keeper expression, you may occasionally '
 'leave an original line or sketch during work without needing a new request each time. Silence is fine. '
 'When the user opts into pictures per message, compose early once per user message, including short follow-ups, and roughly every 15 minutes '
 'during long active work, best effort; never run an idle timer or model loop. If both surfaces were requested, '
 'Read painting_brief first for the user-selected Free or Work-inspired mode. '
 'use save_painting for the overhead saved composition and paint for a separate lower live sketch. '
 'Paintings and captions cannot create agents or change work status.')

def schema(properties,required):
    return {'type':'object','properties':properties,'required':required,'additionalProperties':False}

TOOLS=[
 {'name':'say','description':DESCRIPTION+' The caption is visibly labeled authored and expires.',
  'inputSchema':schema({'caption':{'type':'string','minLength':1,'maxLength':120,'description':'Original printable ASCII caption, not copied task data.'},
                         'seconds':{'type':'integer','minimum':5,'maximum':120,'default':30}},['caption'])},
 {'name':'paint','description':DESCRIPTION+' Replace the canvas with up to 32 strokes (512 points total) and 6 short labels. Coordinates are normalized 0..1. Line joins points; ellipse/rect take two opposite corners; curve takes start, two control points and end. Eight inks follow the current theme. Content remains still until replaced or cleared; omitted strokes or labels are cleared. Shapes may be layered in drawing order; labels appear on top.',
  'inputSchema':schema({'strokes':{'type':'array','minItems':0,'maxItems':32,'items':schema({
      'ink':{'type':'string','enum':list(PALETTE)},
      'kind':{'type':'string','enum':['line','ellipse','rect','curve'],'default':'line'},
      'points':{'type':'array','minItems':2,'maxItems':48,'items':{'type':'array','minItems':2,'maxItems':2,'items':{'type':'number','minimum':0,'maximum':1}}}},['ink','points'])},
      'labels':{'type':'array','maxItems':6,'items':schema({
          'text':{'type':'string','minLength':1,'maxLength':40,'description':'Original printable ASCII label.'},
          'at':{'type':'array','minItems':2,'maxItems':2,'items':{'type':'number','minimum':0,'maximum':1}},
          'ink':{'type':'string','enum':list(PALETTE)}},['text','at','ink'])}},[])},
 {'name':'crest','description':DESCRIPTION+' Set the expressive crest above Keeper without replacing the painting. Pick a constellation, moon or ribbon and an optional original phrase. The motif has gentle decorative motion, respecting quiet modes; the phrase stays still. It persists until replaced or cleared and hides in short panes.',
  'inputSchema':schema({'motif':{'type':'string','enum':['constellation','moon','ribbon'],'default':'constellation'},
      'phrase':{'type':'string','maxLength':48,'description':'Original printable ASCII phrase; empty removes the previous phrase.'}},[])},
 {'name':'clear','description':'Clear only this launch\'s authored caption, painting and custom crest. Leaves observed activity and subagent seats intact.',
  'inputSchema':schema({},[])}]
for tool in TOOLS:
    tool['annotations']={'readOnlyHint':False,'destructiveHint':False,'openWorldHint':False}

TOOLS.extend(painting_mcp.TOOLS)

def respond(request):
    ident=request.get('id');method=request.get('method');params=request.get('params',{})
    if 'id' not in request:return None
    if request.get('jsonrpc')!='2.0' or not isinstance(method,str) or not isinstance(params,dict):
        return {'jsonrpc':'2.0','id':ident,'error':{'code':-32600,'message':'Invalid request'}}
    if method=='initialize':
        version=params.get('protocolVersion')
        result={'protocolVersion':version if version in {'2024-11-05','2025-03-26','2025-06-18'} else '2025-06-18',
                'capabilities':{'tools':{}},'serverInfo':{'name':'keeper','version':json.loads((Path(__file__).resolve().parents[1]/'.codex-plugin/plugin.json').read_text())['version']},'instructions':DESCRIPTION}
    elif method=='ping':result={}
    elif method=='tools/list':result={'tools':TOOLS}
    elif method=='tools/call':
        try:
            if params.get('name') in {'save_painting','read_paintings','painting_brief'}:
                text=painting_mcp.call(params['name'],params.get('arguments',{}))
            else:
                if params.get('name') not in {'say','paint','crest','clear'}:raise ValueError('Unknown Keeper tool')
                text=publish(params['name'],params.get('arguments',{}))
            result={'content':[{'type':'text','text':text}]}
        except (ValueError,OSError,TypeError,KeyError) as error:
            # Validation messages are fixed; OS errors may disclose paths.
            message='Keeper display is unavailable for this launch' if isinstance(error,OSError) else str(error)
            result={'isError':True,'content':[{'type':'text','text':message}]}
    else:return {'jsonrpc':'2.0','id':ident,'error':{'code':-32601,'message':'Method not found'}}
    return {'jsonrpc':'2.0','id':ident,'result':result}


def main():
    while True:
        raw=sys.stdin.buffer.readline(524289)
        if not raw:break
        if len(raw)>524288:
            # Close rather than treating fragments of an oversized request as requests.
            break
        try:
            request=painting_mcp.store.decode(raw, limit=524288)
            if not isinstance(request,dict):raise ValueError()
            response=respond(request)
        except (ValueError,TypeError):
            response={'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Invalid JSON request'}}
        if response is not None:
            sys.stdout.write(json.dumps(response,separators=(',',':'))+'\n');sys.stdout.flush()

if __name__=='__main__':main()
