import json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'plugins/cyclops-keeper/scripts'))
from test_painting_store import sample
import terminal,expression
from painting_outline import outline

class Sketch(unittest.TestCase):
 def test_outline_is_deterministic_read_only_and_shape_aware(self):
  for shape in ('wide','square','tall'):
   p=sample();p['shape']=shape;p['mirror']='xy';before=json.dumps(p)
   lines=outline(p,70,12,False)
   self.assertEqual(len(lines),12);self.assertEqual(set(map(len,lines)),{70})
   self.assertTrue(any(any(0x2800<ord(c)<=0x28ff for c in row) for row in lines))
   self.assertEqual(lines,outline(p,70,12,False));self.assertEqual(json.dumps(p),before)
 def test_live_sketch_overrides_fallback_without_heading(self):
  options=dict(painting_lines=['P'*70]*20,sketch_lines=['F'*70]*10)
  fresh=terminal.render('idle',70,52,**options)
  self.assertIn('F'*70,fresh);self.assertNotIn('Keeper / draw box',fresh)
  captioned=terminal.render('idle',70,52,expression={'caption':'A small greeting'},**options)
  self.assertIn('F'*70,captioned);self.assertIn('A small greeting',captioned)
  live=terminal.render('idle',70,52,expression={'strokes':[{'ink':'aqua','points':[[0,0],[1,1]]}]},**options)
  self.assertNotIn('F'*70,live);self.assertNotIn('Keeper / authored',live)
  self.assertEqual(len(fresh.splitlines()),52);self.assertEqual(len(live.splitlines()),52)
 def test_preferences_are_bound_and_reject_bad_values(self):
  import painting_choice as choice
  from launcher_link import atomic
  expected={'owner':{},'session':'a','generation':1}
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'attachment.json'
   with patch.object(choice,'read_attachment',return_value=expected):
    choice.write(path,expected,'work')
    self.assertEqual(choice.read(path,expected),'work')
    self.assertEqual(choice.read(path,{**expected,'generation':2}),'free')
    with self.assertRaises(ValueError):choice.write(path,expected,'private text')
   with patch.object(choice,'read_attachment',return_value={**expected,'generation':2}):
    with self.assertRaises(ValueError):choice.write(path,expected,'free')
   file=path.parent/choice.FILENAME;file.unlink();file.symlink_to(path)
   self.assertEqual(choice.read(path,expected),'free')
 def test_mcp_brief_returns_only_fixed_mode_guidance(self):
  import painting_mcp,painting_choice
  with patch.object(expression,'binding',return_value=(Path('/unused/attachment.json'),{'owner':{},'session':'a','generation':1})),patch.object(painting_choice,'read',return_value='work'):
   result=json.loads(painting_mcp.call('painting_brief',{}))
   self.assertEqual(result['mode'],'work');self.assertEqual(set(result),{'mode','guidance'})

 def test_empty_project_still_offers_painting_choice(self):
  from painting_panel import Panel
  import launcher_link
  with tempfile.TemporaryDirectory() as tmp:
   panel=Panel(Path(tmp)/'attachment.json',{'owner':launcher_link.process_identity(os.getpid()),'session':'a','generation':1},70,24,False,True)
   panel.next_scan=float('inf')
   frame=panel.draw(0)
   self.assertEqual(len(frame['lines']),1);self.assertIn('[Free]',frame['lines'][0])
   self.assertEqual(frame['hits'][0]['action'],'painting_mode')
