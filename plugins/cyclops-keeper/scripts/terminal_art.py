"""Keeper's woven terminal identity, rasterised to 2 x 4 Unicode subcells.

Standard library only. Geometry describes observed poses; breath is decoration.
Every invocation owns a stationary route derived from its complete opaque key.
"""
import hashlib
import math
from collections import OrderedDict
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
        masks,roles,priorities=self.masks,self.roles,self.priorities
        width,height=self.columns*2,self.rows*4
        bits=BITS
        previous_drawn=False
        for wa,wb,wc,wd,fraction in samples:
            point=(wa*a[0]+wb*b[0]+wc*c[0]+wd*d[0],
                   wa*a[1]+wb*b[1]+wc*c[1]+wd*d[1])
            if not dash or int(fraction*length/dash) % 2 == 0:
                ax,ay=prior
                dx,dy=point[0]-ax,point[1]-ay
                distance=math.hypot(dx,dy)
                segment_count=max(1,math.ceil(distance*2))
                # Adjacent curve segments share an endpoint. Preserve its
                # coverage while rasterizing the curve without one Python
                # method dispatch per sample or duplicate endpoint writes.
                first=1 if previous_drawn else 0
                last_x=round(ax) if previous_drawn else None
                last_y=round(ay) if previous_drawn else None
                for i in range(first,segment_count+1):
                    u=i/segment_count
                    x,y=round(ax+dx*u),round(ay+dy*u)
                    if not (0<=x<width and 0<=y<height):
                        continue
                    if x==last_x and y==last_y:
                        continue
                    row,col=y//4,x//2
                    masks[row][col]|=bits[y%4][x%2]
                    if priority>=priorities[row][col]:
                        roles[row][col]=role
                        priorities[row][col]=priority
                    last_x,last_y=x,y
                previous_drawn=True
            else:
                previous_drawn=False
            prior=point
        return prior

    def ellipse(self, centre, rx, ry, role=1, priority=1, start=0, end=math.tau):
        count=max(12, math.ceil((end-start)*max(rx,ry)*2))
        prior=(centre[0]+math.cos(start)*rx,centre[1]+math.sin(start)*ry)
        masks,roles,priorities=self.masks,self.roles,self.priorities
        width,height=self.columns*2,self.rows*4
        bits=BITS
        for i in range(1,count+1):
            angle=start+(end-start)*i/count
            point=(centre[0]+math.cos(angle)*rx,centre[1]+math.sin(angle)*ry)
            ax,ay=prior
            dx,dy=point[0]-ax,point[1]-ay
            distance=math.hypot(dx,dy)
            segment_count=max(1,math.ceil(distance*2))
            first=0 if i==1 else 1
            last_x=last_y=None
            for j in range(first,segment_count+1):
                u=j/segment_count
                x,y=round(ax+dx*u),round(ay+dy*u)
                if not (0<=x<width and 0<=y<height):
                    continue
                if x==last_x and y==last_y:
                    continue
                row,col=y//4,x//2
                masks[row][col]|=bits[y%4][x%2]
                if priority>=priorities[row][col]:
                    roles[row][col]=role
                    priorities[row][col]=priority
                last_x,last_y=x,y
            prior=point

    def frame(self, status, *, caption=None, colour=False, truecolour=False,
              dim=False, calm=False, unicode=True):
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
        if caption is not None:
            output.append((codes[10] if colour else '')+caption+("\x1b[0m" if colour else ''))
        output.append((codes[10] if colour else '')+status+("\x1b[0m" if colour else ''))
        return "\n".join(output)

    def overlay(self, layer, occupied):
        """Composite a sealed, sparse surface with the original priority rule."""
        if (self.columns,self.rows)!=(layer.columns,layer.rows):
            raise ValueError('surface layer geometry mismatch')
        for row,col in occupied:
            self.masks[row][col] |= layer.masks[row][col]
            if layer.priorities[row][col] >= self.priorities[row][col]:
                self.roles[row][col]=layer.roles[row][col]
                self.priorities[row][col]=layer.priorities[row][col]


class RelationLayerCache:
    """A tiny LRU for settled tool/branch routes; event gestures bypass it."""
    def __init__(self,maxsize=4):
        self.maxsize=max(1,int(maxsize));self.layers=OrderedDict()
        self.builds=0;self.hits=0

    def clear(self):
        self.layers.clear();self.builds=0;self.hits=0

    @property
    def size(self):return len(self.layers)

    def get_or_create(self,key,builder):
        cached=self.layers.get(key)
        if cached is not None:
            self.layers.move_to_end(key);self.hits+=1
            return cached
        layer=builder()
        occupied=tuple((row,col) for row,masks in enumerate(layer.masks)
                       for col,mask in enumerate(masks) if mask)
        value=(layer,occupied)
        self.layers[key]=value;self.layers.move_to_end(key);self.builds+=1
        while len(self.layers)>self.maxsize:self.layers.popitem(last=False)
        return value


ACTIVE_RELATION_LAYER_CACHE=RelationLayerCache()


def life_amount(record, lively, calm, reduced_motion):
    """Decorative motion only; unavailable evidence and quiet controls win."""
    if not lively or calm or reduced_motion or record['stale'] or record['state'] in {'unknown','ended'}:
        return 0
    return {'waiting':.25,'stopped':.35,'interrupted':.35,'idle':.65}.get(record['state'],1)


def _witness_canvas(surface, record, *, body_rows, cx, cy, sx, sy, now, calm,
                    reduced_motion, frozen, lively):
    """Paint the latest observed event in a canvas below Keeper when it fits."""
    if surface.columns < 32 or body_rows < 8:
        return

    sequence=record.get('sequence')
    event=next((item for item in reversed(record.get('transitions',[]))
                if item['sequence']==sequence),None)
    if not record.get('event_observed') or event is None:
        return

    # Reserve a row after Keeper's longest filament. The larger canvas uses
    # the open space below the body, and naturally contracts with short panes.
    tail_bottom=cy+216*sy
    below_row=math.ceil(tail_bottom/4)+1
    below_rows=body_rows-below_row
    if below_rows>=5:
        tile_columns=min(48,surface.columns-4,max(16,round(surface.columns*.72)))
        tile_rows=min(12,below_rows)
        left=max(2,math.ceil(cx/2-tile_columns/2))
        left=min(left,surface.columns-tile_columns-2)
        x0,y0=left*2,below_row*4
        x1=x0+tile_columns*2-1;y1=y0+tile_rows*4-1
        edge=min(5,max(2,tile_rows//2))
    else:
        # Keep the existing compact mark for ordinary short terminal heights.
        left_cells=(cx-147*sx)/2
        tile_columns=min(9,int(left_cells)-2)
        if tile_columns < 4:
            return
        x0,y0=2,max(4,min((body_rows-4)*4,round(body_rows*.16)*4))
        x1=x0+tile_columns*2-1;y1=y0+11
        edge=2
    for a,b in (((x0,y0),(x0+edge,y0)),((x0,y0),(x0,y0+edge)),
                ((x1-edge,y0),(x1,y0)),((x1,y0),(x1,y0+edge)),
                ((x0,y1-edge),(x0,y1)),((x0,y1),(x0+edge,y1)),
                ((x1-edge,y1),(x1,y1)),((x1,y1-edge),(x1,y1))):
        surface.line(a,b,0,0)

    age=now-event['at']
    animate=(not calm and not reduced_motion and not frozen and lively and 0<=age<.72)
    reveal=max(.05,min(1,age/.72)) if animate else 1
    ix0,ix1=x0+2,x1-2;iy0,iy1=y0+2,y1-2

    def p(u,v):
        return (ix0+u*(ix1-ix0),iy0+v*(iy1-iy0))

    def curve(points,role):
        surface.curve([p(*point) for point in points],role,0,until=reveal)

    def line(a,b,role):
        start,end=p(*a),p(*b)
        end=(start[0]+(end[0]-start[0])*reveal,
             start[1]+(end[1]-start[1])*reveal)
        surface.line(start,end,role,0)

    def bead(at,role=5):
        surface.point(*p(*at),role,0)

    kind=event.get('kind') or 'other'
    role={'inspect':6,'change':7,'execute':4,'service':8,'other':1}.get(kind,1)
    eye=(.30,.58);crown=(.72,.12)
    # Keeper's crown, off-centre aperture and trailing line anchor each mark.
    curve(((.08,.76),(.02,.34),(.39,.27),crown),1)
    curve((crown,(.95,.20),(.91,.48),(.83,.59)),2)
    bead(eye);bead((eye[0]+.08,eye[1]),4)

    name=event['event']
    if name=='UserPromptSubmit':
        curve(((.02,.90),(.22,.82),(.58,.47),(.94,.25)),6);bead((.94,.25))
    elif name=='PreToolUse':
        if kind=='inspect':
            curve((eye,(.46,.34),(.71,.42),(.96,.24)),6);bead((.96,.24))
        elif kind=='change':
            curve(((.25,.22),(.49,.34),(.62,.66),(.91,.78)),7)
            curve(((.24,.77),(.48,.62),(.62,.35),(.92,.24)),6)
        elif kind=='execute':
            line((.36,.61),(.36,.91),4);line((.14,.91),(.92,.91),4)
        elif kind=='service':
            curve(((.56,.42),(.68,.12),(.97,.25),(.81,.49)),8)
            curve(((.81,.49),(.64,.69),(.47,.52),(.56,.42)),8);bead((.82,.29))
        else:
            curve((eye,(.49,.42),(.72,.71),(.96,.45)),1)
    elif name=='PostToolUse':
        curve(((.98,.24),(.78,.38),(.52,.54),eye),role);bead(eye)
    elif name=='PermissionRequest':
        for x in (.16,.84):line((x,.22),(x,.82),3)
        for y in (.22,.82):
            line((.16,y),(.30,y),3);line((.70,y),(.84,y),3)
        bead((.50,.52))
    elif name=='SubagentStart':
        curve((eye,(.48,.51),(.65,.50),(.94,.18)),8)
        curve(((.48,.51),(.64,.52),(.69,.72),(.94,.86)),2)
        bead((.94,.18));bead((.94,.86))
    elif name=='SubagentStop':
        curve(((.06,.18),(.30,.30),(.43,.48),(.60,.53)),8)
        curve(((.06,.86),(.30,.72),(.43,.57),(.60,.53)),2)
        curve(((.60,.53),(.76,.53),(.82,.46),(.96,.42)),5)
    elif name=='Interrupt':
        line((.12,.78),(.40,.50),9);line((.59,.34),(.88,.08),9);bead((.50,.51),9)
    elif name=='PreCompact':
        curve(((.06,.14),(.28,.24),(.38,.42),(.50,.53)),3)
        curve(((.96,.15),(.78,.29),(.65,.43),(.50,.53)),2);bead((.50,.53))
    elif name=='PostCompact':
        curve(((.50,.53),(.35,.31),(.22,.19),(.04,.14)),3)
        curve(((.50,.53),(.70,.31),(.82,.20),(.97,.13)),2);bead((.50,.53))
    elif name=='Stop':
        line((.12,.82),(.91,.82),4);bead((.70,.77))
    elif name=='SessionStart':
        curve(((.12,.83),(.12,.42),(.36,.19),crown),1);bead((.87,.29))
    elif name=='SessionEnd':
        curve(((.10,.35),(.24,.84),(.76,.84),(.91,.35)),2)
        line((.22,.86),(.80,.86),0)
    else:
        curve((eye,(.44,.30),(.71,.68),(.95,.42)),role)


def _relation_surface(columns,rows,draw):
    layer=Surface(columns,rows)
    draw(layer)
    return layer


def draw_keeper(record, columns, rows, status, *, mode='balanced', now=0,
                calm=False, reduced_motion=False, blink=False, colour=False,
                truecolour=False, lively=True, caption=None, relation_cache=True):
    level=detail(columns,rows)
    if level in {'micro','insufficient'}:
        return micro(record,columns,rows,now,unicode=True,reduced_motion=reduced_motion,calm=calm,colour=colour)
    if level=='small':
        return miniature(record,columns,rows,status,now,colour=colour,truecolour=truecolour,
                         calm=calm,reduced_motion=reduced_motion,mode=mode,lively=lively,
                         caption=caption)
    caption_rows=len(caption.splitlines()) if caption is not None else 0
    body_rows=max(0,rows-1-caption_rows)
    surface=Surface(columns,body_rows)
    if columns < 3 or rows < 3:
        return surface.frame(status,caption=caption,colour=colour,truecolour=truecolour)
    w,h=columns*2,body_rows*4
    frozen=record['stale'] or record['state']=='unknown'
    state='unknown' if frozen else record['state']
    gestures=not reduced_motion and not frozen
    animate=gestures and state!='ended'
    life=life_amount(record,lively,calm,reduced_motion)
    # Tall side panes need the Focus-size envelope; keep the existing uniform
    # geometry so the aperture and crown remain the same Keeper at portrait sizes.
    portrait=rows>=columns*.65
    scale=min(w/610,h/430)*(.96 if mode=='focus' or portrait else .74)
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

    _witness_canvas(surface,record,body_rows=body_rows,cx=cx,cy=cy,sx=sx,sy=sy,now=now,
                    calm=calm,reduced_motion=reduced_motion,frozen=frozen,
                    lively=lively)

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
    latest_start_tool={};latest_start_agent={}
    for event in ribbons:
        if not event['key']:continue
        if event['event']=='PreToolUse':latest_start_tool[event['key']]=event
        elif event['event']=='SubagentStart':latest_start_agent[event['key']]=event

    # The membrane breathes independently from its observed work tethers. Use
    # the stable body envelope for these routes so a settled route can be
    # rasterized once and reused without flattening Keeper's body motion.
    relation_sx=scale*(1-fold) if lively else sx
    relation_sy=scale*(1-fold*.6) if lively else sy
    def paint_relations(target):
        def rp(x,y):return (cx+x*relation_sx,cy+y*relation_sy)
        def relation_curve(points,role=1,priority=1,dash=0,until=1):
            return target.curve([rp(*q) for q in points],role,priority,dash,until)
        def relation_line(a,b,role=1,priority=1,dash=0):
            target.line(rp(*a),rp(*b),role,priority,dash)
        def relation_ring(x,y,r,role=1,priority=1,aspect=1,start=0,end=math.tau):
            target.ellipse(rp(x,y),max(.6,r*relation_sx),
                           max(.6,r*relation_sy*aspect),role,priority,start,end)
        for agent,items in ((False,record['active_tools']),(True,record['active_subagents'])):
            starts=latest_start_agent if agent else latest_start_tool
            for item in items:
                points=route(item['key'],agent);role=8 if agent else kind_roles[item['kind']]
                extension=1
                start_event=starts.get(item['key'])
                if gestures and start_event and 0<=now-start_event['at']<arrival_time:
                    extension=max(.08,(now-start_event['at'])/arrival_time)
                held=frozen or state in {'waiting','stopped','interrupted','ended'}
                dash=3 if held else 2 if agent or item.get('kind') in {'execute','other'} else 0
                until=.72 if state=='ended' else extension
                relation_curve(points,role,1,dash,until)
                x,y=points[-1]
                if agent:
                    relation_ring(x,y,7,role,2);relation_ring(x,y,2.5,role,2)
                elif held or item['kind']=='service':
                    relation_ring(x,y,4.5,role,2)
                    if state=='waiting':relation_line((x-2,y),(x+2,y),role,2)
                else:
                    relation_ring(x,y,2,role,2)
                    target.point(*rp(x,y),role,2)
                if not agent and item['kind']=='change' and not held:
                    relation_curve([(x,y+4) for x,y in points],role,1,0,extension)

    relation_gesture_live=False
    if gestures:
        for agent,items in ((False,record['active_tools']),(True,record['active_subagents'])):
            starts=latest_start_agent if agent else latest_start_tool
            for item in items:
                start_event=starts.get(item['key'])
                if start_event and 0<=now-start_event['at']<arrival_time:
                    relation_gesture_live=True;break
            if relation_gesture_live:break
    relation_key=(columns,body_rows,state,frozen,mode,relation_sx,relation_sy,
                  tuple((item['key'],item['kind']) for item in record['active_tools']),
                  tuple(item['key'] for item in record['active_subagents']))
    if relation_cache and lively and not relation_gesture_live:
        relation_layer,occupied=ACTIVE_RELATION_LAYER_CACHE.get_or_create(
            relation_key,lambda: _relation_surface(columns,body_rows,paint_relations))
        surface.overlay(relation_layer,occupied)
    else:
        paint_relations(surface)
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
    return surface.frame(status,caption=caption,colour=colour,truecolour=truecolour,
                         dim=frozen or state=='ended',calm=calm)
