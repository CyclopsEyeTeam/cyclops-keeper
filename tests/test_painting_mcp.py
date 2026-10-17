import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'plugins/cyclops-keeper/scripts'))
import presence_mcp
from test_painting_store import sample

class PaintingMCP(unittest.TestCase):
    def call(self,name,args):
        return presence_mcp.respond({'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':name,'arguments':args}})['result']

    def test_stdio_duplicate_keys_are_refused(self):
        import subprocess
        raw=b'{"jsonrpc":"2.0","id":1,"method":"ping","method":"tools/list"}\n'
        result=subprocess.run([sys.executable,'-B',str(Path(presence_mcp.__file__))],input=raw,capture_output=True,timeout=5)
        response=json.loads(result.stdout)
        self.assertEqual(response.get('error',{}).get('code'),-32700)

    def test_saved_painting_tool_is_separate_from_expression(self):
        tools={t['name']:t for t in presence_mcp.TOOLS}
        self.assertIn('save_painting',tools)
        self.assertIn('strokes',tools['paint']['inputSchema']['properties'])
        self.assertIn('read_paintings',tools)

    def test_unbound_save_and_unreviewed_text_refused(self):
        with patch.dict(os.environ,{},clear=True):
            result=self.call('save_painting',{'painting':sample(),'privacy_checked':True})
        self.assertTrue(result.get('isError'))
        self.assertNotIn('Unknown Keeper tool',result['content'][0]['text'])

    def test_bound_save_read_and_generation_change(self):
        self.assertIsNotNone(importlib.util.find_spec('painting_mcp'),'saved painting interface missing')
        import painting_mcp
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
            self.addCleanup(os.close,fd)
            state={'owner':{'pid':os.getpid(),'start':'test'},'session':'opaque','generation':1,'project_fd':fd}
            path=root/'attachment.json'
            expression=root/'.keeper-expression.json';expression.write_bytes(b'keep this exactly')
            before=expression.stat().st_mtime_ns
            with patch.object(painting_mcp.expression,'binding',return_value=(path,state)):
                refused=self.call('save_painting',{'painting':sample(),'privacy_checked':False})
                self.assertTrue(refused.get('isError'));self.assertFalse((root/'keeper-paintings').exists())
                result=self.call('save_painting',{'painting':sample(),'privacy_checked':True})
                self.assertNotIn('isError',result)
                listed=self.call('read_paintings',{'owner':'keeper'})
                self.assertIn('01-an-open-window.json',listed['content'][0]['text'])
            self.assertEqual(expression.read_bytes(),b'keep this exactly');self.assertEqual(expression.stat().st_mtime_ns,before)
            changed=dict(state,generation=2)
            with patch.object(painting_mcp.expression,'binding',side_effect=[(path,state),(path,changed)]):
                result=self.call('save_painting',{'painting':sample('Changed'),'privacy_checked':True})
                self.assertTrue(result.get('isError'))
            self.assertEqual(len(list((root/'keeper-paintings').glob('*.json'))),1)
