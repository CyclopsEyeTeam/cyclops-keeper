import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(os.environ.get('KEEPER_TEST_ROOT', str(Path(__file__).resolve().parents[1])))
SETUP = ROOT / 'plugins/cyclops-keeper/scripts/shell_setup.py'


class ShellSetup(unittest.TestCase):
    def test_registration_is_idempotent_and_removal_preserves_user_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = Path(tmp) / 'bash rc'
            original = 'export MY_SETTING=untouched\n# final line without newline'
            rc.write_text(original)
            wrapper = ROOT / 'plugins/cyclops-keeper/scripts/integration.bash'
            command = ['python3', '-B', str(SETUP), 'install', '--rc', str(rc), '--integration', str(wrapper)]
            subprocess.run(command, check=True, capture_output=True)
            installed = rc.read_text()
            subprocess.run(command, check=True, capture_output=True)
            self.assertEqual(rc.read_text(), installed)
            # Loading the registered file really defines Codex, without starting it.
            result = subprocess.run(['bash', '--noprofile', '--norc', '-c',
                                     'source "$1"; declare -F codex; unset -f codex; ! declare -F codex',
                                     'bash', str(rc)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run(['python3', '-B', str(SETUP), 'remove', '--rc', str(rc)],
                           check=True, capture_output=True)
            self.assertEqual(rc.read_text(), original)

    def test_symlink_startup_file_is_refused_without_changing_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'target'
            target.write_text('keep me')
            rc = Path(tmp) / 'rc'
            rc.symlink_to(target)
            result = subprocess.run(['python3', '-B', str(SETUP), 'install', '--rc', str(rc),
                                     '--integration', str(ROOT / 'plugins/cyclops-keeper/scripts/integration.bash')], capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(target.read_text(), 'keep me')


if __name__ == '__main__':
    unittest.main()
