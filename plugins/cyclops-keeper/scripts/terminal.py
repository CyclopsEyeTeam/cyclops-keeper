#!/usr/bin/env python3
"""Balanced and Focus terminal compositions for the local Keeper observer."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import select
import shutil
import signal
import statistics
import sys
import termios
import time
import tty

sys.dont_write_bytecode = True
from activity import EVENTS, LABELS, TOOL_KINDS, default_data, public_snapshot
from terminal_art import draw_keeper

KEY_PATTERN = set('0123456789abcdef')


def _key(value):
    return isinstance(value, str) and len(value) == 64 and set(value) <= KEY_PATTERN


def _record(value, stale=False):
    if isinstance(value, str):
        event = {'idle':'SessionStart','unknown':'SessionStart','working':'UserPromptSubmit',
                 'tool':'PreToolUse','branching':'SubagentStart','compacting':'PreCompact',
                 'waiting':'PermissionRequest','stopped':'Stop','interrupted':'Interrupt',
                 'ended':'SessionEnd'}.get(value, 'SessionStart')
        return {'schema':'activity-face/v1','state':value if value in LABELS else 'unknown',
                'event':event,'updated_at':0,'sequence':0,'stale':stale,
                'active_tools':[],'active_subagents':[],'transitions':[]}
    if not isinstance(value, dict):
        return _record('unknown')
    state=value.get('state') if value.get('state') in LABELS else 'unknown'
    event=value.get('event') if value.get('event') in EVENTS else 'SessionStart'
    tools=[]
    for item in value.get('active_tools',[]) if isinstance(value.get('active_tools'),list) else []:
        if isinstance(item,dict) and _key(item.get('key')):
            kind=item.get('kind') if item.get('kind') in TOOL_KINDS else 'other'
            sequence=item.get('sequence') if isinstance(item.get('sequence'),int) else 0
            tools.append({'key':item['key'],'kind':kind,'sequence':sequence})
    agents=[]
    for item in value.get('active_subagents',[]) if isinstance(value.get('active_subagents'),list) else []:
        if isinstance(item,dict) and _key(item.get('key')):
            sequence=item.get('sequence') if isinstance(item.get('sequence'),int) else 0
            agents.append({'key':item['key'],'sequence':sequence})
    transitions=[]
    for item in value.get('transitions',[]) if isinstance(value.get('transitions'),list) else []:
        if (isinstance(item,dict) and item.get('event') in EVENTS and
                isinstance(item.get('sequence'),int) and isinstance(item.get('at'),(int,float))):
            transitions.append({'sequence':item['sequence'],'event':item['event'],
                                'at':item['at'],'key':item.get('key') if _key(item.get('key')) else None,
                                'kind':item.get('kind') if item.get('kind') in TOOL_KINDS else None})
    return {'schema':'activity-face/v1','state':state,'event':event,
            'relations_incomplete':bool(value.get('relations_incomplete')),
            'updated_at':value.get('updated_at',0),'sequence':value.get('sequence',0),
            'stale':bool(stale or value.get('stale')),'active_tools':sorted(tools,key=lambda x:(x['sequence'],x['key'])),
            'active_subagents':sorted(agents,key=lambda x:(x['sequence'],x['key'])),
            'transitions':sorted(transitions[-32:],key=lambda x:x['sequence'])}


def _glyphs(unicode):
    if unicode:
        return {'h':'─','v':'│','up':'╱','down':'╲','dot':'·','light':'∘',
                'ring':'○','eye':'◎','pupil':'┃','sat':'◉','crown':'⌃',
                'node':'◦','cross':'×','dash':'┄','trail':'┈'}
    return {'h':'-','v':'|','up':'/','down':'\\','dot':'.','light':'.',
            'ring':'o','eye':'O','pupil':'|','sat':'o','crown':'^',
            'node':'+','cross':'x','dash':':','trail':'.'}


def render(snapshot, width, height, blink=False, stale=False, *, mode='balanced',
           now=0, calm=False, reduced_motion=False, unicode=True,
           colour=False, truecolour=False):
    """Draw one exact cell grid. Tool routes are key-stable and viewport-clamped."""
    width=max(1,int(width));height=max(1,int(height))
    mode='focus' if mode=='focus' else 'balanced'
    current=_record(snapshot,stale)
    state=current['state'];events=current['transitions'];g=_glyphs(bool(unicode))
    label=LABELS.get(state,LABELS['unknown'])
    status=f"KEEPER / {label}"
    if current.get('relations_incomplete'):status+=' / UNTRACKED RELATIONS'
    if current['stale']:status+=' / LAST SIGNAL OLD'
    if current['active_tools'] and width>=24:status+=f" / {len(current['active_tools'])} TETHER{'S' if len(current['active_tools'])!=1 else ''}"
    if current['active_subagents'] and width>=32:status+=f" / {len(current['active_subagents'])} BRANCH{'ES' if len(current['active_subagents'])!=1 else ''}"
    if width>=50:status+=f" / {'CALM' if calm else 'C:CALM'} {'REDUCED' if reduced_motion else 'R:REDUCED'}  Q:EXIT"
    status=status[:width].ljust(width)
    if unicode:
        return draw_keeper(current,width,height,status,mode=mode,now=now,
                           calm=calm,reduced_motion=reduced_motion,blink=blink,
                           colour=colour,truecolour=truecolour)
    body_rows=max(0,height-1)
    grid=[[' ' for _ in range(width)] for _ in range(body_rows)]
    def put(x,y,ch):
        if body_rows and math.isfinite(x) and math.isfinite(y):
            ix,iy=round(x),round(y)
            if 0<=ix<width and 0<=iy<body_rows:grid[iy][ix]=ch
    def line(a,b,char=None):
        x0,y0=map(round,a);x1,y1=map(round,b)
        dx,dy=abs(x1-x0),abs(y1-y0);sx=1 if x0<x1 else -1;sy=1 if y0<y1 else -1
        err=dx-dy
        while True:
            if char is None:
                ch=g['h'] if abs(x1-x0)>=abs(y1-y0)*1.4 else g['v'] if abs(y1-y0)>=abs(x1-x0)*1.4 else g['up'] if (x1-x0)*(y1-y0)<0 else g['down']
            else:ch=char
            put(x0,y0,ch)
            if x0==x1 and y0==y1:break
            e2=2*err
            if e2>-dy:err-=dy;x0+=sx
            if e2<dx:err+=dx;y0+=sy
    def ellipse(cx,cy,rx,ry,char=None,steps=None):
        if rx<=0 or ry<=0:return
        count=steps or max(12,round(math.tau*max(rx,ry)*2.1))
        previous=None
        for i in range(count+1):
            a=math.tau*i/count;p=(cx+rx*math.cos(a),cy+ry*math.sin(a))
            if previous is not None:line(previous,p,char)
            previous=p
    def strand(a,b,c,d,texture=None):
        count=max(12,round((abs(d[0]-a[0])+abs(d[1]-a[1]))*2.2));prev=None
        for i in range(count+1):
            t=i/count;u=1-t
            x=u**3*a[0]+3*u*u*t*b[0]+3*u*t*t*c[0]+t**3*d[0]
            y=u**3*a[1]+3*u*u*t*b[1]+3*u*t*t*c[1]+t**3*d[1]
            p=(x,y)
            if prev is not None:line(prev,p,texture)
            else:put(x,y,texture or g['dot'])
            prev=p
    def bezier_points(a,b,c,d,count=16,until=1):
        result=[]
        steps=max(1,round(count*max(0,min(1,until))))
        for i in range(steps+1):
            t=max(0,min(1,until))*i/steps;u=1-t
            result.append((u**3*a[0]+3*u*u*t*b[0]+3*u*t*t*c[0]+t**3*d[0],
                           u**3*a[1]+3*u*u*t*b[1]+3*u*t*t*c[1]+t**3*d[1]))
        return result
    def polyline(points,char=None):
        for p,q in zip(points,points[1:]):line(p,q,char)
    if body_rows and width>=3:
        usable_w=max(1,width-2);usable_h=max(1,body_rows-1)
        cx=(width-1)*(.47 if mode=='focus' else .49)
        cy=(body_rows-1)*(.5 if mode=='focus' else .49)
        if mode=='focus':
            rx=max(1,min(usable_w*.235,usable_h*.46));ry=max(1,min(usable_h*.47,usable_w*.22))
            tether_span=max(1,(width-1)-(cx+rx*.55)-1)
        else:
            rx=max(1,min(usable_w*.135,usable_h*.35));ry=max(1,min(usable_h*.36,usable_w*.12))
            tether_span=max(1,min((width-1)-(cx+rx*.55)-1,usable_w*.25))
        fold=state=='compacting'
        if fold:rx*=.78
        # Asymmetric membrane: an open upper-right crown, one aperture, and a
        # long single thread that falls left of the body.
        def p(nx,ny):return (cx+nx*rx,cy+ny*ry)
        for offset in (0,.07,.14):
            strand(p(.76,-1.02),p(.92-offset,-.39),p(.28-offset,.27),p(-.17,.16))
            strand(p(.76,-1.02),p(.57-offset,-.58),p(-.88+offset,-.08),p(-.17,.16))
        strand(p(-.17,.16),p(-.62,.43),p(.54,.7),p(.08,1.02))
        strand(p(-.31,.08),p(-.72,.54),p(.34,.71),p(-.27,.98),g['dot'])
        # The final strand is deliberately asymmetric; writing it separately
        # keeps the aperture and crown recognizable at small character sizes.
        strand(p(.14,.14),p(.63,.47),p(-.1,.83),p(.28,.98),g['trail'])
        eye_x,eye_y=p(-.13,-.17);erx=max(1,rx*.27);ery=max(1,ry*.24)
        ellipse(eye_x,eye_y,erx,ery);ellipse(eye_x,eye_y,erx*.69,ery*.68)
        pupil=g['ring'] if current['stale'] or state=='unknown' else '-' if blink and not reduced_motion else g['pupil']
        put(eye_x,eye_y,pupil)
        if state=='waiting':
            put(eye_x,eye_y-1,g['dot']);put(eye_x,eye_y+1,g['dot'])
        crown=p(.76,-1.02)
        line(p(.5,-.8),crown);line(crown,p(.9,-.78));line(crown,p(.7,-.68),g['dot'])
        put(*crown,g['crown'])

        tools=current['active_tools'];agents=current['active_subagents'];frozen=current['stale'] or state=='unknown'
        tool_return={e['key']:e for e in events if e['event']=='PostToolUse' and e['key']}
        agent_return={e['key']:e for e in events if e['event']=='SubagentStop' and e['key']}
        def route_for(key,is_agent=False):
            route_key=hashlib.sha256(key.encode('ascii')).hexdigest()
            h1=int(route_key[:8],16)/0xffffffff;h2=int(route_key[8:16],16)/0xffffffff
            start=p(.52,-.48) if not is_agent else p(.64,-.87)
            reach=tether_span*(.55+.43*h2)
            end=(min(width-2,start[0]+reach),max(0,min(body_rows-1,cy+((h1-.5)*2)*max(1,min(ry*1.35,usable_h*.39)))))
            c1=(start[0]+reach*.31,start[1]+(end[1]-start[1])*.1)
            c2=(end[0]-reach*.24,end[1])
            return start,c1,c2,end,h1,h2
        def path_glyph(kind):
            return {'inspect':g['h'],'change':'=' if not unicode else '═',
                    'execute':g['dot'],'service':':','other':g['trail']}[kind]
        for tool in tools:
            start,c1,c2,end,h1,h2=route_for(tool['key'])
            kind=tool['kind'];stroke=path_glyph(kind)
            matching=tool_return.get(tool['key'])
            age=max(0,now-matching['at']) if matching else 999
            if matching and not reduced_motion and not frozen and age<.8:
                progress=min(1,age/.8);polyline(bezier_points(start,c1,c2,end,14,1-progress),g['dash'])
                point=bezier_points(start,c1,c2,end,14,1-progress)[-1];put(*point,g['node'])
            else:
                start_event=next((e for e in reversed(events) if e['key']==tool['key'] and e['event']=='PreToolUse'),None)
                extension=1
                if start_event and not reduced_motion and not frozen and 0<=now-start_event['at']<.55:
                    extension=max(.08,(now-start_event['at'])/.55)
                if state=='stopped':extension=min(extension,.72)
                if state=='interrupted':extension=min(extension,.83)
                if state=='ended':extension=min(extension,.73)
                polyline(bezier_points(start,c1,c2,end,18,extension),g['dash'] if frozen or state in {'waiting','stopped','interrupted','ended'} else stroke)
                if extension>=.98:
                    mark={'inspect':g['dot'],'change':'=','execute':':','service':'o','other':g['node']}[kind]
                    if unicode and kind=='change':mark='═'
                    put(*end, g['ring'] if frozen or state in {'stopped','ended','interrupted'} else mark)
                    if kind=='change':put(end[0],min(body_rows-1,end[1]+1),mark)
                    if kind=='service':ellipse(end[0],end[1],1,1,g['ring'],8)
                elif state in {'stopped','ended','interrupted'}:
                    anchor=bezier_points(start,c1,c2,end,18,extension)[-1]
                    put(*anchor,g['ring'])
        for agent in agents:
            start,c1,c2,end,h1,h2=route_for(agent['key'],True)
            returning=agent_return.get(agent['key']);age=max(0,now-returning['at']) if returning else 999
            if returning and not reduced_motion and not frozen and age<.8:
                end_progress=max(.05,1-age/.8)
                polyline(bezier_points(start,c1,c2,end,14,end_progress),g['trail'])
                point=bezier_points(start,c1,c2,end,14,end_progress)[-1];put(*point,g['sat'])
            else:
                starting=next((e for e in reversed(events) if e['key']==agent['key'] and e['event']=='SubagentStart'),None)
                extension=1
                if starting and not reduced_motion and not frozen and 0<=now-starting['at']<.55:
                    extension=max(.08,(now-starting['at'])/.55)
                if state=='ended':extension=min(extension,.73)
                polyline(bezier_points(start,c1,c2,end,14,extension),g['trail'] if not frozen else g['dash'])
                if extension<.98:
                    anchor=bezier_points(start,c1,c2,end,14,extension)[-1]
                    put(*anchor,g['ring'])
                ellipse(end[0],end[1],1.35,1.05,g['ring'] if frozen or state=='ended' else g['sat'],10)

        # A matching return remains in the bounded event ribbon after its
        # active relation is removed. Draw its own short retraction so terminal
        # views express the observed return without restoring the tether.
        if not reduced_motion and not frozen:
            active_tool_keys={item['key'] for item in tools}
            active_agent_keys={item['key'] for item in agents}
            for transition in events[-32:]:
                age=now-transition['at']
                if not 0<=age<.8:
                    continue
                remaining=1-age/.8
                key=transition['key']
                if (transition['event']=='PostToolUse' and key
                        and key not in active_tool_keys):
                    start,c1,c2,end,_,_=route_for(key)
                    kind=transition['kind'] or 'other'
                    points=bezier_points(start,c1,c2,end,16,remaining)
                    polyline(points,path_glyph(kind))
                    if points:put(*points[-1],g['node'])
                elif (transition['event']=='SubagentStop' and key
                        and key not in active_agent_keys):
                    start,c1,c2,end,_,_=route_for(key,True)
                    points=bezier_points(start,c1,c2,end,14,remaining)
                    polyline(points,g['trail'])
                    if points:put(*points[-1],g['sat'])

        if not reduced_motion and not frozen:
            for transition in events[-32:]:
                age=now-transition['at']
                if not 0<=age<1:continue
                progress=min(1,age/.65)
                if transition['event']=='UserPromptSubmit':
                    start=(-1,cy);end=(eye_x-erx,eye_y);c1=(cx*.32,cy-ry*.65);c2=(cx-erx*2,eye_y-ry*.25)
                    points=bezier_points(start,c1,c2,end,20,progress);polyline(points,g['dot']);put(*points[-1],g['node'])
                elif transition['event']=='PostCompact':
                    put(*p(.85,-.85),g['crown']);put(*p(.67,-.7),g['node'])
                elif transition['event']=='Interrupt':
                    q=p(.42,.47);put(q[0],q[1],g['cross']);put(q[0]+2,q[1]+1,g['cross'])
                elif transition['event']=='Stop':
                    q=p(.14,.76);put(q[0],q[1],g['dot'])
        if state=='interrupted':
            q=p(.42,.47);put(q[0],q[1],g['cross']);put(q[0]+2,q[1]+1,g['cross'])
        if state=='waiting':
            put(p(.95,-.15)[0],p(.95,-.15)[1],g['ring'])
        if state=='ended':
            put(p(-.25,.93)[0],p(-.25,.93)[1],g['ring'])
        if not reduced_motion and not frozen and not calm and state in {'idle','working','tool','branching'}:
            # A tiny orbit fleck establishes ambient life without implying work.
            orbit=now*.28;put(cx+rx*.88+math.cos(orbit)*1.4,cy-ry*.33+math.sin(orbit)*1.2,g['light'])
        if state=='compacting':put(*p(-.13,-.17),g['dot'])

    frame='\n'.join(''.join(row) for row in grid+[list(status)])
    if colour:
        prefix=colour_code(load_palette().get(state,[160,170,164]),truecolour,current['stale'],calm)
        frame='\n'.join(prefix+row+'\x1b[0m' for row in frame.split('\n'))
    return frame


def load_palette():
    path=Path(__file__).resolve().parents[1]/'assets/palette.json'
    try:return json.loads(path.read_text())['colours']
    except (OSError,ValueError,KeyError):return {}


def colour_code(rgb,truecolour,stale,calm=False):
    factor=.48 if stale else .67 if calm else 1
    rgb=[max(0,min(255,int(v*factor))) for v in rgb]
    if truecolour:return '\x1b[38;2;'+';'.join(str(v) for v in rgb)+'m'
    r,g,b=[round(v/255*5) for v in rgb]
    return f'\x1b[38;5;{16+36*r+6*g+b}m'


def main():
    parser=argparse.ArgumentParser(description='Cyclops Keeper local Codex presence. q / Escape exits; c and r change motion.')
    parser.add_argument('mode',nargs='?',choices=['focus'],help='fill the terminal with Keeper Focus')
    parser.add_argument('--data',type=Path,default=default_data())
    parser.add_argument('--session',help='Pin the full session hash from the state file')
    parser.add_argument('--no-colour',action='store_true')
    parser.add_argument('--ascii',action='store_true',help='Use the complete ASCII fallback')
    parser.add_argument('--calm',action='store_true',help='Lower contrast and ambient rhythm')
    parser.add_argument('--reduced-motion',action='store_true',help='Freeze decoration while applying observed poses immediately')
    parser.add_argument('--once',action='store_true',help='Print one plain-text frame')
    parser.add_argument('--metrics',action='store_true',help='Print bounded local render-work measurements on exit')
    args=parser.parse_args()
    if not args.once and (not sys.stdin.isatty() or not sys.stdout.isatty()):
        parser.error('Open a terminal, or pass --once for a plain-text frame.')
    encoding=(sys.stdout.encoding or '').upper()
    unicode=not args.ascii and 'UTF' in encoding and os.environ.get('TERM')!='dumb'
    truecolour=os.environ.get('COLORTERM') in {'truecolor','24bit'}
    colour=not args.no_colour and 'NO_COLOR' not in os.environ and os.environ.get('TERM')!='dumb'
    mode='focus' if args.mode=='focus' else 'balanced'
    calm=args.calm;reduced_motion=args.reduced_motion
    attrs=termios.tcgetattr(sys.stdin) if not args.once else None
    old_handler=signal.getsignal(signal.SIGTERM)
    measurements={'frames':0,'cpu_ms':0.0,'wall_started':time.perf_counter(),
                  'samples':[],'updates':[],'last_update':None,'phase':'unknown',
                  'max_tools':0,'max_subagents':0,'unicode':unicode,'colour':colour,
                  'mode':mode,'calm':calm,'reduced_motion':reduced_motion}
    def terminate(_sig,_frame):raise KeyboardInterrupt
    try:
        if not args.once:
            signal.signal(signal.SIGTERM,terminate);tty.setcbreak(sys.stdin)
            sys.stdout.write('\x1b[?1049h\x1b[?25l\x1b[2J');sys.stdout.flush()
        last_frame=None
        while True:
            sessions=public_snapshot(args.data,session=args.session)['sessions']
            current=next((s for s in sessions if s['session']==args.session),None) if args.session else next(iter(sessions),None)
            stale=bool(current and current['stale'])
            state=current['state'] if current else 'unknown'
            measurements['phase']=state
            measurements['max_tools']=max(measurements['max_tools'],len(current.get('active_tools',[])) if current else 0)
            measurements['max_subagents']=max(measurements['max_subagents'],len(current.get('active_subagents',[])) if current else 0)
            size=shutil.get_terminal_size((80,24))
            width=max(1,size.columns-1);height=max(1,size.lines)
            begin=time.perf_counter()
            frame=render(current or 'unknown',width,height,
                         blink=not reduced_motion and state in {'idle','stopped'} and time.time()%6.5<.14,
                         stale=stale,mode=mode,now=time.time(),calm=calm,
                         reduced_motion=reduced_motion,unicode=unicode,
                         colour=colour and not args.once,truecolour=truecolour)
            cost=(time.perf_counter()-begin)*1000
            measurements['frames']+=1;measurements['cpu_ms']+=cost
            measurements['samples'].append(cost)
            if len(measurements['samples'])>600:measurements['samples'].pop(0)
            timestamp=time.perf_counter()
            if measurements['last_update'] is not None:
                measurements['updates'].append((timestamp-measurements['last_update'])*1000)
                if len(measurements['updates'])>600:measurements['updates'].pop(0)
            measurements['last_update']=timestamp
            if args.once:
                print(frame)
                break
            if frame!=last_frame:
                rows=frame.split('\n')
                output='\x1b[H'+''.join(row+'\x1b[K\n' for row in rows[:-1])+rows[-1]+'\x1b[K\x1b[0m'
                sys.stdout.write(output);sys.stdout.flush();last_frame=frame
            cadence=.45 if reduced_motion else .25 if calm or state in {'idle','waiting','unknown','stopped'} else .09
            ready=select.select([sys.stdin],[],[],cadence)[0]
            if ready:
                key=os.read(sys.stdin.fileno(),1)
                if key in {b'q',b'Q',b'\x1b',b'\x03'}:break
                if key in {b'c',b'C'}:calm=not calm;last_frame=None
                if key in {b'r',b'R'}:reduced_motion=not reduced_motion;last_frame=None
    except KeyboardInterrupt:
        pass
    finally:
        if not args.once:
            termios.tcsetattr(sys.stdin,termios.TCSADRAIN,attrs)
            signal.signal(signal.SIGTERM,old_handler)
            sys.stdout.write('\x1b[0m\x1b[?25h\x1b[?1049l');sys.stdout.flush()
    if args.metrics:
        sample=measurements['samples'];updates=measurements['updates']
        report={k:v for k,v in measurements.items() if k not in {'samples','updates','last_update'}}
        report.update({'wall_ms':round((time.perf_counter()-measurements['wall_started'])*1000,3),
                       'median_render_ms':round(statistics.median(sample),5) if sample else 0,
                       'p95_render_ms':round(sorted(sample)[min(len(sample)-1,int(len(sample)*.95))],5) if sample else 0,
                       'median_update_ms':round(statistics.median(updates),2) if updates else None,
                       'p95_update_ms':round(sorted(updates)[min(len(updates)-1,int(len(updates)*.95))],2) if updates else None,
                       'measurement':'renderer CPU and observed loop interval; not terminal presentation FPS'})
        print(json.dumps(report,sort_keys=True),file=sys.stderr)


if __name__=='__main__':
    main()
