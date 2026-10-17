"""Exercise the installer in a private home with a disposable Codex package manager."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Installation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='keeper-install-')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        binary = self.home / 'bin'
        binary.mkdir()
        codex = binary / 'codex'
        codex.write_text('''#!/usr/bin/env python3
import json, os, shutil, sys
from pathlib import Path
args = sys.argv[1:]
home = Path(os.environ['CODEX_HOME'])
with (Path(os.environ['HOME'])/'calls.jsonl').open('a') as log:
    log.write(json.dumps(args)+'\\n')
if args[:2] == ['plugin','add']:
    source = Path(os.environ['FIXTURE_SOURCE'])/'plugins/cyclops-keeper'
    version = json.loads((source/'.codex-plugin/plugin.json').read_text())['version']
    target = home/'plugins/cache/cyclops-keeper/cyclops-keeper'/version
    if target.parent.exists(): shutil.rmtree(target.parent)
    if os.environ.get("FIXTURE_INSTALL_FAIL"): sys.exit(7)
    shutil.copytree(source,target)
    (home/'installed').touch()
elif args[:3] == ['plugin','marketplace','add']:
    home.mkdir(parents=True,exist_ok=True);(home/'marketplace').touch()
elif args[:2] == ['plugin','remove']:
    if not (home/'installed').exists():sys.exit(2)
    (home/'installed').unlink();shutil.rmtree(home/'plugins/cache/cyclops-keeper')
elif args[:3] == ['plugin','marketplace','remove']:
    if not (home/'marketplace').exists():sys.exit(2)
    (home/'marketplace').unlink()
elif args == ['plugin','list','--json']:
    print(os.environ.get('FIXTURE_PLUGIN_STATUS',json.dumps({'installed':[{'pluginId':'cyclops-keeper@cyclops-keeper','installed':True}] if (home/'installed').exists() else [], 'available':[]})))
elif args == ['plugin','marketplace','list','--json']:
    print(os.environ.get('FIXTURE_MARKETPLACE_STATUS',json.dumps({'marketplaces':[{'name':'cyclops-keeper'}] if (home/'marketplace').exists() else []})))
elif args == ['plugin','list']:
    print('cyclops-keeper@cyclops-keeper '+('installed, enabled' if (home/'installed').exists() else 'not installed'))
    print('unrelated available plugin '*100000)
elif args == ['plugin','marketplace','list']:
    if (home/'marketplace').exists():print('cyclops-keeper')
elif args[:1] != ['plugin']:
    print(json.dumps(args))
''')
        codex.chmod(0o700)
        for name in ['tmux', 'gnome-terminal']:
            tool = binary / name
            tool.write_text('#!/bin/sh\nexit 0\n')
            tool.chmod(0o700)
        self.env = dict(os.environ, HOME=str(self.home), CODEX_HOME=str(self.home/'.codex'),
                        PATH=str(binary)+os.pathsep+os.environ['PATH'], FIXTURE_SOURCE=str(ROOT))
        for name in ['KEEPER_SHELL_ACTIVE', 'KEEPER_LAUNCHER', 'KEEPER_CODEX', 'KEEPER_PLUGIN_ROOT']:
            self.env.pop(name, None)
        self.rc = self.home / '.bashrc'
        self.original = 'export USER_SETTING=untouched\n# final line without newline'
        self.rc.write_text(self.original)

    def run_script(self, name, *args, env_override=None):
        return subprocess.run(['bash', str(ROOT/name), *args], env=dict(self.env, **(env_override or {})),
                              text=True, capture_output=True, timeout=15)

    def test_upgrade_preserves_old_session_files_even_on_failure(self):
        import hashlib
        for fail in ('', '1'):
            with self.subTest(failed=bool(fail)):
                old=self.home/'.codex/plugins/cache/cyclops-keeper/cyclops-keeper/0.4.0'
                (old/'scripts').mkdir(parents=True,exist_ok=True)
                (old/'.codex-plugin').mkdir(exist_ok=True)
                (old/'.codex-plugin/plugin.json').write_text('{"name":"cyclops-keeper","version":"0.4.0"}')
                hook=old/'scripts/hook.py';hook.write_text('print("original hook")\n')
                digest=hashlib.sha256(hook.read_bytes()).hexdigest()
                result=self.run_script('install.sh',env_override={'FIXTURE_INSTALL_FAIL':fail})
                self.assertEqual(result.returncode == 0, not bool(fail),result.stderr)
                self.assertTrue(hook.is_file(),'refresh removed the active session hook')
                self.assertEqual(hashlib.sha256(hook.read_bytes()).hexdigest(),digest)
                if not fail:
                    self.assertFalse((old/'.codex-plugin/plugin.json').exists(), 'old manifest remains discoverable')

    def test_plain_install_enables_codex_and_refresh_is_idempotent(self):
        first = self.run_script('install.sh')
        self.assertEqual(first.returncode, 0, first.stderr)
        installed = self.rc.read_text()
        self.assertNotEqual(installed, self.original, 'plain install did not enable the commands')
        self.assertIn(str(ROOT/'plugins/cyclops-keeper/scripts/integration.bash'),installed)
        self.assertNotIn('/plugins/cache/',installed)
        again = self.run_script('install.sh')
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(self.rc.read_text(), installed)
        shell = subprocess.run(['bash', '--noprofile', '--norc', '-c',
                                'source "$HOME/.bashrc"; declare -F codex; codex --version'],
                               env=self.env, text=True, capture_output=True, timeout=5)
        self.assertEqual(shell.returncode, 0, shell.stderr)
        self.assertEqual(shell.stdout.splitlines(), ['codex', '["--version"]'])
        self.assertIn('codex --keeper side', first.stdout)
        self.assertIn('codex --keeper top', first.stdout)

    def test_uninstall_restores_the_exact_startup_file(self):
        self.assertEqual(self.run_script('install.sh').returncode, 0)
        removed = self.run_script('uninstall.sh')
        self.assertEqual(removed.returncode, 0, removed.stderr)
        self.assertEqual(self.rc.read_text(), self.original)

    def test_uninstall_removes_the_installed_plugin_and_is_safe_to_repeat(self):
        self.assertEqual(self.run_script('install.sh').returncode,0)
        activity=self.home/'.codex/plugins/data/cyclops-keeper-cyclops-keeper/activity.json'
        activity.parent.mkdir(parents=True);activity.write_text('recorded fixture activity')
        removed=self.run_script('uninstall.sh')
        self.assertEqual(removed.returncode,0,removed.stderr)
        self.assertFalse((self.home/'.codex/installed').exists(), 'installed plugin remained after uninstall')
        self.assertFalse((self.home/'.codex/marketplace').exists())
        self.assertEqual(activity.read_text(),'recorded fixture activity')
        again=self.run_script('uninstall.sh')
        self.assertEqual(again.returncode,0,again.stderr)
        self.assertEqual(self.rc.read_text(),self.original)
        self.assertEqual(activity.read_text(),'recorded fixture activity')

    def test_uninstall_removes_previous_shell_registration(self):
        self.rc.write_text(self.original + '\n# >>> Cyclops Keeper shell >>>\n'
                           'source /old/keeper-shell.sh\n# <<< Cyclops Keeper shell <<<\n')
        self.assertEqual(self.run_script('uninstall.sh').returncode, 0)
        self.assertEqual(self.rc.read_text(), self.original)

    def test_uninstall_stops_on_unexpected_sdk_status_without_claiming_success(self):
        for variable, field, identifier, marker in [
            ('FIXTURE_PLUGIN_STATUS', 'installed', 'pluginId', 'installed'),
            ('FIXTURE_MARKETPLACE_STATUS', 'marketplaces', 'name', 'marketplace'),
        ]:
            for value in [[], {field: {}}, {field: ''}, {field: [None]},
                          {field: [{identifier: 7}]}, {field: [{}]}]:
                with self.subTest(variable=variable, value=value):
                    self.assertEqual(self.run_script('install.sh').returncode, 0)
                    removed = self.run_script('uninstall.sh',
                                              env_override={variable: json.dumps(value)})
                    self.assertNotEqual(removed.returncode, 0, removed.stdout)
                    self.assertNotIn('Cyclops Keeper is uninstalled.', removed.stdout)
                    self.assertTrue((self.home/'.codex'/marker).exists(),
                                    'unexpected status was treated as absence')

    def test_extra_install_modes_are_rejected_before_plugin_changes(self):
        result = self.run_script('install.sh', '--shell')
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.home/'calls.jsonl').exists())
        self.assertEqual(self.rc.read_text(), self.original)

    def test_symlink_startup_is_refused_before_plugin_changes(self):
        target = self.home / 'personal-rc'
        self.rc.rename(target)
        self.rc.symlink_to(target)
        result = self.run_script('install.sh')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home/'calls.jsonl').exists())
        self.assertEqual(target.read_text(), self.original)

    def test_existing_codex_customisations_are_refused_before_plugin_changes(self):
        for definition in ["alias codex='command codex -m personal'\n",
                           "codex() { command codex -m personal \"$@\"; }\n",
                           "function codex { command codex \"$@\"; }\n"]:
            with self.subTest(definition=definition):
                self.rc.write_text(definition)
                result = self.run_script('install.sh')
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('codex', result.stderr)
                self.assertFalse((self.home/'calls.jsonl').exists())
                self.assertEqual(self.rc.read_text(), definition)


if __name__ == '__main__':
    unittest.main()
