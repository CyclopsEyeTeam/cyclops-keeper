#!/usr/bin/env python3
"""Explicit local painting interface. Does not launch or control a terminal."""
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import painting_store as store


def preview(p):
    renderer=Path(__file__).with_name('painting_renderer.js').read_text()
    encoded=json.dumps(p,ensure_ascii=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    return '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'">
<title>Keeper painting preview</title><style>
body{margin:0;background:#141218;color:#ede7dd;font:18px system-ui;padding:32px}main{max-width:960px;margin:auto}
canvas{display:block;max-width:100%;height:auto;margin:24px auto;background:#141218}p{line-height:1.5}small{color:#a49baf}
</style><main><small>Keeper · explicit painting preview</small><h1 id="title"></h1><p id="credit"></p>
<canvas id="painting" aria-label="Painting"></canvas><p id="thought"></p><small id="status">Drawing…</small></main><script>'''+renderer+'''
const painting='''+encoded+''';
document.getElementById('title').textContent=painting.title;
document.getElementById('thought').textContent=painting.thought||'';
document.getElementById('credit').textContent=({keeper:'Keeper',spark:'Spark',prism:'Prism'}[painting.by]||'Keeper')+' · '+new Date(painting.at*1000).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'});
const canvas=document.getElementById('painting');const aspect={wide:2,square:1,tall:.5}[painting.shape];
canvas.width=aspect<1?480:960;canvas.height=canvas.width/aspect;
let heartbeat=0;const timer=setInterval(()=>heartbeat++,1);
const ctx=canvas.getContext('2d');ctx.fillStyle='#141218';ctx.fillRect(0,0,canvas.width,canvas.height);
KeeperPainting.paintAsync(ctx,painting,canvas.width,canvas.height).then(stats=>{
 clearInterval(timer);window.previewEvidence={...stats,heartbeat};
 document.getElementById('status').textContent='Saved composition · standalone preview';
 document.body.dataset.complete='true';
});</script></html>'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['validate','save','read','preview'])
    parser.add_argument('--project',default='.')
    parser.add_argument('--owner',choices=store.OWNERS,default='keeper')
    parser.add_argument('--filename')
    parser.add_argument('--privacy-checked',action='store_true',help='Attest title, thought and all text contain no private task or session content')
    args=parser.parse_args()
    try:
        if args.action in ('validate','save'):
            p=store.validate(store.decode(sys.stdin.buffer.read(store.MAX_BYTES+1)))
            if args.action=='validate':result={'valid':True,'marks':len(p['marks'])}
            else:
                if not args.privacy_checked:raise ValueError('Review painting privacy before saving')
                with store.open_project(args.project) as fd:result={'saved':store.save(fd,p)}
        else:
            with store.open_project(args.project) as fd:result=store.read(fd,args.owner,args.filename)
            if args.action=='preview':
                if not args.filename or len(result)!=1:raise ValueError('Choose one valid painting filename')
                print(preview(result[0]['painting']));return 0
        print(json.dumps(result,ensure_ascii=False,allow_nan=False));return 0
    except (ValueError,OSError,TypeError) as error:
        print(json.dumps({'error':'Painting storage unavailable' if isinstance(error,OSError) else str(error)}),file=sys.stderr)
        return 1

if __name__=='__main__':sys.exit(main())
