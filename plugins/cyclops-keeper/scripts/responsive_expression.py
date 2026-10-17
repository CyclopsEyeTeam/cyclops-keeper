"""Small-scale Keeper forms made from terminal geometry, never image crops."""
import hashlib
import math
from responsive import detail

INDICATORS={'unknown':'?', 'idle':'.', 'working':'>', 'tool':'+', 'branching':'*',
            'waiting':'!', 'compacting':'~', 'stopped':'=', 'interrupted':'x', 'ended':'-'}


def micro(record, columns, rows, now, *, unicode=True, reduced_motion=False, calm=False, colour=False, theme='classic'):
    if columns < 2 or rows < 1:
        return '\n'.join(' '*columns for _ in range(rows))
    frozen=record['stale'] or record['state']=='unknown'
    state='unknown' if frozen else record['state']
    eye='◎' if unicode else 'O'
    mark=INDICATORS[state]
    text=eye+(' ' if columns>=3 else '')+mark
    if columns>=4 and not frozen and state!='ended':
        pulse='.' if reduced_motion or calm or int(now*1.25)%2==0 else ':'
        text+=pulse
    line=text.center(columns)
    if colour:
        from terminal_art import colour_codes
        code=('\x1b[38;5;'+('244' if frozen or state=='ended' else '223')+'m'
              if theme=='classic' else colour_codes(False,frozen or state=='ended',calm,theme)[4])
        line=code+line+'\x1b[0m'
    return '\n'.join(line if row==rows//2 else ' '*columns for row in range(rows))


def miniature(record, columns, rows, status, now, *, colour=False, truecolour=False,
              calm=False, reduced_motion=False, unicode=True, mode='balanced', lively=True,
              caption=None, theme='classic'):
    # Import only when drawing, avoiding a module-initialization cycle.
    from terminal_art import Surface, life_amount, expression_particles
    caption_rows=len(caption.splitlines()) if caption is not None else 0
    surface=Surface(columns,max(0,rows-1-caption_rows))
    frozen=record['stale'] or record['state']=='unknown'
    state='unknown' if frozen else record['state']
    life=life_amount(record,lively,calm,reduced_motion)
    width,height=columns*2,surface.rows*4
    portrait=rows>=columns*.65
    prominent=mode=='focus' or portrait
    scale=min(width/48,max(1,height)/52)*(1 if prominent else .9)
    cx,cy=width*(.43 if prominent else .40),height*.43
    fold=.6 if state=='compacting' else 1
    breathe=1 if frozen or reduced_motion or calm else 1+math.sin(now*.6)*(.015+.02*life)
    def p(x,y):return (cx+x*scale*fold*breathe,cy+y*scale*fold*breathe)
    def curve(points,role=1,dash=0):surface.curve([p(*q) for q in points],role,1,dash)
    # Two asymmetrical membrane arcs, open high crown and two loose filaments.
    curve([(7,-17),(-16,-14),(-13,12),(-3,13)],1)
    curve([(7,-17),(19,-10),(12,12),(-3,13)],2)
    surface.line(p(6,-17),p(10,-22),3,3)
    surface.line(p(10,-22),p(13,-16),3,3)
    sway=math.sin(now*.75)*2*life
    lag=math.sin(now*.83+1.7)*2*life
    curve([(-4,12),(-10+sway*.3,16),(-9+sway*.7,22),(-14+sway,25)],2)
    curve([(0,12),(6+lag*.3,15),(2+lag*.7,23),(5+lag,24)],1,2 if state=='interrupted' else 0)
    surface.ellipse(p(0,0),max(2,5*scale*fold),max(3,7*scale*fold),4,3)
    if state=='waiting':
        surface.line(p(-7,-5),p(-7,5),3,3)
        surface.line(p(7,-5),p(7,5),3,3)
    if state=='unknown':surface.ellipse(p(-9,-5),1,1,0,2)
    if state=='interrupted':surface.line(p(4,17),p(7,20),9,3)
    # Two tools/one branch stay distinct; remaining counts are explicit below.
    for item in record['active_tools'][:2]:
        digest=hashlib.sha256(item['key'].encode('ascii')).digest()
        end=(15+digest[0]/255*4,-7+digest[1]/255*18)
        curve([(4,-5),(10,-8),(12,end[1]),end],6,2 if frozen or state=='waiting' else 0)
        surface.ellipse(p(*end),1,1,6,2)
    if record['active_subagents']:
        curve([(8,-18),(12,-23),(18,-19),(19,-14)],8)
        surface.ellipse(p(19,-14),2,2,8,2)
    expression_particles(surface,record,now,(cx,cy),scale,
                         lively=lively,calm=calm,reduced_motion=reduced_motion)
    eye_col=max(0,min(columns-1,round(cx/2)))
    eye_row=max(0,min(rows-2,round(cy/4)))
    surface.glyphs[(eye_row,eye_col)]='◎' if unicode else 'O'
    tools=len(record['active_tools']);branches=len(record['active_subagents'])
    label=f'KEEPER {state.upper()}'
    if tools:label+=f' T:{tools}'+('+' if tools>2 else '')
    if branches:label+=f' B:{branches}'+('+' if branches>1 else '')
    if record.get('relations_incomplete'):label+=' ?'
    return surface.frame(label[:columns].ljust(columns),caption=caption,
                         colour=colour,truecolour=truecolour,
                         dim=frozen or state=='ended',calm=calm,unicode=unicode,theme=theme)
