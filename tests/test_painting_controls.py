import json,os,sys,tempfile,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'plugins/cyclops-keeper/scripts'))
from test_painting_store import sample

class Controls(unittest.TestCase):
 def test_larger_picture_preserves_space(self):
  from painting_terminal import panel_rows,canvas
  self.assertGreaterEqual(panel_rows(72,54),22)
  self.assertLessEqual(panel_rows(72,54),36)
  self.assertEqual(panel_rows(30,20),0)
  rows=canvas(sample(),72,22)
  self.assertGreater(sum('▀' in r for r in rows),12)

 def test_mouse_parser_split_packets_and_escape(self):
  from painting_controls import Input
  p=Input();self.assertEqual(p.feed(b'\x1b[<0;12;',0),[])
  self.assertEqual(p.feed(b'3M',.01),[('click',11,2)])
  self.assertEqual(p.feed(b'\x1b[<0;12;3m',.02),[])
  self.assertEqual(p.feed(b'\x1b[<64;12;3Mq',.03),[('key',b'q')])
  self.assertEqual(p.feed(b'\x1b',.04),[])
  self.assertEqual(p.feed(b'',.15),[('key',b'\x1b')])

 def test_story_pause_resume_end_and_manual_pages(self):
  from painting_controls import Story
  s=Story();items=[sample('First'),sample('Last')]
  s.start(items,0);self.assertEqual(s.frame(1)[0]['title'],'First')
  s.pause(1);self.assertEqual(s.frame(8)[1],s.frame(1)[1])
  s.pause(8);self.assertEqual(s.frame(8)[1],1/2.4)
  s.next(9);self.assertEqual(s.frame(9)[0]['title'],'Last')
  self.assertEqual(s.frame(100)[0]['title'],'Last');self.assertTrue(s.finished)
  s.again(101);self.assertEqual(s.frame(101)[0]['title'],'First')

 def test_progress_final_and_ascii(self):
  from painting_controls import progress
  self.assertIn('100%',progress(1,40))
  self.assertIn('44%',progress(.44,40))
  self.assertTrue(progress(.44,40,False).isascii())

 def test_peers_credit_session_and_read_only(self):
  import painting_controls as pc
  import painting_store as store
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);folder=root/'spark-paintings';folder.mkdir()
   p=sample('Peer');p['by']='keeper';p['at']=200
   path=folder/'01-peer.json';path.write_text(json.dumps(p));before=path.stat().st_mtime_ns
   (folder/'02-link.json').symlink_to(path)
   with store.open_project(root) as fd:
    items=pc.collect(fd,100);self.assertEqual(len(items),1)
    self.assertEqual(items[0]['by'],'spark');self.assertEqual(pc.collect(fd,300),[])
   self.assertEqual(path.stat().st_mtime_ns,before)

 def test_session_filter_does_not_lose_new_entries_after_200(self):
  import painting_controls as pc
  import painting_store as store
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);folder=root/'keeper-paintings';folder.mkdir()
   for i in range(205):
    p=sample('Painting '+str(i));p['at']=1 if i<204 else 1000
    (folder/f'{i:03d}-painting.json').write_text(json.dumps(p))
   with store.open_project(root) as fd:
    self.assertEqual(len(pc.collect(fd)),205)
    self.assertEqual([p['title'] for p in pc.collect(fd,500)],['Painting 204'])

 def test_older_peer_only_project_can_open_all_saved(self):
  from painting_panel import Panel
  import launcher_link as link
  import painting_store as store
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);folder=root/'spark-paintings';folder.mkdir()
   p=sample('Older peer');p['at']=10;p['by']='spark';(folder/'01-old.json').write_text(json.dumps(p))
   with store.open_project(root) as fd:
    panel=Panel(root/'attachment.json',{'owner':link.process_identity(os.getpid()),'session':'a'*64,'generation':1},60,24,True,True)
    panel.since=200;panel.project=lambda:(os.dup(fd),fd)
    self.assertIn('[Story]',panel.draw(0)['lines'][0])
    panel.action('story',1);self.assertIn('[All saved]',panel.draw(1)['lines'][2])
    panel.action('all',2);self.assertEqual(panel.current(3)[0]['by'],'spark')

 def test_cancel_completion_replaces_cancelling_message(self):
  from painting_panel import Panel
  import launcher_link as link
  from types import SimpleNamespace
  panel=Panel('unused',{'owner':link.process_identity(os.getpid()),'session':'a'*64,'generation':1},60,24,True,True)
  r,w=os.pipe();os.close(w)
  panel.job=SimpleNamespace(stdout=os.fdopen(r,'rb'),poll=lambda:0)
  panel.cancelled=True;panel.message='Cancelling export';panel.status={'fraction':.1,'label':'Drawing'}
  panel.poll_job()
  self.assertEqual(panel.status['label'],'Cancelled');self.assertEqual(panel.message,'')
