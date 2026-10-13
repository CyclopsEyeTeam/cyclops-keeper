import importlib.util,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SCRIPTS=ROOT/'plugins/cyclops-keeper/scripts'
sys.path.insert(0,str(SCRIPTS));import terminal,terminal_art
class FrameWork(unittest.TestCase):
 def test_held_dense_frames_cost_less_than_a_quarter_of_native_composition(self):
  import json,time
  from unittest.mock import patch
  record={'state':'branching','sequence':64,
          'active_tools':[{'key':format(i,'064x'),'kind':'execute','sequence':i} for i in range(32)],
          'active_subagents':[{'key':format(i+100,'064x'),'sequence':i} for i in range(32)]}
  paced=terminal.PacedRenderCache();native=terminal.PacedRenderCache(interval=0)
  # The live loop reads a fresh JSON projection each poll. Prepare equivalent
  # independent inputs outside timing so this measures held-frame comparisons.
  snapshots=[json.loads(json.dumps(record)) for _ in range(1000)]
  def cost(cache):
   cache.frame(record,6,1,now=1000)
   start=time.process_time()
   for snapshot in snapshots:cache.frame(snapshot,6,1,now=1000)
   return time.process_time()-start
  with patch.object(terminal.time,'monotonic',return_value=1):
   native_cost=cost(native);paced_cost=cost(paced)
   self.assertLess(paced_cost,native_cost*.25,(paced_cost,native_cost))
   record['state']='interrupted';record['sequence']=65
   self.assertIn('x',paced.frame(record,6,1,now=1000))

 def test_full_surface_does_not_probe_an_empty_override_map_per_cell(self):
  class Empty(dict):
   def get(self,*args):raise AssertionError('empty glyph map probed')
  surface=terminal_art.Surface(100,31);surface.glyphs=Empty();surface.point(20,20)
  self.assertIn(chr(0x2800+1),surface.frame('status'))
 def test_static_body_is_reused_and_real_changes_invalidate_it(self):
  from unittest.mock import patch
  self.assertTrue(hasattr(terminal,'RenderCache'),'bounded static body cache missing')
  cache=terminal.RenderCache()
  with patch.object(terminal,'render',wraps=terminal.render) as draw:
   a=cache.frame('idle',100,32,now=1000,reduced_motion=True)
   self.assertEqual(a,cache.frame('idle',100,32,now=1001,reduced_motion=True));self.assertEqual(draw.call_count,1)
   self.assertNotEqual(a,cache.frame('waiting',100,32,now=1001,reduced_motion=True));self.assertEqual(draw.call_count,2)
   cache.frame('waiting',48,20,now=1001,reduced_motion=True);self.assertEqual(draw.call_count,3)
   cache.frame('waiting',48,20,now=1001,reduced_motion=True,calm=True);self.assertEqual(draw.call_count,4)
   cache.frame('working',100,32,now=1000);cache.frame('working',100,32,now=1000.8);self.assertEqual(draw.call_count,6)

 def test_dynamic_full_and_compact_frames_match_preserved_original(self):
  import json,hashlib
  golden=json.loads((ROOT/'tests/fixtures/responsive-original-frames.json').read_text())
  self.assertEqual(len(golden['cases']),120)
  for case in golden['cases']:
   frame=terminal_art.draw_keeper(case['record'],*case['size'],'status',now=case['now'],colour=case['colour'],truecolour=True)
   self.assertEqual(hashlib.sha256(frame.encode()).hexdigest(),case['sha256'])
