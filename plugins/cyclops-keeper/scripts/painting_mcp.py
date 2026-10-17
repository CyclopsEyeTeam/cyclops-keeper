"""Saved-painting tools, using the existing trusted launch attachment."""
from contextlib import contextmanager
import json
import os
import expression
import painting_store as store


def obj(properties, required):
    return {'type':'object','properties':properties,'required':required,'additionalProperties':False}


def num(lo, hi, integer=False):
    return {'type':'integer' if integer else 'number','minimum':lo,'maximum':hi}


def painting_schema():
    colour={'type':'array','minItems':3,'maxItems':3,'items':num(0,1)}
    variants=[]
    for k in store.KINDS:
        props={'k':{'const':k},'c':colour,'c2':colour,'a':num(0,1)}
        if k in ('line','curve','fill'):
            props['pts']={'type':'array','minItems':3 if k=='fill' else 2,'maxItems':24,
                          'items':{'type':'array','minItems':2,'maxItems':2,'items':num(0,1)}}
            props['grad' if k=='fill' else 'w']=num(-4,4) if k=='fill' else num(.003,.12)
        else: props.update(x=num(0,1),y=num(0,1),r=num(.004,.7))
        if k in ('ring','arc'):props['w']=num(.003,.12)
        if k=='arc':props.update(a0=num(-4,4),a1=num(-4,4))
        if k=='spray':props.update(n=num(1,200,True),s=num(.002,.06),seed=num(1,999999,True))
        variants.append(obj(props,[key for key in props if key not in ('c2','seed')]))
    props={'title':{'type':'string','minLength':1,'maxLength':48},'thought':{'type':'string','maxLength':160},
           'mood':{'type':'string','minLength':1,'maxLength':24},'mirror':{'enum':[None,'x','y','xy']},
           'marks':{'type':'array','minItems':1,'maxItems':96,'items':{'oneOf':variants}},
           'model':{'const':'keeper'},'by':{'const':'keeper'},'at':num(.000001,9999999999),
           'shape':{'enum':['wide','square','tall']},'opening':{'type':'boolean'},'tokens':num(0,1000000000,True)}
    return obj(props,[key for key in props if key not in ('thought','opening','tokens')])

TOOLS=[
 {'name':'painting_brief','description':'Read this launch’s Free or Work-inspired painting choice before composing. Work-inspired means abstract motifs only: never put work data, prompts, code, paths or identifiers in artwork. This is a preference, not a model invocation.',
  'inputSchema':obj({},[]),'annotations':{'readOnlyHint':True,'destructiveHint':False,'openWorldHint':False}},
 {'name':'save_painting','description':
  'Save one deliberate, assistant-authored Keeper composition in this attached project. This is NOT the live expression paint tool. '
  'Only on explicit user painting intent, including continuing per-message or roughly 15-minute active-work opt-in. Save once per requested picture; no idle/background model loop. No fixed style or template; no claim of an autonomous composition engine. '
  'Review all text: no prompts, reasoning, tool results, credentials, project paths or session identifiers. '
  'privacy_checked attests to that review; pattern checks cannot detect all private prose. Strict validation, no clamping, no overwrites.',
  'inputSchema':obj({'painting':painting_schema(),'privacy_checked':{'const':True}},['painting','privacy_checked']),
  'annotations':{'readOnlyHint':False,'destructiveHint':False,'openWorldHint':False}},
 {'name':'read_paintings','description':
  'Read paintings in the attached project only. Without filename, list up to 200 valid paintings as metadata; '
  'with a filename, return one full composition. Folder determines credit. Invalid files and links are skipped. Never writes peer files.',
  'inputSchema':obj({'owner':{'enum':list(store.OWNERS)},'filename':{'type':'string','maxLength':255}},['owner']),
  'annotations':{'readOnlyHint':True,'destructiveHint':False,'openWorldHint':False}}]


@contextmanager
def bound_project():
    path,state=expression.binding()
    remote=state.get('project_fd')
    if type(remote) is not int or remote<0:raise ValueError('Keeper has no attached project')
    fd=os.open(f"/proc/{state['owner']['pid']}/fd/{remote}",os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    expected=(expression.identity(state),remote)
    def guard():
        fresh_path,fresh=expression.binding()
        if fresh_path!=path or (expression.identity(fresh),fresh.get('project_fd'))!=expected:
            raise ValueError('Keeper attachment changed; retry')
    try:
        guard()
        yield fd,guard
    finally:os.close(fd)


def call(name,args):
    if not isinstance(args,dict):raise ValueError('Painting arguments must be an object')
    if name=='painting_brief':
        if args:raise ValueError('Painting brief takes no arguments')
        from painting_choice import read
        path,state=expression.binding()
        mode=read(path,expression.identity(state))
        return json.dumps({'mode':mode,'guidance':'Choose a subject freely, independent of work.' if mode=='free' else 'Use broad abstract themes inspired by the current work; include no private task content.'})
    if name=='save_painting':
        if set(args)!={'painting','privacy_checked'} or args['privacy_checked'] is not True:
            raise ValueError('Review painting privacy before saving')
        store.validate(args['painting'])
        with bound_project() as (fd,guard):result={'saved':store.save(fd,args['painting'],guard)}
    elif name=='read_paintings':
        if set(args)-{'owner','filename'} or args.get('owner') not in store.OWNERS:
            raise ValueError('Invalid painting read arguments')
        filename=args.get('filename')
        if filename is not None and (not isinstance(filename,str) or len(filename)>255 or '/' in filename):
            raise ValueError('Invalid painting filename')
        with bound_project() as (fd,guard):
            result=store.read(fd,args['owner'],filename);guard()
        if filename is None:
            result=[{'filename':p['filename'],**{k:p['painting'].get(k) for k in ('title','at','by','shape')}} for p in result]
    else:raise ValueError('Unknown painting tool')
    return json.dumps(result,ensure_ascii=False,allow_nan=False)
