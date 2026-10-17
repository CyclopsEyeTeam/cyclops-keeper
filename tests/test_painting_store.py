import copy
import hashlib
import importlib.util
import json
import multiprocessing
import os
from pathlib import Path
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'plugins/cyclops-keeper/scripts'
sys.path.insert(0, str(SCRIPTS))

def sample(title='An open window'):
    return dict(title=title, mood='still', mirror=None, marks=[dict(k='dot', x=.5, y=.5, r=.1, c=[1,.5,.2], a=.8)], model='keeper', at=1792210000.25, by='keeper', shape='wide')

def save_worker(project, index, queue):
    import painting_store as ps
    with ps.open_project(project) as fd:
        queue.put(ps.save(fd, sample('Window '+str(index))))

class PaintingStore(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('painting_store'), 'painting storage is not implemented')
        import painting_store
        self.ps = painting_store
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_huge_number_is_validation_error(self):
        p=sample();p['marks'][0]['r']=10**400
        with self.assertRaises(ValueError):self.ps.validate(p)

    def test_existing_large_number_is_not_ignored(self):
        folder=self.root/'keeper-paintings';folder.mkdir()
        (folder/'1000000000000-old.json').write_text('{}')
        with self.ps.open_project(self.root) as fd:
            self.assertTrue(self.ps.save(fd,sample()).startswith('1000000000001-'))

    def test_peer_legacy_metadata_is_ignored_not_exposed(self):
        p=sample();p['by']='prism';p['tokens']={'private':'must not return'};p['v']=1
        result=self.ps.validate(p,'prism',True)
        self.assertNotIn('tokens',result);self.assertNotIn('v',result)
        with self.assertRaises(ValueError):self.ps.validate(p)

    def test_replaced_temporary_inode_never_publishes_link(self):
        from unittest.mock import patch
        folder=self.root/'keeper-paintings';folder.mkdir()
        target=self.root/'private';target.write_text('private')
        link=os.link
        def race(src,dst,**kwargs):
            for temp in folder.glob('.tmp-*'):
                temp.unlink();temp.symlink_to(target)
            return link(src,dst,**kwargs)
        with self.ps.open_project(self.root) as fd,patch.object(self.ps.os,'link',side_effect=race):
            try:self.ps.save(fd,sample())
            except OSError:pass
        for f in folder.glob('*.json'):
            self.assertFalse(f.is_symlink(),'temporary substitution published a symlink')
            self.assertEqual(json.loads(f.read_text())['title'],'An open window')
        self.assertEqual(target.read_text(),'private')

    def test_valid_composition_is_unchanged(self):
        p=sample(); before=copy.deepcopy(p)
        self.assertEqual(self.ps.validate(p),p)
        self.assertEqual(p,before)

    def test_rejects_malformed_without_clamping(self):
        for field,value in [('r',.71),('r',.003),('a',1.1),('x',float('nan')),('x',True),('c',[255,0,0]),('k','unknown')]:
            p=sample();p['marks'][0][field]=value
            with self.subTest(field=field,value=value), self.assertRaises(ValueError):self.ps.validate(p)
        for field,value in [('marks',[]),('marks',sample()['marks']*97),('title','x'*49),('thought','x'*161),('by','spark'),('at',0),('shape','round'),('mirror','z'),('prompt','private')]:
            p=sample();p[field]=value
            with self.subTest(field=field), self.assertRaises(ValueError):self.ps.validate(p)

    def test_rejects_privacy_and_control_text(self):
        for text in ['/home/tom/secret', 'C:\\Users\\Tom', 'ses_abcdefgh123', '01234567-89ab-cdef-0123-456789abcdef', 'a@b.com', 'https://example.com', 'x\x1b[2J', 'prompt: secret', 'tool result: secret']:
            for field in ['title','thought','mood']:
                p=sample();p[field]=text
                with self.subTest(text=text,field=field),self.assertRaises(ValueError):self.ps.validate(p)

    def test_all_marks_and_numeric_bounds(self):
        marks=[dict(k=k,pts=[[0,0],[.5,1],[1,0]],w=.003,c=[0,0,0],a=0,c2=[1,1,1]) for k in ['line','curve']]
        marks += [dict(k='fill',pts=[[0,0],[1,0],[0,1]],grad=-4,c=[1,0,0],a=1)]
        marks += [dict(k=k,x=0,y=1,r=.7,c=[0,1,0],a=1,**extra) for k,extra in [('ring',{'w':.12}),('arc',{'w':.12,'a0':-4,'a1':4}),('glow',{}),('spray',{'n':200,'s':.06,'seed':999999})]]
        p=sample();p['marks']=marks
        self.assertEqual(self.ps.validate(p),p)
        for field,value in [('n',201),('n',2.5),('s',.001),('seed',0)]:
            q=copy.deepcopy(p);q['marks'][-1][field]=value
            with self.assertRaises(ValueError):self.ps.validate(q)

    def test_json_duplicate_keys_and_oversize_refused(self):
        for raw in [b'{"title":"a","title":"b"}', b' '*262145, b'{"x":NaN}']:
            with self.assertRaises(ValueError):self.ps.decode(raw)

    def test_duplicate_save_rechecks_attachment_before_success(self):
        with self.ps.open_project(self.root) as fd:
            self.ps.save(fd,sample())
            calls=[]
            def guard():
                calls.append(1)
                if len(calls)>1:raise ValueError('attachment changed')
            with self.assertRaises(ValueError):self.ps.save(fd,sample(),guard)

    def test_save_deduplicates_and_never_replaces(self):
        with self.ps.open_project(self.root) as fd:
            a=self.ps.save(fd,sample());path=self.root/'keeper-paintings'/a
            before=(path.read_bytes(),path.stat().st_mtime_ns)
            p=sample();p['at']+=.5
            self.assertEqual(self.ps.save(fd,p),a)
            self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),before)
            b=self.ps.save(fd,sample('Second'))
            self.assertTrue(b.startswith('02-'))
            self.assertEqual(len(list(path.parent.glob('*.json'))),2)
            self.assertFalse(list(path.parent.glob('.tmp-*')))

    def test_concurrent_writers_have_distinct_numbers(self):
        ctx=multiprocessing.get_context('fork');q=ctx.Queue()
        procs=[ctx.Process(target=save_worker,args=(self.root,i,q)) for i in range(8)]
        for p in procs:p.start()
        for p in procs:p.join(10);self.assertEqual(p.exitcode,0)
        names=[q.get(timeout=2) for _ in procs]
        self.assertEqual(sorted(int(n.split('-')[0]) for n in names),list(range(1,9)))

    def test_folder_and_file_symlinks_are_never_followed(self):
        other=self.root/'other';other.mkdir()
        folder=self.root/'keeper-paintings';folder.symlink_to(other,target_is_directory=True)
        with self.ps.open_project(self.root) as fd:
            with self.assertRaises((OSError,ValueError)):self.ps.save(fd,sample())
        self.assertEqual(list(other.iterdir()),[])
        folder.unlink();folder.mkdir()
        target=other/'target';target.write_text('untouched')
        (folder/'01-an-open-window.json').symlink_to(target)
        with self.ps.open_project(self.root) as fd:self.assertTrue(self.ps.save(fd,sample()).startswith('02-'))
        self.assertEqual(target.read_text(),'untouched')

    def test_peer_read_is_unchanged_and_skips_invalid(self):
        folder=self.root/'prism-paintings';folder.mkdir()
        p=sample();p['by']='unknown';p['model']='prism'
        path=folder/'01-peer.json';path.write_text(json.dumps(p))
        before=(hashlib.sha256(path.read_bytes()).hexdigest(),path.stat().st_mtime_ns)
        (folder/'02-link.json').symlink_to(path)
        (folder/'03-bad.json').write_text('{')
        bad=sample();bad['marks'][0]['k']='spaceship'
        (folder/'04-bad.json').write_text(json.dumps(bad))
        with self.ps.open_project(self.root) as fd:result=self.ps.read(fd,'prism')
        self.assertEqual(len(result),1);self.assertEqual(result[0]['painting']['by'],'prism')
        self.assertEqual((hashlib.sha256(path.read_bytes()).hexdigest(),path.stat().st_mtime_ns),before)
        self.assertEqual(len(list(folder.iterdir())),4)
        with self.ps.open_project(self.root) as fd:
            with self.assertRaises(ValueError):self.ps.read(fd,'../other')

if __name__ == '__main__':unittest.main()
