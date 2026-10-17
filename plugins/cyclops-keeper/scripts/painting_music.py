"""Deterministic instrumental score from painting marks; no words or model calls.
Colour/fifths/84-bpm mapping follows Spark's documented shared roll convention.
"""
import array,colorsys,math,time,wave
MODES={'major':[0,2,4,5,7,9,11],'dorian':[0,2,3,5,7,9,10],'aeolian':[0,2,3,5,7,8,10]}
FIFTHS=[0,7,2,9,4,11,6,1,8,3,10,5]

def colour(p):
    x=y=light=warm=total=0
    for m in p['marks']:
        h,l,s=colorsys.rgb_to_hls(*m['c']);w=m['a']*(4 if m['k']=='fill' else 2 if m['k']=='glow' else .4)
        x+=math.cos(h*math.tau)*s*w;y+=math.sin(h*math.tau)*s*w
        light+=l*w;warm+=math.cos((h-1/12)*math.tau)*s*w;total+=w
    return math.atan2(y,x)%math.tau,light/max(.001,total),warm/max(.001,total)

def score(paintings):
    colours=[colour(p) for p in paintings];n=max(1,len(colours))
    hue=math.atan2(sum(math.sin(c[0]) for c in colours),sum(math.cos(c[0]) for c in colours))%math.tau
    light=sum(c[1] for c in colours)/n;warm=sum(c[2] for c in colours)/n
    mode='major' if warm>.1 and light>.32 else 'aeolian' if warm<-.15 and light<.3 else 'dorian'
    root=FIFTHS[round(hue/math.tau*12)%12];scale=MODES[mode]
    def tone(d,octave=4):return 12*(octave+1)+root+scale[d%7]+12*(d//7)
    events=[];starts=[];holds=[];at=2.
    def add(t,midi,length,voice,vel=.25,pan=0):events.append(dict(t=t,midi=midi,length=length,voice=voice,vel=vel,pan=pan))
    for d in (0,2,4):add(0,tone(d,3),2.6,'pad',.12)
    for i,p in enumerate(paintings):
        starts.append(at)
        turn=.5 if i==0 else abs(math.sin((colours[i][0]-colours[i-1][0])/2))
        beats=4+round(min(1,.5*min(1,len(p['marks'])/60)+.5*turn)*4)+(4 if i==len(paintings)-1 else 0)
        hold=beats*60/84;holds.append(hold);degree=0 if i==len(paintings)-1 else (i*3)%7
        for d in (degree,degree+2,degree+4):add(at,tone(d,3),2+hold,'pad',.1)
        for j,m in enumerate(p['marks']):
            pts=m.get('pts');x=sum(v[0] for v in pts)/len(pts) if pts else m.get('x',.5)
            y=sum(v[1] for v in pts)/len(pts) if pts else m.get('y',.5)
            voice={'dot':'bell','ring':'bell','arc':'bell','line':'pluck','curve':'pluck','spray':'sparkle','glow':'swell'}.get(m['k'])
            if voice:add(at+2*j/max(1,len(p['marks'])),tone(round((1-y)*12),4),1.7 if voice!='swell' else 3,voice,.1+.22*m['a'],x*2-1)
        at+=2+hold-(.6 if i<len(paintings)-1 else 0)
    return dict(root=root,mode=mode,starts=starts,holds=holds,duration=at,events=events)


def write_music(path,plan,report=lambda _:None,rate=22050):
    events=plan['events'];total=math.ceil(plan['duration']*rate)
    with wave.open(str(path),'wb') as out:
        out.setnchannels(2);out.setsampwidth(2);out.setframerate(rate)
        for start in range(0,total,rate//4):
            count=min(rate//4,total-start);left=[0.]*count;right=[0.]*count
            t0=start/rate;t1=(start+count)/rate
            for e in events:
                if e['t']>=t1 or e['t']+e['length']<=t0:continue
                lo=max(0,math.ceil((e['t']-t0)*rate));hi=min(count,math.ceil((e['t']+e['length']-t0)*rate))
                freq=440*2**((e['midi']-69)/12);pan=(e['pan']+1)/2
                for k in range(lo,hi):
                    t=t0+k/rate-e['t'];phase=t*freq*math.tau;remaining=max(0,1-t/e['length'])
                    if e['voice']=='pad':v=math.sin(phase)*min(1,t/.25)*min(1,remaining*4)*.35
                    elif e['voice']=='swell':v=math.sin(phase)*math.sin(math.pi*t/e['length'])*.5
                    else:
                        overtone=2.71 if e['voice']=='bell' else 3 if e['voice']=='sparkle' else 2
                        v=(math.sin(phase)+.25*math.sin(phase*overtone))*math.exp(-t*(5 if e['voice']=='pluck' else 3))*min(1,t/.008)*remaining
                    v*=e['vel']*.5;left[k]+=v*math.sqrt(1-pan);right[k]+=v*math.sqrt(pan)
            data=array.array('h')
            for a,b in zip(left,right):data.extend((round(math.tanh(a)*26000),round(math.tanh(b)*26000)))
            import sys
            if sys.byteorder!='little':data.byteswap()
            out.writeframesraw(data.tobytes());report((start+count)/total);time.sleep(.001)
