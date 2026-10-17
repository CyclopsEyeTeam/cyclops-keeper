"""Deterministic exports, isolated from terminal input and atomically published."""
import base64,ctypes,errno,html,io,json,math,os,secrets,shutil,signal,stat,subprocess,sys,tempfile,time
from contextlib import contextmanager
from pathlib import Path
import painting_store as store

class Cancelled(Exception):pass

def cancelled(_sig,_frame):raise Cancelled()

def credit(p,way=''):
    return p['by'].title()+' | '+time.strftime('%d %b %Y',time.localtime(p['at']))+(' | '+way if way else '')

@contextmanager
def destination(project,kind,guard=lambda:None):
    with store.folder(project,'keeper',create=True) as parent:
        name='.keeper-export-'+secrets.token_hex(8);os.mkdir(name,0o700,dir_fd=parent)
        fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
        target=None
        parent_info=os.fstat(parent);stage_info=os.fstat(fd)
        def matches(info,expected):return stat.S_ISDIR(info.st_mode) and (info.st_dev,info.st_ino)==(expected.st_dev,expected.st_ino)
        try:
            path=Path('/proc/self/fd')/str(fd)
            def publish():
                nonlocal target
                guard()
                if not matches(os.stat('keeper-paintings',dir_fd=project,follow_symlinks=False),parent_info):raise ValueError('Painting folder changed')
                if not matches(os.stat(name,dir_fd=parent,follow_symlinks=False),stage_info):raise ValueError('Export staging changed')
                os.fsync(fd)
                final=kind+'-'+time.strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(4)
                libc=ctypes.CDLL(None,use_errno=True)
                if libc.renameat2(parent,name.encode(),parent,final.encode(),1)!=0:
                    raise OSError(ctypes.get_errno(),'Exclusive export publication failed')
                target=final
                os.fsync(parent);return target
            yield path,publish
        finally:
            os.close(fd)
            if target is None:
                try:
                    if matches(os.stat(name,dir_fd=parent,follow_symlinks=False),stage_info):shutil.rmtree(Path('/proc/self/fd')/str(parent)/name)
                except FileNotFoundError:pass


def write_new(path,data):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())


def source_columns(p,cols,rows):
    if rows is None:return cols
    aspect={'wide':2,'square':1,'tall':.5}[p.get('shape','wide')]
    h=max(2,min((rows-2)*2,int(min(cols,160)/aspect)));h-=h%2
    return max(1,min(cols,160,int(h*aspect)))


def raster(p,width,way='faithful',cols=60,levels=256,reveal=1,work_limit=512):
    from PIL import Image
    from painting_raster import painting_scene,rasterize_scene,tonemap_light
    aspect={'wide':2,'square':1,'tall':.5}[p.get('shape','wide')]
    w=min(width,work_limit);h=max(2,round(w/aspect))
    unit=w/max(1,cols) if way=='truest' else w/width
    px=rasterize_scene(painting_scene(p,w,h,reveal),w,h,min_r_px=.6*unit,min_hw_px=.45*unit)
    buf=bytearray(w*h*3)
    for i,cell in enumerate(px):
        a=min(1,cell[3]);rgb=tonemap_light(*cell[:3])
        for j,(v,b) in enumerate(zip(rgb,(.078,.071,.094))):
            channel=max(0,min(1,v+b*(1-a)))
            buf[i*3+j]=round(channel*255)
        if i%4096==0:time.sleep(.001)
    image=Image.frombytes('RGB',(w,h),bytes(buf));target=(width,round(width/aspect))
    image=image.resize(target,Image.Resampling.BICUBIC) if image.size!=target else image
    if way=='truest':image=image.point([round(round(v/255*(levels-1))/(levels-1)*255) for v in range(256)]*3)
    return image


def caption_image(p,image,way):
    from PIL import Image,ImageDraw,ImageFont
    margin=max(30,round(image.width*.07));out=Image.new('RGB',(image.width,image.height+margin),(20,18,24));out.paste(image,(0,0))
    draw=ImageDraw.Draw(out);size=max(10,round(image.width*.015))
    try:font=ImageFont.truetype('DejaVuSans.ttf',size)
    except OSError:font=ImageFont.load_default()
    # Fit potentially wide titles instead of clipping into another UI/output region.
    for i,text in enumerate([p['title'],credit(p,way)]):
        while draw.textlength(text,font=font)>image.width-8 and len(text)>1:text=text[:-2]
        draw.text((image.width/2,image.height+3+i*(margin//2)),text,font=font,anchor='mt',fill=(220,219,235))
    return out


def svg_image(p,art,way,levels):
    """Raster-backed painting group with sRGB stepping; native caption outside."""
    margin=max(30,round(art.width*.07));height=art.height+margin
    size=max(10,round(art.width*.015));defs='';effect=''
    if way=='truest' and levels<256:
        table=' '.join(format(math.ceil(k/2)/(levels-1),'.12g') for k in range(2*(levels-1)))
        funcs=''.join(f'<feFunc{channel} type="discrete" tableValues="{table}"/>' for channel in 'RGB')
        defs=f'<defs><filter id="levels" color-interpolation-filters="sRGB"><feComponentTransfer>{funcs}</feComponentTransfer></filter></defs>'
        effect=' filter="url(#levels)"'
    data=io.BytesIO();art.save(data,format='PNG')
    image=base64.b64encode(data.getvalue()).decode()
    text=''.join(f'<text x="{art.width/2}" y="{art.height+3+i*(margin//2)}" dominant-baseline="hanging" text-anchor="middle" font-family="DejaVu Sans,sans-serif" font-size="{size}" fill="#dcdbeb">{html.escape(label)}</text>' for i,label in enumerate((p['title'],credit(p,way))))
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{art.width}" height="{height}" viewBox="0 0 {art.width} {height}"><title>{html.escape(p["title"])}</title><desc>{html.escape(credit(p,way))}; raster-backed painting with native caption</desc>{defs}<g{effect}><image width="{art.width}" height="{art.height}" href="data:image/png;base64,{image}"/></g><rect y="{art.height}" width="{art.width}" height="{margin}" fill="#141218"/>{text}</svg>'


def convert(project,paintings,way='truest',width=1920,cols=60,levels=16,report=lambda _:None,guard=lambda:None,source_rows=None):
    if not 1<=len(paintings)<=60:raise ValueError('Choose between 1 and 60 paintings')
    ways=['truest','faithful'] if way=='both' else [way]
    if any(w not in ('truest','faithful') for w in ways) or levels not in (6,8,16,32,64,256):raise ValueError('Unsupported conversion')
    with destination(project,'convert',guard) as (folder,publish):
        cards=[];total=len(paintings)*len(ways);done=0
        for i,p in enumerate(paintings):
            store.validate(p,p['by'],reading=True)
            for variant in ways:
                report(dict(fraction=done/total*.95,label='Drawing '+str(done+1)+'/'+str(total)))
                art=raster(p,width,variant,source_columns(p,cols,source_rows),levels)
                image=caption_image(p,art,variant)
                stem=f'{i+1:02d}-{p["by"]}'+('-'+variant if len(ways)>1 else '')
                data=io.BytesIO();image.save(data,format='PNG');png=data.getvalue();write_new(folder/(stem+'.png'),png)
                svg=svg_image(p,art,variant,levels)
                write_new(folder/(stem+'.svg'),svg.encode())
                cards.append(f'<figure><a href="{stem}.png"><img src="{stem}.png" alt="{html.escape(p["title"],quote=True)}"></a><figcaption>{html.escape(p["title"])} — {html.escape(credit(p,variant))} · <a href="{stem}.svg">SVG (raster-backed)</a></figcaption></figure>')
                done+=1;report(dict(fraction=done/total*.95,label='Rendered '+str(done)+'/'+str(total)))
        gallery='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Keeper painting gallery</title><style>body{background:#141218;color:#eee;font:18px system-ui;max-width:1100px;margin:2em auto}img{max-width:100%}a{color:#aee}</style><h1>Painting gallery</h1>'+''.join(cards)
        write_new(folder/'index.html',gallery.encode());name=publish()
    report(dict(fraction=1,label='Saved '+name,output=name));return name


@contextmanager
def scratch():
    mount=Path('/mnt/e0c1f9cf-dfe9-4135-9aa1-9697141a36d9')
    result=subprocess.run(['findmnt','-no','UUID','--target',str(mount)],capture_output=True,text=True,check=True)
    if result.stdout.strip()!='e0c1f9cf-dfe9-4135-9aa1-9697141a36d9':raise ValueError('Painting scratch HDD is unavailable')
    root=mount/'CyclopsScratch/Codex';root.mkdir(exist_ok=True)
    if shutil.disk_usage(root).free<512*1024**2:raise ValueError('Painting scratch needs 512 MiB free')
    with tempfile.TemporaryDirectory(prefix='keeper-roll-job-',dir=root) as tmp:yield Path(tmp)


def roll(project,paintings,size='720p',music=True,cols=60,levels=16,report=lambda _:None,guard=lambda:None,test_width=None,source_rows=None):
    from PIL import Image,ImageDraw,ImageFont
    from painting_music import score,write_music
    if not 1<=len(paintings)<=60:raise ValueError('Choose between 1 and 60 paintings')
    if levels not in (6,8,16,32,64,256):raise ValueError('Unsupported levels')
    if size not in ('720p','1080p','short'):raise ValueError('Invalid roll size')
    if not shutil.which('ffmpeg'):raise ValueError('ffmpeg is required for rolls')
    plan=score(paintings);width,height={'720p':(1280,720),'1080p':(1920,1080),'short':(1080,1920)}[size]
    if test_width:width,height=test_width,test_width*9//16
    with scratch() as tmp,destination(project,'roll',guard) as (folder,publish):
        if music:write_music(tmp/'music.wav',plan,lambda f:report(dict(fraction=f*.12,label='Scoring music')))
        movie=folder/'roll.mp4'
        # ffmpeg receives our already-created private fd, never an output pathname to replace.
        outfd=os.open(movie,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        args=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}','-r','12','-i','pipe:0']
        if music:args+=['-i',str(tmp/'music.wav'),'-c:a','aac','-b:a','128k']
        args+=['-vf','fps=30','-c:v','libx264','-threads','2','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-t',str(plan['duration']),'-f','mp4','-movflags','frag_keyframe+empty_moov','pipe:'+str(outfd)]
        proc=subprocess.Popen(args,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,pass_fds=(outfd,));os.close(outfd)
        fps=12;frames=math.ceil(plan['duration']*fps);cache={};previous=None
        def frame(p,reveal):
            # A small scene buffer becomes a smoothly scaled video frame. Cache only one painting's reveal frames.
            art_w=int(width*.88);aspect={'wide':2,'square':1,'tall':.5}[p.get('shape','wide')]
            art_w=min(art_w,int(height*.76*aspect))
            art=raster(p,max(16,art_w),'truest',source_columns(p,cols,source_rows),levels,reveal,work_limit=192)
            out=Image.new('RGB',(width,height),(20,18,24));x=(width-art.width)//2;y=max(0,(height-art.height)//2-int(height*.04));out.paste(art,(x,y))
            draw=ImageDraw.Draw(out)
            try:font=ImageFont.truetype('DejaVuSans.ttf',max(10,width//45))
            except OSError:font=ImageFont.load_default()
            title=p['title']
            while draw.textlength(title,font=font)>width-12 and len(title)>1:title=title[:-2]
            draw.text((width//2,min(height-35,y+art.height+6)),title,anchor='mt',font=font,fill=(235,229,241))
            draw.text((width//2,min(height-18,y+art.height+width//28)),credit(p),anchor='mt',font=font,fill=(165,185,211))
            return out
        title=Image.new('RGB',(width,height),(20,18,24));draw=ImageDraw.Draw(title)
        cx,cy=width/2,height*.38;radius=min(width,height)*.1
        draw.ellipse((cx-radius,cy-radius*.55,cx+radius,cy+radius*.55),outline=(155,188,230),width=max(1,width//300));draw.ellipse((cx-radius*.2,cy-radius*.2,cx+radius*.2,cy+radius*.2),fill=(235,202,142))
        text='Keeper | '+str(len(paintings))+' paintings'
        draw.text((width//2,int(height*.6)),text,anchor='mm',fill=(220,220,235))
        draw.text((width//2,int(height*.67)),('music: '+['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B'][plan['root']]+' '+plan['mode']) if music else 'silent roll',anchor='mm',fill=(150,180,220))
        try:
            for f in range(frames):
                at=f/fps
                if at<2:im=title
                else:
                    i=max(j for j,start in enumerate(plan['starts']) if start<=at)
                    if previous!=i:
                        prev=frame(paintings[i-1],1) if i else title
                        cache.clear();previous=i
                    elapsed=at-plan['starts'][i];q=min(24,int(elapsed*12));key=q
                    if key not in cache:
                        cache.clear();cache[key]=frame(paintings[i],min(1,q/24))
                    im=cache[key]
                    if elapsed<.6:im=Image.blend(prev,im,elapsed/.6)
                proc.stdin.write(im.tobytes())
                report(dict(fraction=.12+.84*(f+1)/frames,label='Making roll '+str(f+1)+'/'+str(frames)))
            proc.stdin.close();error=proc.stderr.read(8192);code=proc.wait(timeout=60)
            if code:raise ValueError('Video encoder failed')
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:proc.wait(timeout=2)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
            proc.stderr.close()
        write_new(folder/'index.html',b'<!doctype html><meta charset="utf-8"><title>Keeper roll</title><video controls style="max-width:100%" src="roll.mp4"></video>')
        name=publish()
    report(dict(fraction=1,label='Saved '+name,output=name));return name


def main():
    signal.signal(signal.SIGTERM,cancelled)
    req=json.loads(sys.stdin.buffer.readline(16*1024*1024));project=int(sys.argv[1])
    from launcher_link import read_attachment
    from expression import identity
    def guard():
        fresh=read_attachment(req['attachment'])
        if identity(fresh)!=req['binding'] or fresh.get('project_fd')!=req['remote']:raise ValueError('Attachment changed')
    last=0
    def report(data):
        nonlocal last
        now=time.monotonic()
        if data['fraction']>=1 or now-last>=.2:print(json.dumps(data),flush=True);last=now
    try:
        guard()
        common=dict(project=project,paintings=req['paintings'],cols=req['cols'],levels=req['levels'],source_rows=req.get('source_rows'),report=report,guard=guard)
        if req['kind']=='convert':convert(**common,way=req['way'],width=req['width'])
        else:roll(**common,size=req['size'],music=req['music'])
    except Cancelled:print(json.dumps(dict(fraction=0,label='Cancelled',cancelled=True)),flush=True)
    except (OSError,ValueError,ImportError,subprocess.SubprocessError):print(json.dumps(dict(fraction=0,label='Export failed; check dependencies, disk and attachment',error=True)),flush=True);return 1
    return 0

if __name__=='__main__':sys.exit(main())
