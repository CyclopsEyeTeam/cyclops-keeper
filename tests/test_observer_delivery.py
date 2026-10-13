import concurrent.futures,fcntl,hashlib,json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SCRIPTS=ROOT/'plugins/cyclops-keeper/scripts'
sys.path.insert(0,str(SCRIPTS));import activity
class Delivery(unittest.TestCase):
 def test_sixteen_barrier_writers_record_all_within_measured_budget(self):
  with tempfile.TemporaryDirectory() as tmp:
   data=Path(tmp);worker=data/'slow_worker.py'
   worker.write_text("import sys,os,time,stat\nsys.path.insert(0,sys.argv[1])\nimport hook,activity\nfrom pathlib import Path\np=Path(os.environ['PLUGIN_DATA'])\n(p/(str(os.getpid())+'.ready')).touch()\nwhile not (p/'go').exists():time.sleep(.002)\nf=os.fsync\ndef sync(fd):\n if stat.S_ISREG(os.fstat(fd).st_mode):time.sleep(.065)\n f(fd)\nos.fsync=sync\nhook.main()\n")
   env=dict(os.environ,PLUGIN_DATA=tmp,KEEPER_LINK='0',KEEPER_LAUNCH_SOCKET='',PYTHONDONTWRITEBYTECODE='1')
   def send(i):return subprocess.run([sys.executable,str(worker),str(SCRIPTS)],input=json.dumps({'hook_event_name':'PreToolUse','session_id':'delivery-fixture','tool_use_id':str(i),'tool_name':'Bash'}),capture_output=True,text=True,env=env,timeout=4)
   with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
    futures=[ex.submit(send,i) for i in range(16)]
    deadline=time.monotonic()+3
    while len(list(data.glob('*.ready')))<16 and time.monotonic()<deadline:time.sleep(.005)
    self.assertEqual(len(list(data.glob('*.ready'))),16);(data/'go').touch()
    results=[f.result() for f in futures]
   self.assertTrue(all(p.returncode==0 and p.stdout.strip()=='{}' and p.stderr=='' for p in results),[(p.returncode,p.stderr) for p in results])
   record=json.loads((data/'activity-face/sessions'/ (activity.digest('delivery-fixture')+'.json')).read_text())
   self.assertEqual(set(record['_tools']),{activity.digest(str(i)) for i in range(16)});self.assertEqual(record['sequence'],16)
 def test_overload_is_explicit_and_never_loses_an_acknowledged_event(self):
  with tempfile.TemporaryDirectory() as tmp:
   data=Path(tmp);worker=data/'overload.py'
   worker.write_text("import sys,os,time\nsys.path.insert(0,sys.argv[1])\nimport hook\nf=os.fsync\ndef sync(fd):\n time.sleep(.12);f(fd)\nos.fsync=sync\nhook.main()\n")
   def send(i):return subprocess.run([sys.executable,str(worker),str(SCRIPTS)],input=json.dumps({'hook_event_name':'PreToolUse','session_id':'overload','tool_use_id':str(i)}),capture_output=True,text=True,env=dict(os.environ,PLUGIN_DATA=tmp,KEEPER_LINK='0',KEEPER_LAUNCH_SOCKET=''),timeout=3)
   with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:results=list(ex.map(send,range(16)))
   record=json.loads((data/'activity-face/sessions'/(activity.digest('overload')+'.json')).read_text());keys=set(record['_tools'])
   for i,p in enumerate(results):
    self.assertEqual(p.returncode,0);self.assertEqual(p.stdout.strip(),'{}')
    if not p.stderr:self.assertIn(activity.digest(str(i)),keys)
    else:self.assertIn('observation_timeout',p.stderr)
 def test_held_lock_is_explicitly_rejected_within_host_budget(self):
  with tempfile.TemporaryDirectory() as tmp:
   directory=Path(tmp)/'activity-face/sessions';directory.mkdir(parents=True)
   with (directory/(activity.digest('SECRET-session')+'.lock')).open('w') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    start=time.monotonic();p=subprocess.run([sys.executable,str(SCRIPTS/'hook.py')],input=json.dumps({'hook_event_name':'PreToolUse','session_id':'SECRET-session','tool_use_id':'SECRET-call','tool_input':{'command':'SECRET-command'}}),capture_output=True,text=True,env=dict(os.environ,PLUGIN_DATA=tmp,KEEPER_LINK='0'),timeout=3)
   self.assertLess(time.monotonic()-start,2.9)
   self.assertEqual(p.stdout.strip(),'{}');self.assertIn('observation_timeout',p.stderr)
   self.assertNotIn('SECRET',p.stdout+p.stderr);self.assertFalse(list(directory.glob('*.json')))
 def test_acknowledgement_follows_file_and_directory_fsync(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as tmp:
   calls=[];real=activity.os.fsync
   def sync(fd):
    import stat
    mode=os.fstat(fd).st_mode;calls.append(mode)
    if stat.S_ISDIR(mode):
     # Open-description locking: an independent handle must acquire now.
     path=Path(tmp)/'activity-face/sessions'/(activity.digest('s')+'.lock')
     with path.open('r') as lock:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    return real(fd)
   with patch.object(activity.os,'fsync',side_effect=sync):result=activity.update(tmp,{'hook_event_name':'PreToolUse','session_id':'s','tool_use_id':'one'})
   self.assertIsInstance(result,dict);self.assertEqual(result['status'],'accepted');self.assertGreaterEqual(len(calls),4)
 def test_io_failure_is_visible_and_corrupt_prior_record_is_preserved(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as tmp:
   with patch.object(activity.os,'fsync',side_effect=OSError('PRIVATE-detail')):
    with self.assertRaises(OSError):activity.update(tmp,{'hook_event_name':'PreToolUse','session_id':'s','tool_use_id':'one'})
   directory=Path(tmp)/'activity-face/sessions';self.assertFalse(list(directory.glob('*.json')))
   path=directory/(activity.digest('s')+'.json');path.write_text('unique corrupt negative evidence')
   p=subprocess.run([sys.executable,str(SCRIPTS/'hook.py')],input=json.dumps({'hook_event_name':'PreToolUse','session_id':'s','tool_use_id':'two'}),text=True,capture_output=True,env=dict(os.environ,PLUGIN_DATA=tmp,KEEPER_LINK='0'),timeout=3)
   self.assertEqual(path.read_text(),'unique corrupt negative evidence');self.assertIn('invalid_record',p.stderr)

class ReviewBoundaries(unittest.TestCase):
 def test_new_directory_links_are_synced_before_acknowledgement(self):
  from unittest.mock import patch
  import stat
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'brand-new/data';paths=[];real=activity.os.fsync
   def sync(fd):
    if stat.S_ISDIR(os.fstat(fd).st_mode):paths.append(Path(os.readlink(f'/proc/self/fd/{fd}')))
    return real(fd)
   with patch.object(activity.os,'fsync',side_effect=sync):receipt=activity.update(root,{'hook_event_name':'PreToolUse','session_id':'s','tool_use_id':'one'})
   self.assertEqual(receipt['status'],'accepted')
   self.assertTrue({root/'activity-face/sessions',root/'activity-face',root,root.parent,Path(tmp)}.issubset(paths),paths)
