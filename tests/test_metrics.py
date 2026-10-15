"""Composition CPU must exclude time spent waiting for external work."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(os.environ.get('KEEPER_TEST_ROOT', str(Path(__file__).resolve().parents[1])))


class Metrics(unittest.TestCase):
    def test_waiting_is_not_reported_as_cpu(self):
        with tempfile.TemporaryDirectory() as tmp:
            program = """import sys,time
sys.path.insert(0,sys.argv[1])
import terminal
original=terminal.render
def waiting(*args,**kwargs):
 time.sleep(.15)
 return original(*args,**kwargs)
terminal.render=waiting
sys.argv=['terminal','--once','--ascii','--metrics']
terminal.main()
"""
            result = subprocess.run([sys.executable, '-B', '-c', program,
                                     str(ROOT/'plugins/cyclops-keeper/scripts')],
                                    env=dict(os.environ, PLUGIN_DATA=tmp, KEEPER_LINK='0',
                                             COLUMNS='6', LINES='1'),
                                    text=True, capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stderr)
            self.assertGreaterEqual(report['wall_ms'], 150)
            self.assertLess(report['cpu_ms'], report['wall_ms']*.5)


if __name__ == '__main__':
    unittest.main()
