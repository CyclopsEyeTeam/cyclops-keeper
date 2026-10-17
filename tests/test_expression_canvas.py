import json
from pathlib import Path
import re
import sys
import unittest
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'plugins/cyclops-keeper/scripts'))
import expression
import presence_mcp
import terminal


class ExpressionCanvas(unittest.TestCase):
    def test_live_crest_moves_but_respects_quiet_modes(self):
        def top(now, **options):
            return terminal.render('working',54,40,crest=True,now=now,
                                   **options).splitlines()[:4]
        self.assertNotEqual(top(1),top(2))
        for options in ({'calm':True},{'reduced_motion':True},{'stale':True},
                        {'lively':False}):
            self.assertEqual(top(1,**options),top(2,**options))
        for now in (0,1,2,3):
            self.assertEqual(set(map(len,top(now))),{54})

    def test_event_panel_is_centered_wide_and_open(self):
        from terminal_art import Surface, _witness_canvas
        surface=Surface(54,60)
        record={'sequence':1,'event_observed':True,
                'transitions':[{'sequence':1,'event':'Stop','at':0}]}
        _witness_canvas(surface,record,body_rows=60,cx=42,cy=40,sx=.2,sy=.2,
                        now=10,calm=False,reduced_motion=False,frozen=False,lively=True)
        occupied=[(r,c) for r,row in enumerate(surface.masks) for c,m in enumerate(row) if m]
        left=min(c for r,c in occupied);right=max(c for r,c in occupied)
        top=min(r for r,c in occupied);bottom=max(r for r,c in occupied)
        self.assertLessEqual(abs(top-(59-bottom)),1)
        self.assertLessEqual(abs(left-(53-right)),1)
        self.assertGreaterEqual(right-left+1,46)
        self.assertLess(sum(m.bit_count() for row in surface.masks for m in row),1000)
        self.assertGreater(len({surface.roles[r][c] for r,c in occupied}),1)
        self.assertTrue(any(0<m<255 for row in surface.masks for m in row))

    def test_crest_keeps_canvas_and_status_and_hides_in_short_panes(self):
        art={'crest':{'motif':'moon','phrase':'A little orbit of light.'},
             'strokes':[{'ink':'gold','points':[[0,0],[1,1]]}]}
        for width,height in [(32,28),(54,36),(100,60)]:
            frame=terminal.render('working',width,height,expression=art,crest=True)
            lines=frame.splitlines()
            self.assertEqual(len(lines),height)
            self.assertEqual(set(map(len,lines)),{width})
            self.assertIn('A little orbit of light.',lines[3])
            self.assertIn('KEEPER',lines[-1])
            start=next(i for i,line in enumerate(lines) if 'Keeper / authored' in line)
            self.assertEqual(height-start-1,min(24,max(6,height*2//5)))
        for size in [(31,36),(54,27)]:
            self.assertEqual(terminal.render('working',*size,crest=True),terminal.render('working',*size))

    def test_crest_alone_does_not_open_empty_bottom_canvas(self):
        frame=terminal.render('idle',54,36,crest=True,
                              expression={'crest':{'motif':'ribbon','phrase':'A quiet fold.'}})
        self.assertIn('A quiet fold.',frame)
        self.assertNotIn('Keeper / authored',frame)
        self.assertEqual(len(frame.splitlines()),36)

    def test_crest_motifs_are_static_and_reject_controls(self):
        for motif in ['constellation','moon','ribbon']:
            value=expression.crest_value({'motif':motif,'phrase':'A quiet fold.'})
            a=expression.crest_lane(json.dumps(value),54,True,True,False,'moonlight')
            self.assertIn('A quiet fold.',a)
            self.assertEqual(a,expression.crest_lane(json.dumps(value),54,True,True,False,'moonlight'))
        for value in [{'motif':'success'},{'motif':'moon','phrase':'bad\x1b'},
                      {'motif':'moon','phrase':'x'*49}]:
            with self.assertRaises(ValueError):expression.crest_value(value)

    def test_larger_lane_preserves_exact_grid_and_status(self):
        art={'strokes':[{'ink':'gold','points':[[0,0],[1,1]]}], 'caption':None}
        for width,height in [(32,18),(80,24),(54,36),(100,60)]:
            frame=terminal.render('working',width,height,expression=art)
            lines=frame.splitlines()
            self.assertEqual(len(lines),height)
            self.assertEqual(set(map(len,lines)),{width})
            self.assertIn('KEEPER',lines[-1])
            start=next(i for i,line in enumerate(lines) if 'Keeper / authored' in line)
            self.assertEqual(height-start-1,min(24,max(6,height*2//5)))

    def test_shapes_labels_and_theme_render_without_escapes_in_plain_mode(self):
        strokes=[{'kind':kind,'ink':'rose','points':points} for kind,points in [
            ('ellipse',[[.1,.1],[.4,.7]]),('rect',[[.5,.1],[.9,.7]]),
            ('curve',[[0,1],[.3,0],[.7,0],[1,1]])]]
        art={'strokes':expression.painting(strokes),
             'labels':expression.labels([{'text':'moon garden','at':[.2,.8],'ink':'chalk'}])}
        plain=expression.lane(json.dumps(art),60,14,True,False,True,False,'moonlight')
        coloured=expression.lane(json.dumps(art),60,14,True,True,True,False,'moonlight')
        self.assertIn('moon garden',plain)
        self.assertEqual(re.sub(r'\x1b\[[0-9;]*m','',coloured),plain)
        self.assertEqual(set(map(len,plain.splitlines())),{60})
        self.assertNotEqual(plain,expression.lane(json.dumps({'labels':art['labels']}),60,14,True,False,True,False,'moonlight'))

    def test_bounded_geometry_and_terminal_safe_labels(self):
        stroke={'ink':'glass','points':[[0,0],[1,1]]}
        self.assertEqual(len(expression.painting([stroke]*32)),32)
        with self.assertRaises(ValueError):expression.painting([stroke]*33)
        dense={'ink':'glass','points':[[0,0]]*48}
        with self.assertRaises(ValueError):expression.painting([dense]*11)
        for kind,points in [('ellipse',[[0,0]]*3),('rect',[[0,0]]*3),('curve',[[0,0]]*3)]:
            with self.assertRaises(ValueError):expression.painting([dict(kind=kind,ink='gold',points=points)])
        for text in ['bad\x1b[2J','bad\ntext','x'*41]:
            with self.assertRaises(ValueError):expression.labels([dict(text=text,at=[0,0],ink='chalk')])
        with self.assertRaises(ValueError):expression.labels([dict(text='x',at=[float('nan'),0],ink='chalk')])

    def test_mcp_exposes_shape_and_label_controls(self):
        tool=next(t for t in presence_mcp.TOOLS if t['name']=='paint')
        props=tool['inputSchema']['properties']
        self.assertIn('labels',props)
        self.assertIn('curve',props['strokes']['items']['properties']['kind']['enum'])

    def test_publish_read_replace_and_clear_preserve_caption_and_binding(self):
        state={'owner':{'pid':123,'start':'fixture'},'session':'a'*64,'generation':1}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'attachment.json'
            with patch.object(expression,'binding',return_value=(path,state)), \
                 patch.object(expression,'read_attachment',return_value=state), \
                 patch.object(expression.time,'time',return_value=100):
                expression.publish('say',{'caption':'A moon garden','seconds':60})
            with patch.object(expression,'binding',return_value=(path,state)), \
                 patch.object(expression,'read_attachment',return_value=state), \
                 patch.object(expression.time,'time',return_value=102):
                expression.publish('paint',{'labels':[{'text':'moon','at':[.1,.2],'ink':'gold'}]})
                reader=expression.Reader()
                value=reader.load(path,state['session'],(state['owner'],1))
                self.assertEqual(value['caption'],'A moon garden')
                self.assertEqual(value['labels'][0]['text'],'moon')
                self.assertIsNone(reader.load(path,state['session'],(state['owner'],2)))
                with patch.object(expression.time,'time',return_value=104):
                    response=presence_mcp.respond({'jsonrpc':'2.0','id':1,'method':'tools/call',
                        'params':{'name':'crest','arguments':{'motif':'moon','phrase':'A quiet orbit.'}}})
                    self.assertNotIn('isError',response['result'])
                    value=expression.Reader().load(path,state['session'],(state['owner'],1))
                    self.assertEqual(value['crest']['phrase'],'A quiet orbit.')
                    self.assertEqual(value['labels'][0]['text'],'moon')
                    self.assertEqual(value['caption'],'A moon garden')
                expression.publish('clear',{})
                self.assertIsNone(expression.Reader().load(path,state['session'],(state['owner'],1)))

    def test_invalid_canvas_is_rejected_before_any_publish(self):
        for args in [{}, {'strokes':[]}, {'labels':[{'text':'\x1b','at':[0,0],'ink':'gold'}]},
                     {'strokes':[{'kind':'curve','ink':'gold','points':[[0,0],[1,1]]}]}]:
            with patch.object(expression,'binding',side_effect=AssertionError('must validate before binding')):
                with self.assertRaises(ValueError):expression.publish('paint',args)

    def test_static_art_is_cached_and_small_panes_keep_original_layout(self):
        value={'labels':[{'text':'quiet','at':[0,0],'ink':'chalk'}]}
        encoded=json.dumps(value)
        expression.lane.cache_clear()
        first=expression.lane(encoded,54,14,True,True,True,False,'moonlight')
        self.assertEqual(first,expression.lane(encoded,54,14,True,True,True,False,'moonlight'))
        self.assertEqual(expression.lane.cache_info().misses,1)
        self.assertEqual(expression.lane.cache_info().hits,1)
        for size in [(31,36),(54,17)]:
            self.assertEqual(terminal.render('working',*size,expression=value),terminal.render('working',*size))
