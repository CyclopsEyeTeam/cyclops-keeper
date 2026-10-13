import importlib.util
from pathlib import Path
import sys
import unittest

SCRIPTS=Path(__file__).resolve().parents[1]/'plugins/cyclops-keeper/scripts'
sys.path.insert(0,str(SCRIPTS))

class Policy(unittest.TestCase):
    def module(self):
        self.assertTrue((SCRIPTS/'responsive.py').exists(), 'responsive policy is not implemented')
        import responsive
        return responsive

    def test_allocations_protect_codex_in_both_orientations(self):
        r=self.module()
        for mode in ['side','top']:
            for width in range(1,201):
                for height in [1,11,12,13,14,15,24,60]:
                    amount=r.allocate(mode,width,height)
                    if amount:
                        host=(width-amount-1,height) if mode=='side' else (width,height-amount-1)
                        self.assertGreaterEqual(host[0],48)
                        self.assertGreaterEqual(host[1],12)
        self.assertEqual(r.allocate('side',80,24),23)
        self.assertEqual(r.allocate('top',80,24),8)
        self.assertEqual(r.allocate('side',51,24),0)
        self.assertEqual(r.allocate('side',52,24),3)
        self.assertEqual(r.allocate('top',80,13),0)
        self.assertEqual(r.allocate('top',80,14),1)

    def test_return_requires_spare_space_and_stability(self):
        r=self.module();gate=r.PresenceGate()
        self.assertEqual(gate.update('side',80,24,0),0)
        self.assertEqual(gate.update('side',80,24,.31),23)
        self.assertEqual(gate.update('side',51,24,.32),0)
        for t in [.4,.8,1.2]:self.assertEqual(gate.update('side',53,24,t),0)
        self.assertEqual(gate.update('side',54,24,2),0)
        self.assertEqual(gate.update('side',54,24,2.31),5)

    def test_expression_detail_is_resolution_driven(self):
        r=self.module()
        self.assertEqual(r.detail(100,32),'full')
        self.assertEqual(r.detail(48,20),'compact')
        self.assertEqual(r.detail(24,12),'small')
        self.assertEqual(r.detail(6,1),'micro')
        self.assertEqual(r.detail(1,1),'insufficient')
        self.assertEqual(r.detail(120,2),'micro')

if __name__=='__main__':unittest.main()
