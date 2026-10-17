import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'plugins/cyclops-keeper/scripts'))
from test_painting_store import sample
import terminal

class OverheadPainting(unittest.TestCase):
    def test_overhead_keeps_expression_and_status_below(self):
        lines=['OVERHEAD'.ljust(60)]*8
        expression={'strokes':[{'ink':'gold','points':[[.1,.1],[.9,.9]],'kind':'line'}]}
        frame=terminal.render('idle',60,48,painting_lines=lines,expression=expression)
        self.assertEqual(len(frame.splitlines()),48)
        self.assertEqual(frame.splitlines()[0],lines[0])
        self.assertNotIn('Keeper / authored',frame)
        self.assertTrue(any(any(0x2800<=ord(c)<=0x28ff for c in row) for row in frame.splitlines()[-10:-1]))
        self.assertIn('KEEPER',frame.splitlines()[-1])
        crest=terminal.render('idle',60,32,painting_lines=lines,crest=True)
        self.assertNotIn('decorative crest',crest)

    def test_overhead_reserves_live_canvas_and_larger_presence(self):
        from unittest.mock import patch
        import painting_terminal as pt
        overhead=['OVERHEAD'.ljust(70)]*pt.panel_rows(70,52)
        with patch.object(terminal,'_render_body',wraps=terminal._render_body) as body:
            frame=terminal.render('working',70,52,painting_lines=overhead,crest=True)
        self.assertNotIn('Keeper / draw box',frame)
        self.assertNotIn('Keeper / authored',frame)
        self.assertGreaterEqual(body.call_args.args[2],17)
        self.assertEqual(body.call_args.kwargs['mode'],'focus')
        self.assertEqual(len(frame.splitlines()),52)
        self.assertEqual(set(map(len,frame.splitlines())),{70})

    def test_reported_tokens_are_shown_without_inventing_unknown_usage(self):
        import painting_terminal as pt
        import painting_store as store
        p=sample();p['tokens']=1234
        result=store.validate(p)
        self.assertIn('1,234 tokens',pt.canvas(result,70,12,False)[-1])
        self.assertEqual(store.validate(p,reading=True)['tokens'],1234)
        p.pop('tokens')
        self.assertNotIn('tokens',pt.canvas(p,70,12,False)[-1])
        for invalid in (-1,True,1.5,'1234'):
            p['tokens']=invalid
            with self.assertRaises(ValueError):store.validate(p)
            self.assertNotIn('tokens',store.validate(p,reading=True))

    def test_small_pane_preserves_original_layout(self):
        self.assertEqual(terminal.render('idle',30,15,painting_lines=['x'*30]*8),terminal.render('idle',30,15))

    def test_saved_canvas_and_safe_latest(self):
        import painting_terminal as pt
        import painting_store as store
        p=sample(); p['shape']='square'
        lines=pt.canvas(p,60,12,True,True)
        self.assertEqual(len(lines),12)
        self.assertTrue(any('38;2;' in line for line in lines))
        self.assertIn(p['title'],'\n'.join(lines))
        from terminal_output import cells
        coloured=[style for row in lines for glyph,style in cells(row,60) if glyph=='▀']
        self.assertTrue(coloured)
        self.assertTrue(all('38;2;' in style and ';48;2;' in style for style in coloured))
        wide=sample('界'*30)
        title=pt.canvas(wide,32,8)[0]
        self.assertEqual(len(title),32)
        self.assertTrue(title.isascii())
        with tempfile.TemporaryDirectory() as tmp:
            with store.open_project(tmp) as fd:
                name=store.save(fd,p)
                folder=Path(tmp)/'keeper-paintings'
                (folder/'999-broken.json').write_text('{}')
                (folder/'998-link.json').symlink_to(folder/name)
                self.assertEqual(pt.latest(fd)['title'],p['title'])

    def test_layout_reserves_keeper(self):
        import painting_terminal as pt
        self.assertEqual(pt.panel_rows(60,20),0)
        self.assertLessEqual(pt.panel_rows(60,48),24)

if __name__=='__main__':unittest.main()

class SharedRaster(unittest.TestCase):
    def test_matches_prism_all_marks_shapes_and_mirrors(self):
        import importlib.util
        import painting_raster as actual
        path=Path(__file__).parent/'fixtures/prism_raster_reference.py'
        spec=importlib.util.spec_from_file_location('prism_reference',path)
        reference=importlib.util.module_from_spec(spec);spec.loader.exec_module(reference)
        marks=[dict(k='line',pts=[[.1,.2],[.9,.8]],w=.03),
               dict(k='curve',pts=[[.1,.2],[.3,.8],[.6,.4],[.9,.8]],w=.03),
               dict(k='fill',pts=[[0,0],[1,0],[.5,1]],grad=.125),
               dict(k='arc',x=.5,y=.5,r=.3,w=.03,a0=.8,a1=.3),
               dict(k='ring',x=.5,y=.5,r=.3,w=.03),
               dict(k='glow',x=.2,y=.4,r=.3),dict(k='dot',x=.2,y=.4,r=.1),
               dict(k='spray',x=.5,y=.5,r=.3,n=20,s=.01,seed=918)]
        for m in marks:m.update(c=[.3,.7,.9],c2=[.9,.3,.4],a=.6)
        for mirror in [None,'x','y','xy']:
            for w,h in [(40,20),(20,40),(20,20)]:
                p=dict(marks=marks,mirror=mirror)
                expected=reference.painting_scene(p,w,h);scene=actual.painting_scene(p,w,h)
                self.assertEqual(scene,expected)
                self.assertEqual(actual.rasterize_scene(scene,w,h),reference.rasterize_scene(expected,w,h))

    def test_real_worker_nonblocking_resize_and_attachment_change(self):
        import time
        import painting_terminal as pt
        import painting_store as store
        import launcher_link as link
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
            reader=pt.Reader()
            try:
                store.save(fd,sample())
                owner=link.process_identity(os.getpid());session='a'*64
                attachment=root/'attachment.json'
                state={'v':1,'owner':owner,'generation':1,'session':session,'project_fd':fd}
                link.atomic(attachment,state)
                context=(owner,1)
                deadline=time.monotonic()+5;lines=[];costs=[]
                while time.monotonic()<deadline and not lines:
                    start=time.monotonic()
                    lines=reader.load(attachment,session,context,60,48,True,True)
                    costs.append(time.monotonic()-start);time.sleep(.01)
                self.assertTrue(lines)
                self.assertLess(max(costs),.1,'UI reader blocked on raster work')
                reader.buffer=b'["partial'
                failed=reader.process;failed.kill();failed.wait(timeout=2)
                self.assertEqual(reader.load(attachment,session,context,60,48,True,True),[])
                self.assertIsNone(reader.process)
                self.assertEqual(reader.buffer,b'')
                reader.next_retry=0
                reader.load(attachment,session,context,60,48,True,True)
                self.assertIsNotNone(reader.process)
                kept=reader.process
                self.assertEqual(reader.load(attachment,session,context,20,15,True,True),[])
                self.assertIs(reader.process,kept)
                self.assertFalse(reader.event(('click',2,0)))
                old=reader.process
                resized=reader.load(attachment,session,context,70,48,True,True)
                self.assertEqual(resized,[])
                self.assertIsNone(old.poll())
                state['generation']=2;link.atomic(attachment,state)
                self.assertEqual(reader.load(attachment,session,(owner,2),70,48,True,True),[])
                self.assertEqual(reader.load(None,None,None,70,48,True,True),[])
            finally:
                reader.close()
                for p,_ in reader.retired:p.wait(timeout=3)
                os.close(fd)
