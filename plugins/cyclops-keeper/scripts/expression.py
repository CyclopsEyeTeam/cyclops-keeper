"""Explicitly authored, per-launch artwork. Never an activity event source."""
import fcntl
import json
import math
import os
from pathlib import Path
import stat
import time
from functools import lru_cache
import textwrap
from launcher_link import atomic, read_attachment, descendant

FILENAME='.keeper-expression.json'
PALETTE={'glass':1,'lavender':2,'gold':4,'chalk':5}


def caption(value):
    # One-cell printable ASCII keeps terminal escapes, bidi and wide glyphs out.
    if not isinstance(value,str) or not 1<=len(value)<=120 or any(not 32<=ord(c)<=126 for c in value):
        raise ValueError('caption must be 1-120 printable ASCII characters')
    return value


def painting(value):
    if not isinstance(value,list) or not 1<=len(value)<=12:
        raise ValueError('provide 1-12 strokes')
    result=[]
    for stroke in value:
        if not isinstance(stroke,dict) or set(stroke)!={'ink','points'} or stroke['ink'] not in PALETTE:
            raise ValueError('each stroke needs ink and points')
        points=stroke['points']
        if not isinstance(points,list) or not 2<=len(points)<=24:
            raise ValueError('each stroke needs 2-24 points')
        for p in points:
            if not isinstance(p,list) or len(p)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in p):
                raise ValueError('points must be finite [x,y] coordinates from 0 to 1')
        result.append({'ink':stroke['ink'],'points':points})
    return result


def binding():
    """Use inherited launcher ownership, never a model-selected session/path."""
    address=os.environ.get('KEEPER_LAUNCH_SOCKET')
    if not address:
        raise ValueError('Launch Codex with codex --keeper side, top, or fullscreen first')
    path=Path(address).parent.resolve(strict=True)/'attachment.json'
    parent=path.parent.stat()
    if parent.st_uid!=os.getuid() or parent.st_mode & 0o077:
        raise ValueError('Keeper launch directory is not private')
    state=read_attachment(path)
    owner=json.loads(os.environ.get('KEEPER_LAUNCH_OWNER','null'))
    if state['owner']!=owner or not descendant(os.getpid(),state.get('codex')):
        raise ValueError('This MCP server does not belong to the attached Codex process')
    if not state.get('session'):
        raise ValueError('Keeper is awaiting the trusted session hook; retry after attachment')
    return path,state


def identity(state):
    return {key:state[key] for key in ('owner','session','generation')}


def read_file(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd) as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode & 0o077 or info.st_size>32768:
            raise ValueError('Unsafe expression file')
        value=json.load(stream)
    if not isinstance(value,dict):raise ValueError('Invalid expression')
    return value


def publish(action,args):
    if not isinstance(args,dict):raise ValueError('arguments must be an object')
    if action=='say':
        if set(args)-{'caption','seconds'}:raise ValueError('Unknown caption argument')
        text=caption(args.get('caption'));seconds=args.get('seconds',30)
        if type(seconds) is not int or not 5<=seconds<=120:raise ValueError('seconds must be 5-120')
    elif action=='paint':
        if set(args)!={'strokes'}:raise ValueError('paint accepts only strokes')
        strokes=painting(args['strokes'])
    elif action!='clear' or args:raise ValueError('Unknown tool or arguments')
    path,state=binding()
    lock=os.open(path.parent/'.keeper-expression.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW|os.O_NONBLOCK,0o600)
    try:
        if not stat.S_ISREG(os.fstat(lock).st_mode):raise ValueError('Unsafe expression lock')
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Another expression is arriving; retry later')
        expected=identity(state)
        try:old=read_file(path.parent/FILENAME)
        except (OSError,ValueError):old={}
        if old.get('binding')!=expected:old={}
        now=time.time()
        if action!='clear' and now-old.get('written_at',0)<1:
            raise ValueError('Let the previous expression settle; wait one second')
        value={'v':1,'binding':expected,'written_at':now,
               'caption':old.get('caption'),'until':old.get('until',0),
               'strokes':old.get('strokes',[])}
        if action=='say':value.update(caption=text,until=now+seconds)
        elif action=='paint':value['strokes']=strokes
        else:value.update(caption=None,until=0,strokes=[])
        # Refuse if a clear/resume changed attachment while preparing the write.
        if identity(read_attachment(path))!=expected:raise ValueError('Keeper attachment changed; retry')
        atomic(path.parent/FILENAME,value)
        return 'Authored '+({'say':'caption','paint':'painting','clear':'space cleared'}[action])+'. No work status was changed.'
    finally:os.close(lock)


class Reader:
    """At most four stats per second; decode only on atomic file replacement."""
    def __init__(self):
        self.next=0;self.signature=None;self.value={};self.context=None

    def load(self,path,session,attachment_identity):
        context=(str(path),session,attachment_identity)
        if context!=self.context:
            self.context=context;self.next=0;self.signature=None;self.value={}
        now=time.monotonic()
        if now>=self.next:
            self.next=now+.25
            try:
                file=Path(path).parent/FILENAME;info=file.lstat()
                signature=(info.st_ino,info.st_mtime_ns,info.st_size)
                if signature!=self.signature:
                    value=read_file(file)
                    owner,generation=attachment_identity
                    if value.get('v')!=1 or value.get('binding')!={'owner':owner,'generation':generation,'session':session}:
                        raise ValueError('Expression belongs to a different attachment')
                    if value.get('caption') is not None:caption(value['caption'])
                    if value.get('strokes'):painting(value['strokes'])
                    until=value.get('until',0)
                    if type(until) not in (float,int) or not math.isfinite(until):raise ValueError('Invalid expiry')
                    self.value=value;self.signature=signature
            except (OSError,ValueError,TypeError,KeyError):self.value={};self.signature=None
        value=self.value
        text=value.get('caption') if time.time()<value.get('until',0) else None
        strokes=value.get('strokes',[])
        return {'caption':text,'strokes':strokes} if text or strokes else None


@lru_cache(maxsize=4)
def lane(encoded,width,rows,unicode,colour,truecolour,calm):
    """Static, bounded canvas. No animation or activity indicators here."""
    value=json.loads(encoded)
    label='Keeper / authored'
    text=value.get('caption') or 'A small painting, left here.'
    lines=[label[:width].ljust(width)]
    wrapped=textwrap.wrap(text,width=max(1,width-2)) or ['']
    text_rows=min(2,rows-1)
    lines.extend(('  '+line)[:width].ljust(width) for line in wrapped[:text_rows])
    lines.extend(' '*width for _ in range(1+text_rows-len(lines)))
    art_rows=rows-len(lines)
    if art_rows and value.get('strokes'):
        from terminal_art import Surface
        surface=Surface(width,art_rows)
        # Leave side margins and a narrow, intentionally asymmetrical canvas.
        left=width*.16;span=width*.65
        for stroke in value['strokes']:
            points=[((left+x*span)*2,y*max(0,art_rows*4-1)) for x,y in stroke['points']]
            for a,b in zip(points,points[1:]):surface.line(a,b,PALETTE[stroke['ink']],1)
        lines.extend(surface.frame('',unicode=unicode,colour=colour,truecolour=truecolour,calm=calm).splitlines()[:art_rows])
    lines.extend(' '*width for _ in range(rows-len(lines)))
    return '\n'.join(lines)
