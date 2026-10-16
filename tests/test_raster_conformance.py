import json,hashlib,sys,unittest
from unittest import mock
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'plugins/cyclops-keeper/scripts'));import terminal,terminal_art
class RasterConformance(unittest.TestCase):
 def test_all_expression_sizes_events_controls_and_phases_match_previous(self):
  cases=json.loads((ROOT/'tests/fixtures/performance-preserved-frames.json').read_text())['cases'];self.assertEqual(len(cases),320)
  for case in cases:
   with self.subTest(state=case['record']['state'],size=case['size'],options=case['options']):
    got=terminal.render(case['record'],*case['size'],lively=False,**case['options']);self.assertEqual(hashlib.sha256(got.encode()).hexdigest(),case['sha256'])
 def test_rounding_dash_priority_and_clipping_are_preserved(self):
  surface=terminal_art.Surface(4,3)
  surface.line((-.5,.5),(7.5,10.5),4,1)
  surface.line((7.5,10.5),(-.5,.5),8,2,dash=1.3)
  surface.line((-.5,.5),(7.5,10.5),2,0)
  self.assertEqual(hashlib.sha256(surface.frame('state',colour=True,truecolour=True).encode()).hexdigest(),'2694e7af60b5a0acc3b9910807ea140223d00a0728619ba75b64963a6e3e724f')
 def test_curve_rasterizes_without_per_segment_line_dispatch(self):
  surface=terminal_art.Surface(80,30)
  with mock.patch.object(surface,'line',side_effect=AssertionError('curve dispatched each segment')):
   surface.curve([(-60,-20),(-10,40),(40,-30),(120,80)],role=4,priority=2)
 def test_ellipse_rasterizes_without_per_segment_line_dispatch(self):
  surface=terminal_art.Surface(80,30)
  with mock.patch.object(surface,'line',side_effect=AssertionError('ellipse dispatched each segment')):
   surface.ellipse((40,15),18,9,role=4,priority=2)
