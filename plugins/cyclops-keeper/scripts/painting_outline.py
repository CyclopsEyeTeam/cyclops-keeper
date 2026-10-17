"""Read-only line-art interpretation of saved marks; rendered in the painting worker."""
import math,time
from painting_raster import painting_scene
from terminal_art import Surface,THEMES

def outline(painting,width,rows,colour=True,unicode=True):
    # This is an outline interpretation, not another authored painting.
    columns=min(160,width);surface=Surface(columns,rows)
    aspect={'wide':2,'square':1,'tall':.5}[painting['shape']]
    h=min(rows*4-2,(columns*2-8)/aspect);w=h*aspect
    scale=min(w,h)/2.4
    ox,oy=columns,rows*2
    palette=THEMES['moonlight'];last=time.monotonic()
    for mark in painting_scene(painting,w,h):
        if time.monotonic()-last>=.018:time.sleep(.001);last=time.monotonic()
        if mark['a']<=.002 or mark['k']=='glow':continue
        rgb=mark.get('c',mark.get('c0'))
        role=min(range(len(palette)),key=lambda i:sum((palette[i][c]/255-rgb[c])**2 for c in range(3)))
        def project(point):return (ox+point[0]*scale,oy+point[1]*scale)
        kind=mark['k']
        if kind in ('path','poly'):
            points=[project(p) for p in mark['pts']]
            if kind=='poly':points.append(points[0])
            for a,b in zip(points,points[1:]):surface.line(a,b,role)
        else:
            centre=project((mark['x'],mark['y']));radius=mark['r']*scale
            if mark.get('is_spray'):surface.point(*centre,role)
            else:surface.ellipse(centre,radius,radius,role,1,start=mark.get('a0',0),end=mark.get('a1',math.tau))
    lines=surface.frame('',unicode=unicode,colour=colour,truecolour=True,theme='moonlight').splitlines()[:rows]
    pad=(width-columns)//2
    return [' '*pad+line+' '*(width-columns-pad) for line in lines]
