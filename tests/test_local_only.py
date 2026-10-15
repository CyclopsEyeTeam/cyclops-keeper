"""Retired sharing preferences must not activate an undisclosed broadcaster."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]/'plugins/cyclops-keeper/scripts'


class LocalOnly(unittest.TestCase):
    def test_legacy_link_consent_is_preserved_but_cannot_publish(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root/'data/link'
            legacy.mkdir(parents=True)
            legacy.chmod(0o700)
            preferences = legacy/'preferences.json'
            original = '{"enabled":true,"reach":true}'
            preferences.write_text(original)
            result = subprocess.run([sys.executable, '-B', str(SCRIPTS/'hook.py')],
                input=json.dumps({'hook_event_name':'SessionStart','source':'startup',
                                  'session_id':'fixture','cwd':tmp}),
                env=dict(os.environ, PLUGIN_DATA=str(root/'data'), KEEPER_LINK='1',
                         KEEPER_LINK_REACH='1', KEEPER_LINK_NO_WORKER='1',
                         CYCLOPS_LINK_DIR=str(root/'broadcast'),
                         XDG_CONFIG_HOME=str(root/'config'), KEEPER_LAUNCH_SOCKET=''),
                text=True, capture_output=True, timeout=3)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '{}\n', ''))
            self.assertEqual(preferences.read_text(), original)
            self.assertEqual(list(legacy.iterdir()), [preferences])
            self.assertFalse((root/'broadcast').exists())


if __name__ == '__main__':
    unittest.main()
