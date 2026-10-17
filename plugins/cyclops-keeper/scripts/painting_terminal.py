"""Read-only overhead painting; raster work lives in a disposable child process."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


def panel_rows(width, height):
    return min(52, max(0, height-18), max(12, (width-2)//4+6), height//2) if width >= 32 and height >= 32 else 0


def latest(project):
    import painting_store as store
    try:
        with store.folder(project, 'keeper') as fd:
            names = [n for n in store.entries(fd) if re.fullmatch(r'[0-9]+-.*\.json', n)]
            for name in sorted(names, key=lambda n: int(n.split('-', 1)[0]), reverse=True):
                try:
                    return store.load(fd, name, 'keeper')
                except (OSError, ValueError, TypeError, OverflowError):
                    continue
    except (OSError, ValueError):
        pass
    return None


def canvas(painting, width, rows, colour=True, unicode=True, reveal=1):
    from painting_raster import painting_scene, rasterize_scene, tonemap_light
    # Half-blocks contain two pixels; preserve the shared 2:1, 1:1, 1:2 shapes.
    aspect = {'wide': 2, 'square': 1, 'tall': .5}[painting['shape']]
    h = max(2, min((rows - 2) * 2, int(min(width - 2, 160) / aspect)))
    h -= h % 2
    w = max(1, min(width - 2, 160, int(h * aspect)))
    pixels = rasterize_scene(painting_scene(painting, w, h, reveal=reveal), w, h)
    def shade(cell):
        rgb = tonemap_light(*cell[:3]); a = min(1., cell[3])
        return tuple(max(0, min(255, round((v + b * (1-a)) * 255)))
                     for v,b in zip(rgb,(.078,.071,.094)))
    lines=[]
    for y in range(0,h,2):
        line=' ' * ((width-w)//2)
        for x in range(w):
            upper=shade(pixels[y*w+x]);lower=shade(pixels[(y+1)*w+x])
            if colour and unicode:
                line+='\x1b[38;2;%d;%d;%d;48;2;%d;%d;%dm▀'%(*upper,*lower)
            else:
                light=max(pixels[y*w+x][:3]+pixels[(y+1)*w+x][:3])
                line+='*' if light>.6 else '+' if light>.2 else '.' if light>.03 else ' '
        if colour and unicode:line+='\x1b[0m'
        lines.append(line+' '*(width-w-(width-w)//2))
    # Existing terminal cell writer supports one-column glyphs only.
    title=(painting.get('by','keeper').title()+' / '+painting['title'].encode('ascii','replace').decode())[:width].center(width)
    usage=(' | '+format(painting['tokens'],',')+' tokens') if type(painting.get('tokens')) is int else ''
    credit=(painting.get('by','keeper').title()+' | '+time.strftime('%d %b %Y',time.localtime(painting['at']))+usage)[:width].center(width)
    return [title]+lines+[' '*width]*(rows-len(lines)-2)+[credit]


def worker(path, expected, width, rows, colour, unicode):
    from painting_panel import run
    run(path,expected,width,rows,colour,unicode)


class Reader:
    """Nonblocking UI endpoint; rendering, scanning and export jobs stay out of it."""
    def __init__(self):
        self.process=None;self.context=None;self.buffer=b'';self.lines=[];self.retired=[];self.next_retry=0
        self.size=None;self.sketch=[];self.sketch_size=None;self.hits=[];self.busy=False;self.outgoing=b'';self.visible=False
    def reap(self):
        import signal
        remaining=[]
        for process,at in self.retired:
            if process.poll() is None:
                if time.monotonic()-at>3:
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                remaining.append((process,at))
        self.retired=remaining
    def close(self):
        import signal
        if self.process is not None:
            if self.process.poll() is None:
                try:os.killpg(self.process.pid,signal.SIGTERM)
                except ProcessLookupError:pass
            self.process.stdout.close();self.process.stdin.close()
            self.retired.append((self.process,time.monotonic()))
        self.process=None;self.context=None;self.buffer=b'';self.lines=[];self.hits=[];self.busy=False;self.outgoing=b'';self.size=None;self.sketch=[];self.sketch_size=None;self.visible=False
        self.reap()
    def send(self,message):
        if not self.process or self.process.poll() is not None:return False
        data=(json.dumps(message)+'\n').encode()
        if len(self.outgoing)+len(data)>65536:return False
        self.outgoing+=data
        self.flush();return True
    def flush(self):
        if not self.outgoing:return
        try:
            n=os.write(self.process.stdin.fileno(),self.outgoing);self.outgoing=self.outgoing[n:]
        except BlockingIOError:pass
        except (BrokenPipeError,OSError):self.outgoing=b''
    def event(self,event):
        if not self.visible:return False
        action=None
        if event[0]=='click':
            _,x,y=event
            action=next((h['action'] for h in self.hits if h['y']==y and h['x0']<=x<h['x1']),None)
        elif event[0]=='key':
            action={b's':'story',b'v':'convert',b'o':'roll',b' ':'pause',b'n':'next',b'p':'prev',b'e':'end',b'x':'cancel'}.get(event[1])
        return self.send({'action':action}) if action else False
    def load(self,path,session,attachment_identity,width,height,colour,unicode):
        self.reap();rows=panel_rows(width,height)
        context=(str(path),session,json.dumps(attachment_identity,sort_keys=True),colour,unicode)
        if not path or not attachment_identity:self.close();return []
        visible=bool(rows);self.visible=visible
        if not visible and self.process is None:return []
        if context!=self.context:self.close();self.context=context;self.next_retry=0
        self.visible=visible
        if self.process is not None and self.process.poll() is not None:
            self.process.stdout.close();self.process.stdin.close();self.process=None;self.lines=[];self.sketch=[];self.sketch_size=None;self.hits=[];self.buffer=b'';self.outgoing=b''
            self.next_retry=time.monotonic()+1
        if self.process is None:
            if time.monotonic()<self.next_retry:return []
            owner,generation=attachment_identity
            expected={'owner':owner,'generation':generation,'session':session}
            self.process=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),str(path),json.dumps(expected),str(width),str(rows),str(int(colour)),str(int(unicode))],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,close_fds=True,start_new_session=True)
            os.set_blocking(self.process.stdout.fileno(),False);os.set_blocking(self.process.stdin.fileno(),False)
            self.size=(width,rows)
        if visible and self.size!=(width,rows):
            self.size=(width,rows);self.lines=[];self.hits=[];self.send({'resize':[width,rows]})
        self.flush()
        try:
            chunk=os.read(self.process.stdout.fileno(),1048576)
            if chunk:self.buffer+=chunk
            if len(self.buffer)>2097152:self.close();return []
            while b'\n' in self.buffer:
                raw,self.buffer=self.buffer.split(b'\n',1);value=json.loads(raw)
                if value.get('size')!=list(self.size):continue
                lines=value['lines']
                if not isinstance(lines,list) or len(lines)>self.size[1] or not all(isinstance(s,str) for s in lines):continue
                sketch=value.get('sketch',[])
                self.sketch=sketch if isinstance(sketch,list) and len(sketch)<=24 and all(isinstance(s,str) for s in sketch) else []
                self.lines=lines;self.hits=value['hits'];self.busy=value['busy']
        except BlockingIOError:pass
        except (OSError,ValueError,KeyError,TypeError):self.close()
        sketch_rows=min(24,max(6,(height-len(self.lines))//3))
        if visible and sketch_rows!=self.sketch_size:
            self.send({'sketch_rows':sketch_rows});self.sketch_size=sketch_rows
        return self.lines if visible else []


if __name__=='__main__':
    worker(sys.argv[1],json.loads(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4]),bool(int(sys.argv[5])),bool(int(sys.argv[6])))
