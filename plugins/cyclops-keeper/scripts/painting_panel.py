"""Persistent painting controller. Runs in the rendering child, never the input loop."""
import json,os,select,signal,subprocess,sys,time
from pathlib import Path
from painting_controls import Story,buttons,collect,has_paintings,launch_time,progress
from painting_terminal import canvas,latest
from launcher_link import read_attachment
from expression import identity

class Panel:
    def __init__(self,path,expected,width,rows,colour,unicode):
        self.path=path;self.expected=expected;self.width=width;self.rows=rows;self.colour=colour;self.unicode=unicode
        self.since=launch_time(expected['owner']);self.story=Story();self.scope='session';self.menu=None;self.message=''
        self.library=[];self.own=None;self.has_any=False;self.next_scan=0;self.job=None;self.jobbuf=b'';self.status=None;self.cancel_at=None
        self.way='truest';self.target='current';self.levels=16;self.music=True;self.cache=None;self.cached=[];self.cancelled=False
        from painting_choice import read
        self.painting_mode=read(path,expected)
        self.sketch_rows=8;self.outline_key=None;self.outline_lines=[]
    def project(self):
        state=read_attachment(self.path)
        if identity(state)!=self.expected:raise ValueError('Attachment changed')
        remote=state.get('project_fd')
        if type(remote) is not int or remote<0:raise ValueError('Missing project')
        fd=os.open(f"/proc/{state['owner']['pid']}/fd/{remote}",os.O_RDONLY|os.O_DIRECTORY)
        try:
            fresh=read_attachment(self.path)
            if identity(fresh)!=self.expected or fresh.get('project_fd')!=remote:raise ValueError('Attachment changed')
        except BaseException:os.close(fd);raise
        return fd,remote
    def scan(self):
        fd,_=self.project()
        try:
            self.own=latest(fd)
            self.library=collect(fd,self.since if self.scope=='session' else 0)
            self.has_any=bool(self.own or self.library) or has_paintings(fd)
        except ValueError as error:
            self.message=str(error);self.next_scan=time.monotonic()+2;return False
        finally:os.close(fd)
        self.next_scan=time.monotonic()+2
        return True
    def items(self):return self.library if self.scope=='all' else [p for p in self.library if p['at']>=self.since]
    def current(self,now):return self.story.frame(now) if self.story.active else (self.own,1)
    def action(self,action,now=None):
        now=time.monotonic() if now is None else now
        if action=='painting_mode':
            from painting_choice import write
            mode='work' if self.painting_mode=='free' else 'free'
            write(self.path,self.expected,mode);self.painting_mode=mode
        elif action=='story':self.menu='scope';self.message='Story: choose paintings'
        elif action in ('session','all'):
            self.scope=action
            if not self.scan():return
            self.story.start(self.items(),now);self.menu=None
            self.message='' if self.story.active else 'No paintings in this session; choose All saved'
        elif action=='pause':
            if self.story.finished:self.story.again(now)
            else:self.story.pause(now)
        elif action=='next':self.story.next(now)
        elif action=='prev':self.story.next(now,-1)
        elif action=='end':self.story.end();self.menu=None;self.message=''
        elif action=='convert':self.menu='target';self.message='Convert: 0 model tokens'
        elif action in ('current','selected'):
            self.target=action;self.menu='way';self.message='Choose rendering: 0 model tokens'
        elif action in ('truest','faithful','both'):
            self.way=action;self.menu='size';self.message='Choose output size'
        elif action=='levels':
            choices=(16,32,64,256,6,8);self.levels=choices[(choices.index(self.levels)+1)%len(choices)]
        elif action in ('hd','4k'):self.start_job('convert',width=1920 if action=='hd' else 3840)
        elif action=='roll':
            self.scan();self.menu='rollscope';self.message='Roll: choose paintings'
        elif action in ('rollsession','rollall'):
            self.scope='session' if action=='rollsession' else 'all'
            if not self.scan():return
            self.menu='rollsize';self.roll_summary()
        elif action=='music':self.music=not self.music;self.roll_summary()
        elif action in ('720p','1080p','short','confirmshort'):
            from painting_music import score
            if action=='short' and score(self.items())['duration']>180:
                self.menu='confirmshort';self.message='Over 3 minutes: make portrait roll anyway?'
            else:self.start_job('roll',size='short' if action=='confirmshort' else action)
        elif action=='cancel':
            if self.job and self.job.poll() is None:
                self.cancelled=True;os.killpg(self.job.pid,signal.SIGTERM);self.cancel_at=now
                self.message='Cancelling export'
        elif action=='back':self.menu=None;self.message=''
    def roll_summary(self):
        from painting_music import score
        n=len(self.items());seconds=round(score(self.items())['duration'])
        self.message=f'{n} paintings | {seconds//60}:{seconds%60:02d} | '+('music' if self.music else 'silent')
    def start_job(self,kind,**options):
        if self.job and self.job.poll() is None:self.message='An export is already running';return
        current,_=self.current(time.monotonic());items=[current] if kind=='convert' and self.target=='current' and current else self.items()
        if not 1<=len(items)<=60:self.message='Choose 1–60 paintings; All saved includes older work';return
        import importlib.util,shutil
        if importlib.util.find_spec('PIL') is None:self.message='Exports need python3-pil (Pillow)';return
        if kind=='roll' and not shutil.which('ffmpeg'):self.message='Rolls need ffmpeg installed';return
        try:
            fd,remote=self.project()
            try:
                req=dict(kind=kind,paintings=items,cols=max(8,self.width-2),levels=self.levels,way=self.way,music=self.music,source_rows=max(3,self.rows-4),
                         attachment=str(self.path),binding=self.expected,remote=remote,**options)
                # File descriptor request avoids blocking the controller on a large stdin payload.
                with os.fdopen(os.memfd_create('keeper-export-request',os.MFD_CLOEXEC),'w+b') as request:
                    request.write(json.dumps(req).encode()+b'\n');request.seek(0)
                    self.job=subprocess.Popen([sys.executable,'-B',str(Path(__file__).with_name('painting_export.py')),str(fd)],
                        stdin=request,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,pass_fds=(fd,),start_new_session=True)
                os.set_blocking(self.job.stdout.fileno(),False)
            finally:os.close(fd)
        except OSError:self.message='Could not start export';return
        self.status={'fraction':0,'label':'Preparing '+kind};self.jobbuf=b'';self.menu=None;self.message='';self.cancelled=False;self.cancel_at=None
    def poll_job(self):
        if not self.job:return
        if self.cancel_at and time.monotonic()-self.cancel_at>2 and self.job.poll() is None:os.killpg(self.job.pid,signal.SIGKILL)
        try:
            chunk=os.read(self.job.stdout.fileno(),65536)
            if chunk:self.jobbuf+=chunk
            while b'\n' in self.jobbuf:
                line,self.jobbuf=self.jobbuf.split(b'\n',1);self.status=json.loads(line)
        except BlockingIOError:pass
        if self.job.poll() is not None:
            if self.cancelled or not self.menu:self.message=''
            if self.cancelled:self.status=dict(fraction=0,label='Cancelled',cancelled=True)
            elif not self.status or self.status.get('fraction')!=1:self.status=dict(fraction=0,label='Export failed',error=True)
            self.job.stdout.close();self.job=None;self.cancel_at=None
    def close(self):
        if self.job and self.job.poll() is None:
            os.killpg(self.job.pid,signal.SIGTERM)
            try:self.job.wait(timeout=2)
            except subprocess.TimeoutExpired:os.killpg(self.job.pid,signal.SIGKILL);self.job.wait()
            self.job.stdout.close()
    def draw(self,now):
        self.poll_job()
        if now>=self.next_scan and not self.job:self.scan()
        p,reveal=self.current(now)
        if not p and not self.library and not self.has_any and not self.menu and not self.status:
            line,hits=buttons([('Work' if self.painting_mode=='work' else 'Free','painting_mode')],self.width,0)
            return dict(lines=[line],sketch=[],hits=hits,busy=bool(self.job),size=[self.width,self.rows])
        lines=[];hits=[]
        def row(items):
            line,h=buttons(items,self.width,len(lines));lines.append(line);hits.extend(h)
        row([('Story','story'),('Convert','convert'),('Roll','roll'),('Work' if self.painting_mode=='work' else 'Free','painting_mode')])
        if self.status and (self.job or (self.status.get('fraction')==1 and not self.message and not self.menu)):
            available=max(6,self.width-(10 if self.job else 0))
            label=self.status['label'][:max(0,available-28)]
            text=(label+' '+progress(self.status['fraction'],max(10,available-len(label)),self.unicode))[:available]
            start=len(text)+1
            lines.append((text+(' [Cancel]' if self.job else ''))[:self.width].ljust(self.width))
            if self.job:hits.append(dict(x0=start,x1=min(self.width,start+8),y=1,action='cancel'))
        else:
            text=self.message or (self.status['label'] if self.status else '')
            if not text and self.story.active:text=f'Story {self.story.index+1}/{len(self.story.items)} | '+('all saved' if self.scope=='all' else 'session')
            if text or self.menu:lines.append(text.encode('ascii','replace').decode()[:self.width].ljust(self.width))
        if self.menu:
            menus={'scope':[('Session','session'),('All saved','all'),('Back','back')],
                   'target':[('This picture','current'),('All selected','selected'),('Back','back')],
                   'way':[('Truest','truest'),('Faithful','faithful'),('Both','both'),('Back','back')],
                   'size':[('HD','hd'),('4K','4k'),(str(self.levels)+' levels','levels'),('Back','back')],
                   'rollscope':[('Session','rollsession'),('All saved','rollall'),('Back','back')],
                   'rollsize':[('720p','720p'),('1080p','1080p'),('Short','short'),('Music' if self.music else 'Silent','music'),('Back','back')],
                   'confirmshort':[('Make anyway','confirmshort'),('Back','back')]}
            row(menus[self.menu])
        remaining=max(3,self.rows-4)
        if p:
            # Quantize reveal at twelve frames/second; same cache during holds.
            reveal=round(reveal*28)/28
            key=(json.dumps(p,sort_keys=True),self.width,remaining,reveal)
            if key!=self.cache:self.cached=canvas(p,self.width,remaining,self.colour,self.unicode,reveal);self.cache=key
            lines+=self.cached
        else:lines+=[' '*self.width]*remaining
        if self.story.active:
            row([('Again' if self.story.finished else 'Play' if self.story.paused_at is not None else 'Pause','pause'),('Prev','prev'),('Next','next'),('End','end')])
        from painting_outline import outline
        outline_key=(json.dumps(self.own,sort_keys=True),self.width,self.sketch_rows,self.colour,self.unicode)
        if outline_key!=self.outline_key:
            self.outline_lines=outline(self.own,self.width,self.sketch_rows,self.colour,self.unicode) if self.own else []
            self.outline_key=outline_key
        return dict(sketch=self.outline_lines,lines=lines[:self.rows],hits=hits,size=[self.width,self.rows],busy=bool(self.job) or (self.story.active and self.story.paused_at is None and not self.story.finished))


def run(path,expected,width,rows,colour,unicode):
    panel=Panel(path,expected,width,rows,colour,unicode);pending=b'';last=None
    def stop(_s,_f):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,stop)
    # If the owning terminal dies unexpectedly, stop this worker and its job.
    import ctypes
    ctypes.CDLL(None).prctl(1,signal.SIGTERM)
    os.set_blocking(sys.stdin.fileno(),False)
    try:
        while True:
            if identity(read_attachment(path))!=expected:return
            if select.select([sys.stdin],[],[],0)[0]:
                data=os.read(sys.stdin.fileno(),65536)
                if not data:return
                pending+=data
                if len(pending)>65536:return
                while b'\n' in pending:
                    line,pending=pending.split(b'\n',1);req=json.loads(line)
                    if 'resize' in req:panel.width,panel.rows=req['resize'];panel.cache=None
                    if 'sketch_rows' in req:panel.sketch_rows=max(6,min(24,int(req['sketch_rows'])))
                    if 'action' in req:panel.action(req['action'])
            frame=panel.draw(time.monotonic())
            if identity(read_attachment(path))!=expected:return
            encoded=json.dumps(frame)
            if encoded!=last:print(encoded,flush=True);last=encoded
            time.sleep(.06 if frame['busy'] else .15)
    except (KeyboardInterrupt,BrokenPipeError):pass
    finally:panel.close()
