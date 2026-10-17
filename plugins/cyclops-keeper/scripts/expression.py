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
PALETTE={'glass':1,'lavender':2,'gold':4,'chalk':5,
         'mist':0,'aqua':6,'violet':8,'rose':9}


def caption(value):
    # One-cell printable ASCII keeps terminal escapes, bidi and wide glyphs out.
    if not isinstance(value,str) or not 1<=len(value)<=120 or any(not 32<=ord(c)<=126 for c in value):
        raise ValueError('caption must be 1-120 printable ASCII characters')
    return value


def coordinate(point):
    if (not isinstance(point,list) or len(point)!=2 or
            any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in point)):
        raise ValueError('points must be finite [x,y] coordinates from 0 to 1')
    return point


def ink(value):
    if not isinstance(value,str) or value not in PALETTE:
        raise ValueError('unknown drawing ink')
    return value


def painting(value):
    if not isinstance(value,list) or not 1<=len(value)<=32:
        raise ValueError('provide 1-32 strokes')
    result=[];total=0
    for stroke in value:
        if not isinstance(stroke,dict) or set(stroke)-{'ink','points','kind'} or not {'ink','points'}<=set(stroke):
            raise ValueError('each stroke needs ink and points, with optional kind')
        colour=ink(stroke['ink']);kind=stroke.get('kind','line')
        if kind not in ('line','ellipse','rect','curve'):
            raise ValueError('kind must be line, ellipse, rect or curve')
        points=stroke['points']
        if not isinstance(points,list) or not 2<=len(points)<=48:
            raise ValueError('each stroke needs 2-48 points')
        if (kind in ('ellipse','rect') and len(points)!=2) or (kind=='curve' and len(points)!=4):
            raise ValueError('ellipse and rect need 2 opposite corners; curve needs 4 control points')
        total+=len(points)
        if total>512:raise ValueError('a painting allows at most 512 points in total')
        for point in points:coordinate(point)
        item={'ink':colour,'points':points}
        if kind!='line':item['kind']=kind
        result.append(item)
    return result


def labels(value):
    if not isinstance(value,list) or len(value)>6:
        raise ValueError('provide at most 6 labels')
    result=[]
    for label in value:
        if not isinstance(label,dict) or set(label)!={'text','at','ink'}:
            raise ValueError('each label needs text, at and ink')
        text=caption(label['text'])
        if len(text)>40:raise ValueError('labels allow at most 40 printable ASCII characters')
        result.append({'text':text,'at':coordinate(label['at']),'ink':ink(label['ink'])})
    return result


def crest_value(value):
    if not isinstance(value,dict) or set(value)-{'motif','phrase'}:
        raise ValueError('crest accepts motif and optional phrase')
    motif=value.get('motif','constellation')
    if motif not in ('constellation','moon','ribbon'):
        raise ValueError('crest motif must be constellation, moon or ribbon')
    phrase=value.get('phrase','')
    if phrase:
        caption(phrase)
    elif not isinstance(phrase,str):
        raise ValueError('crest phrase must be text')
    if len(phrase)>48:raise ValueError('crest phrase allows at most 48 printable ASCII characters')
    return {'motif':motif,'phrase':phrase}


@lru_cache(maxsize=4)
def crest_lane(encoded,width,colour,truecolour,calm,theme='classic'):
    """Four static rows of explicitly decorative or authored expression."""
    from terminal_art import colour_codes
    value=json.loads(encoded) if encoded else {'motif':'constellation','phrase':''}
    motifs={
        'constellation':(' .       *----.        . ', '    *---/      `---*      '),
        'moon':('       .-``-.    *       ', "   .   `-..-'        .   "),
        'ribbon':('   .---.      .---.      ', "  /     `----'     `--.   "),
    }
    title='Keeper / crest - authored' if encoded else 'Keeper / decorative crest'
    lines=[title[:width].center(width)]
    lines.extend(line[:width].center(width) for line in motifs[value['motif']])
    phrase=value.get('phrase','')
    if len(phrase)>width:phrase=phrase[:width-3]+'...'
    lines.append(phrase.center(width))
    if colour:
        codes=colour_codes(truecolour,False,calm,theme)
        lines=[codes[2 if index in (1,2) else 10]+line+'\x1b[0m' for index,line in enumerate(lines)]
    return '\n'.join(lines)


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
        if set(args)-{'strokes','labels'}:raise ValueError('paint accepts strokes and labels')
        strokes=painting(args['strokes']) if args.get('strokes')!=[] and 'strokes' in args else []
        lettering=labels(args.get('labels',[]))
        if not strokes and not lettering:raise ValueError('provide strokes or labels; use clear for an empty canvas')
    elif action=='crest':
        crest=crest_value(args)
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
               'strokes':old.get('strokes',[]),'labels':old.get('labels',[]),'crest':old.get('crest')}
        if action=='say':value.update(caption=text,until=now+seconds)
        elif action=='paint':value.update(strokes=strokes,labels=lettering)
        elif action=='crest':value['crest']=crest
        else:value.update(caption=None,until=0,strokes=[],labels=[],crest=None)
        # Refuse if a clear/resume changed attachment while preparing the write.
        if identity(read_attachment(path))!=expected:raise ValueError('Keeper attachment changed; retry')
        atomic(path.parent/FILENAME,value)
        return 'Authored '+({'say':'caption','paint':'painting','crest':'crest','clear':'space cleared'}[action])+'. No work status was changed.'
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
                    if value.get('labels'):labels(value['labels'])
                    if value.get('crest') is not None:crest_value(value['crest'])
                    until=value.get('until',0)
                    if type(until) not in (float,int) or not math.isfinite(until):raise ValueError('Invalid expiry')
                    self.value=value;self.signature=signature
            except (OSError,ValueError,TypeError,KeyError):self.value={};self.signature=None
        value=self.value
        text=value.get('caption') if time.time()<value.get('until',0) else None
        strokes=value.get('strokes',[])
        lettering=value.get('labels',[])
        crest=value.get('crest')
        return {'caption':text,'strokes':strokes,'labels':lettering,'crest':crest} if text or strokes or lettering or crest else None


@lru_cache(maxsize=4)
def lane(encoded,width,rows,unicode,colour,truecolour,calm,theme='classic'):
    """Static, bounded canvas. No animation or activity indicators here."""
    value=json.loads(encoded)
    label='Keeper / authored'
    text=value.get('caption')
    lines=[label[:width].ljust(width)]
    if text:
        wrapped=textwrap.wrap(text,width=max(1,width-2)) or ['']
        lines.extend(('  '+line)[:width].ljust(width) for line in wrapped[:min(2,rows-1)])
    art_rows=rows-len(lines)
    if art_rows and (value.get('strokes') or value.get('labels')):
        from terminal_art import Surface
        surface=Surface(width,art_rows)
        # Two terminal cells of margin; the rest belongs to the drawing.
        left=2;span=max(0,width-5)
        def project(point):
            x,y=point
            return ((left+x*span)*2,y*max(0,art_rows*4-1))
        for stroke in value.get('strokes',[]):
            points=[project(point) for point in stroke['points']]
            role=PALETTE[stroke['ink']];kind=stroke.get('kind','line')
            if kind=='curve':surface.curve(points,role,1)
            elif kind in ('ellipse','rect'):
                (x0,y0),(x1,y1)=points
                if kind=='ellipse':
                    surface.ellipse(((x0+x1)/2,(y0+y1)/2),abs(x1-x0)/2,abs(y1-y0)/2,role,1)
                else:
                    corners=[(x0,y0),(x1,y0),(x1,y1),(x0,y1),(x0,y0)]
                    for a,b in zip(corners,corners[1:]):surface.line(a,b,role,1)
            else:
                for a,b in zip(points,points[1:]):surface.line(a,b,role,1)
        for label in value.get('labels',[]):
            x,y=project(label['at']);row=min(art_rows-1,round(y)//4)
            col=min(width-1,round(x)//2)
            for offset,char in enumerate(label['text'][:max(0,width-2-col)]):
                surface.point((col+offset)*2,row*4,PALETTE[label['ink']],9)
                surface.glyphs[(row,col+offset)]=char
        lines.extend(surface.frame('',unicode=unicode,colour=colour,truecolour=truecolour,
                                   calm=calm,theme=theme).splitlines()[:art_rows])
    lines.extend(' '*width for _ in range(rows-len(lines)))
    return '\n'.join(lines)
