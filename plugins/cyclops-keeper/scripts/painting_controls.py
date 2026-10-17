"""Painting UI state and bounded terminal input; no model or file writes."""
import os
from pathlib import Path
import re
import time

class Input:
    def __init__(self):self.data=b'';self.since=0
    def feed(self,data,now=None):
        now=time.monotonic() if now is None else now
        if not self.data:self.since=now
        self.data=(self.data+data)[-4096:];out=[]
        while self.data:
            if self.data.startswith(b'\x1b[<'):
                match=re.match(rb'\x1b\[<([0-9]{1,3});([0-9]{1,5});([0-9]{1,5})([Mm])',self.data)
                if match:
                    button,x,y,end=match.groups();self.data=self.data[match.end():]
                    if int(button)==0 and end==b'M':out.append(('click',int(x)-1,int(y)-1))
                    continue
                if len(self.data)<40 and now-self.since<.1:break
                self.data=b'';break
            if self.data.startswith(b'\x1b'):
                if self.data in (b'\x1b',b'\x1b[') and now-self.since<.06:break
                if self.data==b'\x1b':out.append(('key',b'\x1b'));self.data=b'';break
                match=re.match(rb'\x1b\[[0-9;?]*[A-Za-z~]',self.data)
                if match:self.data=self.data[match.end():];continue
                self.data=b'';break
            out.append(('key',self.data[:1]));self.data=self.data[1:]
        return out


def collect(project,since=0):
    import painting_store as store
    result=[]
    for owner in store.OWNERS:
        try:
            with store.folder(project,owner) as fd:
                for name in store.entries(fd):
                    try:p=store.load(fd,name,owner)
                    except (OSError,ValueError,TypeError,OverflowError):continue
                    if p['at']>=since:
                        result.append(p)
                        if len(result)>1000:raise ValueError('More than 1000 paintings; choose Session instead')
        except FileNotFoundError:continue
        except OSError:continue
    return sorted(result,key=lambda p:(p['at'],p['by'],p['title']))


def has_paintings(project):
    import painting_store as store
    for owner in store.OWNERS:
        try:
            with store.folder(project,owner) as fd:
                for name in store.entries(fd):
                    try:store.load(fd,name,owner);return True
                    except (OSError,ValueError,TypeError,OverflowError):continue
        except (OSError,ValueError):continue
    return False


def launch_time(owner):
    # Linux process birth in epoch seconds; contains no session identifiers.
    boot=next(int(line.split()[1]) for line in Path('/proc/stat').read_text().splitlines() if line.startswith('btime '))
    return boot+int(owner['start'])/os.sysconf('SC_CLK_TCK')


def progress(value,width,unicode=True):
    value=max(0,min(1,value));n=max(3,min(18,width-8));units=round(value*n*8)
    full,part=divmod(units,8)
    middle=('█'*full+('▏▎▍▌▋▊▉'[part-1] if part else '')).ljust(n) if unicode else ('#'*round(value*n)).ljust(n,'-')
    return ('|'+middle+'| '+str(round(value*100))+'%')[:width]


class Story:
    def __init__(self):self.items=[];self.index=0;self.began=0;self.paused_at=None;self.finished=False
    @property
    def active(self):return bool(self.items)
    def start(self,items,now):
        self.items=list(items);self.index=0;self.began=now;self.paused_at=None;self.finished=False
    def frame(self,now):
        if not self.items:return None,1
        elapsed=max(0,(self.paused_at if self.paused_at is not None else now)-self.began)
        while elapsed>=9.4 and self.index<len(self.items)-1:
            self.index+=1;self.began+=9.4;elapsed-=9.4
        if self.index==len(self.items)-1 and elapsed>=9.4:self.finished=True
        return self.items[self.index],min(1,elapsed/2.4)
    def pause(self,now):
        if self.paused_at is None:self.frame(now);self.paused_at=now
        else:self.began+=now-self.paused_at;self.paused_at=None
    def next(self,now,delta=1):
        self.index=max(0,min(len(self.items)-1,self.index+delta));self.began=now;self.finished=False
        if self.paused_at is not None:self.paused_at=now
    def again(self,now):self.start(self.items,now)
    def end(self):self.items=[];self.paused_at=None;self.finished=False


def buttons(items,width,row):
    text='';hits=[]
    for label,action in items:
        label='['+label+']'
        if len(text)+len(label)>width:break
        hits.append({'x0':len(text),'x1':len(text)+len(label),'y':row,'action':action})
        text+=label+' '
    return text[:width].ljust(width),hits
