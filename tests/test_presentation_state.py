from pathlib import Path
import os
import sys
import tempfile
import unittest
SCRIPTS=Path(__file__).resolve().parents[1]/'plugins/cyclops-keeper/scripts'
sys.path.insert(0,str(SCRIPTS))
import launcher_link as link

class PresentationState(unittest.TestCase):
    def module(self):
        self.assertTrue((SCRIPTS/'presentation_state.py').exists(),'resize preferences are not retained yet')
        import presentation_state
        return presentation_state

    def test_preferences_belong_to_the_same_live_launch(self):
        module=self.module()
        with tempfile.TemporaryDirectory(prefix='keeper-view-') as tmp:
            path=Path(tmp)/'attachment.json';owner=link.process_identity(os.getpid())
            link.atomic(path,{'v':1,'owner':owner,'session':None,'project_fd':None})
            self.assertTrue(module.save(path,True,True))
            self.assertEqual(module.load(path),{'calm':True,'reduced_motion':True})
            link.atomic(path,{'v':1,'owner':dict(owner,start='different'),'session':None,'project_fd':None})
            self.assertEqual(module.load(path),{})

    def test_unmanaged_attachment_does_not_gain_writable_preferences(self):
        module=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'attachment.json'
            link.atomic(path,{'v':1,'owner':link.process_identity(os.getpid()),'session':None,'project_fd':None})
            self.assertFalse(module.save(path,True,True))
            self.assertFalse((Path(tmp)/'.keeper-view.json').exists())

if __name__=='__main__':unittest.main()
