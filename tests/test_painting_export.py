import json,os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'plugins/cyclops-keeper/scripts'))
from test_painting_store import sample

class Exports(unittest.TestCase):
 def test_convert_publishes_png_svg_and_gallery_without_overwrite(self):
  import painting_export as ex
  from PIL import Image
  import painting_store as store
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);events=[]
   with store.open_project(root) as fd:
    first=ex.convert(fd,[sample()],way='truest',width=96,cols=40,levels=16,report=events.append)
    second=ex.convert(fd,[sample()],way='faithful',width=96,cols=40,levels=256,report=events.append)
   self.assertNotEqual(first,second)
   out=root/'keeper-paintings'/first
   self.assertTrue((out/'index.html').exists())
   with Image.open(out/'01-keeper.png') as image:self.assertEqual(image.size,(96,78))
   self.assertIn('image/png;base64',(out/'01-keeper.svg').read_text())
   self.assertIn('Keeper',(out/'index.html').read_text())
   self.assertEqual(events[-1]['fraction'],1)

 def test_symlink_output_refused(self):
  import painting_export as ex
  import painting_store as store
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'elsewhere').mkdir();(root/'keeper-paintings').symlink_to(root/'elsewhere')
   with store.open_project(root) as fd:
    with self.assertRaises(OSError):ex.convert(fd,[sample()],width=32)
   self.assertEqual(list((root/'elsewhere').iterdir()),[])

 def test_roll_schedule_and_music_deterministic(self):
  import painting_music as music
  a=music.score([sample()]);b=music.score([sample()])
  self.assertEqual(a,b);self.assertGreater(a['duration'],6)
  self.assertIn(a['mode'],['major','dorian','aeolian'])
  self.assertTrue(a['events']);self.assertEqual(a['starts'][0],2)

 def test_real_roll_contains_video_and_audio(self):
  import painting_export as ex
  import painting_store as store
  import subprocess
  from unittest.mock import patch
  from contextlib import contextmanager
  @contextmanager
  def isolated_scratch():
   # Test-only intermediates follow TMPDIR (HDD locally, runner scratch in CI).
   # Production export retains its independently verified HDD guard.
   with tempfile.TemporaryDirectory() as directory:yield Path(directory)
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);events=[]
   with patch.object(ex,'scratch',isolated_scratch),store.open_project(root) as fd:
    name=ex.roll(fd,[sample()],test_width=160,report=events.append)
   movie=root/'keeper-paintings'/name/'roll.mp4'
   probe=subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type','-of','json',str(movie)],capture_output=True,text=True,check=True)
   self.assertEqual({s['codec_type'] for s in json.loads(probe.stdout)['streams']},{'video','audio'})
   self.assertEqual(events[-1]['fraction'],1)

 def test_replaced_parent_and_staging_are_not_published(self):
  import painting_export as ex
  import painting_store as store
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   with store.open_project(root) as fd:
    with self.assertRaises(ValueError):
     with ex.destination(fd,'convert') as (stage,publish):
      (root/'keeper-paintings').rename(root/'moved')
      (root/'keeper-paintings').mkdir()
      publish()
    with self.assertRaises(ValueError):
     with ex.destination(fd,'convert') as (stage,publish):
      original=next((root/'keeper-paintings').glob('.keeper-export-*'))
      original.rename(root/'held-stage')
      original.symlink_to(root/'held-stage',target_is_directory=True)
      publish()
   self.assertFalse(any(p.name.startswith('convert-') for p in (root/'keeper-paintings').iterdir()))

class Truest(unittest.TestCase):
 def test_posterization_after_resize_and_caption_outside_svg_filter(self):
  import painting_export as ex
  import xml.etree.ElementTree as ET
  p=sample();p['marks'].append(dict(k='glow',x=.2,y=.3,r=.3,c=[.2,.4,.6],a=.4))
  art=ex.raster(p,180,'truest',40,16,work_limit=64)
  self.assertTrue(all(v%17==0 for v in art.tobytes()))
  captioned=ex.caption_image(p,art,'truest')
  self.assertTrue(any(v%17 for v in captioned.crop((0,art.height,art.width,captioned.height)).tobytes()))
  root=ET.fromstring(ex.svg_image(p,art,'truest',16));ns={'s':'http://www.w3.org/2000/svg'}
  effect=root.find('.//s:filter',ns);self.assertEqual(effect.get('color-interpolation-filters'),'sRGB')
  values=list(map(float,root.find('.//s:feFuncR',ns).get('tableValues').split()))
  self.assertEqual(len(values),30);self.assertEqual(values[0],0);self.assertEqual(values[-1],1)
  group=root.find('s:g',ns);self.assertEqual(group.get('filter'),'url(#levels)')
  self.assertIsNone(group.find('.//s:text',ns));self.assertEqual(len(root.findall('s:text',ns)),2)
  self.assertNotIn('GaussianBlur',ex.svg_image(p,art,'truest',16))
  self.assertNotIn('<filter',ex.svg_image(p,art,'truest',256))
