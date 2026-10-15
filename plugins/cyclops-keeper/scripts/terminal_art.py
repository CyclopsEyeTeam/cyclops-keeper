"""Keeper's woven terminal identity, rasterised to 2 x 4 Unicode subcells.

Standard library only. Geometry describes observed poses; breath is decoration.
Every invocation owns a stationary route derived from its complete opaque key.
"""
import hashlib
import math
from functools import lru_cache
from responsive import detail
from responsive_expression import micro, miniature

# Sea glass membrane, lavender weave, pale gold aperture. Roles carry colour,
# never success, failure, or a guess about the meaning of an invocation.
COLOURS = ((83, 118, 136), (91, 169, 181), (158, 156, 210),
           (186, 167, 224), (225, 201, 153), (247, 237, 216),
           (126, 191, 196), (203, 178, 146), (169, 164, 214),
           (204, 155, 133), (173, 190, 201))
BITS = ((1, 8), (2, 16), (4, 32), (64, 128))
GLYPHS = (' ',) + tuple(chr(0x2800+mask) for mask in range(1,256))
ASCII_GLYPHS = (' ',) + tuple('|' if mask & 0x47 else '.' for mask in range(1,256))


@lru_cache(maxsize=8)
def colour_codes(truecolour, dim, calm):
    factor=.48 if dim else .72 if calm else 1
    codes=[]
    for rgb in COLOURS:
        values=[round(v*factor) for v in rgb]
        if truecolour:
            codes.append("\x1b[38;2;"+";".join(map(str,values))+"m")
        else:
            r,g,b=[round(v/255*5) for v in values]
            codes.append(f"\x1b[38;5;{16+36*r+6*g+b}m")
    return tuple(codes)


def _basis_samples(count, until):
    for i in range(1,count+1):
        fraction=i/count
        u=fraction*until;v=1-u
        yield (v**3,3*v*v*u,3*v*u*u,u**3,fraction)


@lru_cache(maxsize=64)
def _complete_basis(count):
    # Only time-independent sampling coefficients, never poses, keys or
    # pixels. Callers bypass the cache above256samples and for gestures.
    return tuple(_basis_samples(count,1))


class Surface:
    def __init__(self, columns, rows):
        self.columns, self.rows = columns, rows
        self.glyphs = {}
        self.masks = [bytearray(columns) for _ in range(rows)]
        self.roles = [bytearray(columns) for _ in range(rows)]
        self.priorities = [[-1] * columns for _ in range(rows)]

    def point(self, x, y, role=1, priority=1):
        x, y = round(x), round(y)
        if not (0 <= x < self.columns * 2 and 0 <= y < self.rows * 4):
            return
        row, col = y // 4, x // 2
        self.masks[row][col] |= BITS[y % 4][x % 2]
        if priority >= self.priorities[row][col]:
            self.roles[row][col] = role
            self.priorities[row][col] = priority

    def line(self, a, b, role=1, priority=1, dash=0):
        # Raster a segment in one batch. Keep the original samples, floating
        # arithmetic, rounding and priority order; only Python dispatch and
        # repeated buffer/coordinate lookups are removed.
        dx,dy=b[0]-a[0],b[1]-a[1]
        distance=math.hypot(dx,dy)
        count=max(1, math.ceil(distance * 2))
        masks,roles,priorities=self.masks,self.roles,self.priorities
        width,height=self.columns*2,self.rows*4
        ax,ay=a
        for i in range(count+1):
            if dash and int(distance * i / count / dash) % 2:
                continue
            u=i/count
            x,y=round(ax+dx*u),round(ay+dy*u)
            if not (0 <= x < width and 0 <= y < height):
                continue
            row,col=y//4,x//2
            masks[row][col] |= BITS[y%4][x%2]
            if priority >= priorities[row][col]:
                roles[row][col]=role
                priorities[row][col]=priority

    def curve(self, points, role=1, priority=1, dash=0, until=1):
        a,b,c,d=points
        length=sum(math.hypot(q[0]-p[0],q[1]-p[1]) for p,q in zip(points,points[1:]))
        count=max(8, math.ceil(length * 1.5))
        prior=a
        samples=_complete_basis(count) if until==1 and count<=256 else _basis_samples(count,until)
        for wa,wb,wc,wd,fraction in samples:
            point=(wa*a[0]+wb*b[0]+wc*c[0]+wd*d[0],
                   wa*a[1]+wb*b[1]+wc*c[1]+wd*d[1])
            if not dash or int(fraction*length/dash) % 2 == 0:
                self.line(prior,point,role,priority)
            prior=point
        return prior

    def ellipse(self, centre, rx, ry, role=1, priority=1, start=0, end=math.tau):
        count=max(12, math.ceil((end-start)*max(rx,ry)*2))
        prior=(centre[0]+math.cos(start)*rx,centre[1]+math.sin(start)*ry)
        for i in range(1,count+1):
            angle=start+(end-start)*i/count
            point=(centre[0]+math.cos(angle)*rx,centre[1]+math.sin(angle)*ry)
            self.line(prior,point,role,priority)
            prior=point

    def frame(self, status, *, colour=False, truecolour=False, dim=False, calm=False, unicode=True):
        codes=colour_codes(truecolour,dim,calm) if colour else ()
        glyphs=GLYPHS if unicode else ASCII_GLYPHS
        output=[]
        for row_index,(masks,roles) in enumerate(zip(self.masks,self.roles)):
            row=[];prior=None
            for col_index,(mask,role) in enumerate(zip(masks,roles)):
                if colour and mask and role != prior:
                    row.append(codes[role]);prior=role
                glyph=glyphs[mask]
                if self.glyphs:glyph=self.glyphs.get((row_index,col_index),glyph)
                row.append(glyph)
            if colour:row.append("\x1b[0m")
            output.append(''.join(row))
        output.append((codes[10] if colour else '')+status+("\x1b[0m" if colour else ''))
        return "\n".join(output)


def life_amount(record, lively, calm, reduced_motion):
    """Decorative motion only; unavailable evidence and quiet controls win."""
    if not lively or calm or reduced_motion or record['stale'] or record['state'] in {'unknown','ended'}:
        return 0
    return {'waiting':.25,'stopped':.35,'interrupted':.35,'idle':.65}.get(record['state'],1)


def draw_keeper(record, columns, rows, status, *, mode='balanced', now=0,
                calm=False, reduced_motion=False, blink=False, colour=False,
                truecolour=False, lively=True):
    level=detail(columns,rows)
    if level in {'micro','insufficient'}:
        return micro(record,columns,rows,now,unicode=True,reduced_motion=reduced_motion,calm=calm,colour=colour)
    if level=='small':
        return miniature(record,columns,rows,status,now,colour=colour,truecolour=truecolour,
                         calm=calm,reduced_motion=reduced_motion,mode=mode,lively=lively)
    surface=Surface(columns,max(0,rows-1))
    if columns < 3 or rows < 3:
        return surface.frame(status,colour=colour,truecolour=truecolour)
    w,h=columns*2,(rows-1)*4
    frozen=record['stale'] or record['state']=='unknown'
    state='unknown' if frozen else record['state']
    gestures=not reduced_motion and not frozen
    animate=gestures and state!='ended'
    life=life_amount(record,lively,calm,reduced_motion)
    scale=min(w/610,h/430)*(.96 if mode=='focus' else .74)
    cx,cy=w*.425,h*.465
    fold=.24 if state=='compacting' else 0
    breath=1+(math.sin(now*.6)*(.007+.015*life) if animate and not calm else 0)
    sx=scale*(1-fold)*breath
    sy=scale*(1-fold*.6)*breath
    def p(x,y):return (cx+x*sx,cy+y*sy)
    def curve(points,role=1,priority=1,dash=0,until=1):
        return surface.curve([p(*q) for q in points],role,priority,dash,until)
    def line(a,b,role=1,priority=1,dash=0):
        surface.line(p(*a),p(*b),role,priority,dash)
    def ring(x,y,r,role=1,priority=1,aspect=1,start=0,end=math.tau):
        surface.ellipse(p(x,y),max(.6,r*sx),max(.6,r*sy*aspect),role,priority,start,end)

    # The asymmetry is the signature: a high open crown on the right, a
    # membrane gathered around one aperture, then loose downward filaments.
    crown_lift=math.sin(now*.8)*4*life
    crown=(112,-160+crown_lift)
    strands=9 if level=='full' else 4
    for i in range(strands):
        u=i/(strands-1)
        sway=math.sin(now*.85+u*1.4)*6*life
        curve([crown,(-18+u*72+sway,-125-u*12),(-141+u*36-sway,-36+u*23),(-39+u*63,64)],
              1 if i%3 else 2,1)
        curve([crown,(145-u*24-sway,-82+u*24),(74-u*18+sway,50-u*12),(-24+u*39,64)],
              2 if i%3 else 1,1)
    # Fine cross-weave remains lighter than the aperture and crown.
    for i in range(5 if level=='full' else 2):
        y=-90+i*25+math.sin(now*.85+i*.7)*2*life
        curve([(-55-i*6,y),(0,y-30),(58,y+5),(93-i*11,y-24)],0,0,dash=2.7)
    line((91,-150+crown_lift),(135,-181+crown_lift),3,3)
    line((135,-181+crown_lift),(159,-143+crown_lift),3,3)
    line((111,-158+crown_lift),(118,-128+crown_lift),4,2)
    ring(112,-160+crown_lift,2.2+life*(.7+.6*math.sin(now*.9)),5,4)
    # A single interrupted body strand is severed at turn level. It never
    # attributes an interruption to a guessed tool or branch.
    tails=[((-40,58),(-94,100),(-106,155),(-147,190)),
           ((-22,64),(-57,111),(-38,171),(-73,216)),
           ((-8,61),(13,106),(-21,156),(-22,208)),
           ((12,61),(47,106),(27,155),(54,185))]
    for i,points in enumerate(tails if level=='full' else tails[:2]):
        if life:
            # Each loose filament has its own lag; its root stays gathered.
            points=tuple((x+life*(9+i*3)*(j/3)**1.2*math.sin(now*(.64+i*.07)-j*.55+i),
                          y+life*2*(j/3)*math.sin(now*.7+i))
                         for j,(x,y) in enumerate(points))
        if level=='compact':points=tuple((x,y*.78) for x,y in points)
        curve(points,2 if i%2 else 1,1,dash=0 if i<2 else 2.5,
              until=.43 if state=='interrupted' and i==3 else 1)
    if state=='interrupted':
        line((43,135),(50,143),9,3)
        line((58,151),(61,161),9,3)
        ring(53,147,3,9,3)
    if animate and not calm:
        # Decorative only: the membrane breathes; no marker travels along a
        # pending relation and no pose is randomly selected.
        ring(-106+math.sin(now*.55)*6*life,39+math.sin(now*.42)*(2+5*life),1.6,2,1)

    # Event-owned relations have stationary routes between observed gestures.
    def route(key,agent=False):
        digest=hashlib.sha256(key.encode('ascii')).digest()
        a=int.from_bytes(digest[:4],'big')/0xffffffff
        b=int.from_bytes(digest[4:8],'big')/0xffffffff
        if agent:
            start=(111,-158);end=(177+b*137,-166+a*215)
            return [start,(153,-197),(end[0]-21,end[1]-22),end]
        start=(91,-107);end=(184+b*161,-128+a*268)
        return [start,(136,-104),(end[0]-32,end[1]),end]
    kind_roles={'inspect':6,'change':7,'execute':4,'service':8,'other':0}
    ribbons=record['transitions']
    gesture_time=1.2 if lively and not calm else .8
    arrival_time=.75 if lively and not calm else .55
    for agent,items in ((False,record['active_tools']),(True,record['active_subagents'])):
        for item in items:
            points=route(item['key'],agent);role=8 if agent else kind_roles[item['kind']]
            extension=1
            if gestures:
                start_event=next((e for e in reversed(ribbons) if e['key']==item['key'] and
                                 e['event']==('SubagentStart' if agent else 'PreToolUse')),None)
                if start_event and 0 <= now-start_event['at'] < arrival_time:
                    extension=max(.08,(now-start_event['at'])/arrival_time)
            held=frozen or state in {'waiting','stopped','interrupted','ended'}
            dash=3 if held else 2 if agent or item.get('kind') in {'execute','other'} else 0
            until=.72 if state=='ended' else extension
            curve(points,role,1,dash,until)
            x,y=points[-1]
            if agent:
                ring(x,y,7,role,2);ring(x,y,2.5,role,2)
            elif held or item['kind']=='service':
                ring(x,y,4.5,role,2)
                if state=='waiting':line((x-2,y),(x+2,y),role,2)
            else:
                ring(x,y,2,role,2)
                surface.point(*p(x,y),role,2)
            if not agent and item['kind']=='change' and not held:
                curve([(x,y+4) for x,y in points],role,1,0,extension)
    if gestures:
        active_tools={item['key'] for item in record['active_tools']}
        active_agents={item['key'] for item in record['active_subagents']}
        for event in ribbons:
            age=now-event['at']
            if not 0 <= age < gesture_time:continue
            if event['event']=='PostToolUse' and event['key'] and event['key'] not in active_tools:
                tip=curve(route(event['key']),kind_roles.get(event['kind'],0),2,until=1-age/gesture_time)
                surface.ellipse(tip,1,1,5,3)
            elif event['event']=='SubagentStop' and event['key'] and event['key'] not in active_agents:
                tip=curve(route(event['key'],True),8,2,dash=2,until=1-age/gesture_time)
                surface.ellipse(tip,1.5,1.5,8,3)
            elif event['event']=='UserPromptSubmit':
                tip=curve([(-220,-65),(-170,-99),(-88,-34),(-34,0)],4,2,until=min(1,age/(.85 if lively and not calm else .65)))
                surface.ellipse(tip,1,1,5,3)
            elif event['event']=='PostCompact':
                ring(0,0,43+age*8,3,2,start=-1.5,end=-.1)

    # Draw the eye last, so an invocation can never overwrite its aperture.
    ring(0,0,34,2,3)
    ring(0,0,27,4,3,start=-2.7,end=1.7)
    ring(0,0,40,0,2,start=-1.3,end=.1)
    ring(0,0,40,0,2,start=1.9,end=3.8)
    if state=='unknown':
        ring(0,0,7,0,4,aspect=2.1)
    elif blink and animate:
        line((-8,0),(8,0),5,5)
    else:
        aperture=8 if state=='waiting' else 12 if state in {'stopped','ended'} else 18
        aperture+=math.sin(now*1.1)*1.5*life
        for x in (-2,-1,0,1,2):
            line((x,-aperture+abs(x)*3),(x,aperture-abs(x)*3),5 if x==0 else 4,5)
        if state=='waiting':
            line((-11,-10),(-11,10),3,4)
            line((11,-10),(11,10),3,4)
    return surface.frame(status,colour=colour,truecolour=truecolour,
                         dim=frozen or state=='ended',calm=calm)
