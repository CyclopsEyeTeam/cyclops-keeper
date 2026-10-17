import json,os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'plugins/cyclops-keeper/scripts'))
import painting_chat as chat

P={'title':'A small sun','mood':'quiet','by':'keeper','model':'keeper','at':1.,'shape':'wide','mirror':None,'marks':[{'k':'dot','x':.5,'y':.5,'r':.1,'c':[1,.6,.2],'a':1}]}
class ChatTests(unittest.TestCase):
 def test_prompt_is_art_and_side_history_only(self):
  p=chat.prompt(P,[{'question':'Why amber?','answer':'For warmth.'}],'What about blue?')
  self.assertIn('What about blue?',p);self.assertIn('For warmth.',p);self.assertNotIn(str(Path.home()),p)
  self.assertNotIn('PRIVATE',chat.prompt({**P,'project':'PRIVATE'},[],'Hello'))
 def test_command_is_ephemeral_without_context_or_execution_tools(self):
  cmd=chat.command('/empty')
  for arg in ['--no-daemon','--ephemeral','--ignore-user-config','--ignore-rules','--strict-config','features.shell_tool=false','features.plugins=false','features.memories=false','features.multi_agent=false','project_doc_max_bytes=0'] :self.assertIn(arg,cmd)
 def test_event_parser_accepts_only_final_and_real_usage(self):
  p=chat.Events();p.feed({'type':'item.completed','item':{'type':'reasoning','text':'SECRET'}})
  p.feed({'type':'item.completed','item':{'type':'agent_message','text':'Amber light.'}})
  p.feed({'type':'turn.completed','usage':{'input_tokens':23,'output_tokens':7}})
  self.assertEqual(p.answer,'Amber light.');self.assertEqual(p.usage,{'input_tokens':23,'output_tokens':7})
  self.assertTrue(p.done)
 def test_controls_are_removed_and_utf8_preserved(self):
  self.assertEqual(chat.clean('café\x1b[31m\x00'), 'café[31m')
 def test_state_refuses_symlink_and_fifo(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'bad';os.mkfifo(p)
   with self.assertRaises(OSError):chat.read(p)
   p.unlink();p.symlink_to('/etc/passwd')
   with self.assertRaises(OSError):chat.read(p)
 def test_duplicate_and_busy_requests_do_not_spawn(self):
  with tempfile.TemporaryDirectory() as td:
   c=chat.Chat(Path(td),'a'*64)
   c.write({'status':'answering','request':'one','history':[]})
   self.assertFalse(c.submit('hello',P,request='two',spawn=lambda *_:self.fail('spawned')))
 def test_cancel_keeps_history_and_discards_pending(self):
  with tempfile.TemporaryDirectory() as td:
   c=chat.Chat(Path(td),'a'*64);c.write({'status':'answering','request':'one','history':[{'question':'q','answer':'a'}]})
   c.cancel();self.assertEqual(c.read()['status'],'cancelled');self.assertEqual(len(c.read()['history']),1)

class EditorTests(unittest.TestCase):
 def test_utf8_and_backspace_are_atomic(self):
  e=chat.Editor()
  for b in 'café'.encode():e.key(bytes([b]))
  self.assertEqual(e.text,'café');e.key(b'\x7f');self.assertEqual(e.text,'caf')
  self.assertEqual(e.key(b'\r'),'send');self.assertEqual(e.key(b'\x1b'),'back')
 def test_chat_consumes_quit_and_cancel_keys(self):
  from painting_terminal import Reader
  r=Reader();r.visible=True;r.chatting=True;sent=[];r.send=lambda message:sent.append(message) or True
  self.assertTrue(r.event(('key',b'q')));self.assertEqual(sent,[{'chat_key':'71'}])

class BridgeTests(unittest.TestCase):
 def test_studio_is_targeted_and_clearing_cancels(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);b=chat.Bridge(root/'data','b'*64,root/'feeds','studio-1',root)
   b.chat.select(P);b.base.mkdir(parents=True,exist_ok=True)
   chat._atomic_json(b.base/'studio.json',{'ask':{'id':'spark-question','text':'Not Keeper'}})
   with patch.object(b.chat,'submit') as submit:b.tick('run-1',None);submit.assert_not_called()
   ask={'id':'keeper-question','text':'Why amber?','run':'run-1','t':__import__('time').time()}
   chat._atomic_json(b.base/'studio.json',{'keeperAsk':ask})
   with patch.object(b.chat,'submit',return_value=True) as submit:
    b.tick('run-2',None);submit.assert_not_called()
    b.tick('run-1',None);submit.assert_called_once()
   b.chat.write({'status':'answering','request':'keeper-question','source':'studio','started':__import__('time').time(),'history':[]})
   chat._atomic_json(b.base/'studio.json',{})
   b.tick('run-1',None);self.assertEqual(b.chat.read()['status'],'cancelled')

class ConcurrencyTests(unittest.TestCase):
 def test_selection_cannot_change_inflight_painting(self):
  with tempfile.TemporaryDirectory() as td:
   c=chat.Chat(Path(td),'d'*64);c.submit('why?',P,spawn=lambda *a,**k:None)
   c.select({**P,'title':'Another painting'})
   self.assertEqual(c.read()['request_painting']['title'],P['title'])
 def test_busy_studio_request_is_not_queued_for_later(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);b=chat.Bridge(root/'data','e'*64,root/'feeds','studio',root);b.base.mkdir(parents=True,exist_ok=True)
   b.chat.write({'status':'answering','request':'old','source':'terminal','started':__import__('time').time(),'painting':P})
   chat._atomic_json(b.base/'studio.json',{'keeperAsk':{'id':'new','run':'run','t':__import__('time').time(),'text':'question'}})
   b.tick('run',None)
   s=b.chat.read();s['status']='done';b.chat.write(s)
   with patch.object(b.chat,'submit') as submit:b.tick('run',None);submit.assert_not_called()

class FreshStudioTests(unittest.TestCase):
 def test_latest_picture_opens_project_as_fd(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'keeper-paintings').mkdir();(root/'keeper-paintings/01-sun.json').write_text(json.dumps(P))
   b=chat.Bridge(root/'data','f'*64,root/'feeds','studio',root);b.base.mkdir(parents=True,exist_ok=True)
   chat._atomic_json(b.base/'studio.json',{'keeperAsk':{'id':'new','run':'run','t':__import__('time').time(),'text':'question'}})
   with patch.object(b.chat,'submit',return_value=True) as submit:
    b.tick('run',None);self.assertEqual(submit.call_args.args[1]['title'],P['title'])

class WorkerLifecycleTests(unittest.TestCase):
 def test_cancel_stops_provider_and_does_not_accept_late_answer(self):
  import threading,time
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as td:
   c=chat.Chat(Path(td),'1'*64);c.submit('question',P,request='cancel-test',spawn=lambda *a,**k:None)
   with patch.object(chat,'command',return_value=[sys.executable,'-c','import time;time.sleep(30)']):
    thread=threading.Thread(target=chat.worker,args=(c.root,'cancel-test'));thread.start()
    deadline=time.monotonic()+2
    while c.read().get('status')!='answering' and time.monotonic()<deadline:time.sleep(.02)
    c.cancel();thread.join(3)
    self.assertFalse(thread.is_alive());self.assertEqual(c.read()['status'],'cancelled');self.assertFalse(c.read().get('history'))

class FinalLifecycleTests(unittest.TestCase):
 def test_old_cancel_does_not_touch_replacement(self):
  with tempfile.TemporaryDirectory() as td:
   c=chat.Chat(Path(td),'2'*64);c.submit('new',P,request='new',spawn=lambda *a,**k:None)
   c.cancel(expected_request='old');self.assertEqual(c.read()['status'],'starting')
 def test_provider_eof_is_not_a_busy_loop(self):
  import threading,time
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as td:
   c=chat.Chat(Path(td),'3'*64);c.submit('question',P,request='eof',spawn=lambda *a,**k:None)
   with patch.object(chat,'command',return_value=[sys.executable,'-c','import os,time;os.close(1);time.sleep(30)']):
    thread=threading.Thread(target=chat.worker,args=(c.root,'eof'));thread.start();thread.join(2)
    if thread.is_alive():c.cancel();thread.join(2);self.fail('EOF left provider running')
    self.assertEqual(c.read()['status'],'error')

class PanelChatTests(unittest.TestCase):
 def test_chat_opens_selected_picture_and_keeps_grid(self):
  from unittest.mock import patch
  from painting_panel import Panel
  from launcher_link import process_identity
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);panel=Panel(root/'attachment',{'owner':process_identity(os.getpid()),'session':'4'*64,'generation':1},60,24,False,True)
   panel.own=P
   with patch('activity.default_data',return_value=root):panel.action('chat')
   for byte in 'café q'.encode():panel.chat_key(bytes([byte]).hex())
   frame=panel.draw(0)
   self.assertTrue(frame['chatting']);self.assertEqual(len(frame['lines']),24);self.assertTrue(all(len(line)==60 for line in frame['lines']))
   self.assertIn('caf', '\n'.join(frame['lines']));self.assertEqual(panel.chat.read()['painting']['title'],P['title'])
   panel.chat_key('1b');self.assertFalse(panel.chatting)

if __name__=='__main__':unittest.main()
