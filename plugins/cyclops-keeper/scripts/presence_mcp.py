#!/usr/bin/env python3
"""Small stdio MCP server. Blocks on stdin; no worker, watcher or model loop."""
import json
import sys
sys.dont_write_bytecode=True
from expression import publish

DESCRIPTION=('Author a small expression for this launch\'s Keeper. This is creative display, '
 'not telemetry or hidden thought. Never copy prompts, private reasoning, tool arguments/results, '
 'credentials, paths or transcript text. Use sparingly alongside real work; never spawn an agent '
 'just to keep this space active. When the user has invited Keeper expression, you may occasionally '
 'leave an original line or sketch during work without needing a new request each time. Silence is fine. '
 'Paintings and captions cannot create agents or change work status.')

def schema(properties,required):
    return {'type':'object','properties':properties,'required':required,'additionalProperties':False}

TOOLS=[
 {'name':'say','description':DESCRIPTION+' The caption is visibly labeled authored and expires.',
  'inputSchema':schema({'caption':{'type':'string','minLength':1,'maxLength':120,'description':'Original printable ASCII caption, not copied task data.'},
                         'seconds':{'type':'integer','minimum':5,'maximum':120,'default':30}},['caption'])},
 {'name':'paint','description':DESCRIPTION+' Replace the quiet painting with 1-12 polylines. It remains still until replaced or cleared. Use Keeper aperture, off-centre crown and loose threads as inspiration.',
  'inputSchema':schema({'strokes':{'type':'array','minItems':1,'maxItems':12,'items':schema({
      'ink':{'type':'string','enum':['glass','lavender','gold','chalk']},
      'points':{'type':'array','minItems':2,'maxItems':24,'items':{'type':'array','minItems':2,'maxItems':2,'items':{'type':'number','minimum':0,'maximum':1}}}},['ink','points'])}},['strokes'])},
 {'name':'clear','description':'Clear only this launch\'s authored caption and painting. Leaves observed activity and subagent seats intact.',
  'inputSchema':schema({},[])}]
for tool in TOOLS:
    tool['annotations']={'readOnlyHint':False,'destructiveHint':False,'openWorldHint':False}


def respond(request):
    ident=request.get('id');method=request.get('method');params=request.get('params',{})
    if 'id' not in request:return None
    if request.get('jsonrpc')!='2.0' or not isinstance(method,str) or not isinstance(params,dict):
        return {'jsonrpc':'2.0','id':ident,'error':{'code':-32600,'message':'Invalid request'}}
    if method=='initialize':
        version=params.get('protocolVersion')
        result={'protocolVersion':version if version in {'2024-11-05','2025-03-26','2025-06-18'} else '2025-06-18',
                'capabilities':{'tools':{}},'serverInfo':{'name':'keeper','version':'0.5.0'},'instructions':DESCRIPTION}
    elif method=='ping':result={}
    elif method=='tools/list':result={'tools':TOOLS}
    elif method=='tools/call':
        try:
            if params.get('name') not in {'say','paint','clear'}:raise ValueError('Unknown Keeper tool')
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
        raw=sys.stdin.buffer.readline(32769)
        if not raw:break
        if len(raw)>32768:
            # Close rather than treating fragments of an oversized request as requests.
            break
        try:
            request=json.loads(raw)
            if not isinstance(request,dict):raise ValueError()
            response=respond(request)
        except (ValueError,TypeError):
            response={'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':'Invalid JSON request'}}
        if response is not None:
            sys.stdout.write(json.dumps(response,separators=(',',':'))+'\n');sys.stdout.flush()

if __name__=='__main__':main()
