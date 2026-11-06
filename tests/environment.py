import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('bridge_test',ROOT/'bin/environment_bridge.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class EnvironmentTests(unittest.TestCase):
    def test_missing_core_keeps_existing_features_independent(self):
        bridge=module.EnvironmentBridge()
        with patch.object(module.subprocess,'run',side_effect=AssertionError('unexpected process')):
            self.assertEqual(bridge.status()['availability'],'unavailable')

    def test_exact_root_and_protocol_with_no_authentication_inheritance(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp)/'cli.py').write_text('# synthetic adapter')
            bridge=module.EnvironmentBridge(core=temp)
            response=json.dumps({'protocol_version':1,'connections':[],'observed_at':'synthetic'})
            with patch.dict(os.environ,{'BW_SESSION':'SYNTHETIC','GH_TOKEN':'SYNTHETIC'}),patch.object(module.subprocess,'run',return_value=subprocess.CompletedProcess([],0,response,'')) as run:
                self.assertEqual(bridge.status()['availability'],'available')
            command=run.call_args.args[0]
            self.assertEqual(command[1],'-I')
            self.assertEqual(command[2],str(Path(temp).resolve()/'cli.py'))
            self.assertNotIn('GH_TOKEN',run.call_args.kwargs['env'])
            self.assertNotIn('BW_SESSION',run.call_args.kwargs['env'])

    def test_protocol_mismatch_is_not_success(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp)/'cli.py').write_text('# synthetic adapter')
            bridge=module.EnvironmentBridge(core=temp)
            with patch.object(module.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'{"protocol_version":2}','')):
                self.assertEqual(bridge.status()['availability'],'unavailable')

    def test_registered_digest_mismatch_never_executes_changed_code(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'cli.py').write_text('# synthetic code')
            (root/'environment_core').mkdir()
            digest=module.source_digest(root)
            bridge=module.EnvironmentBridge(core=temp,digest=digest)
            (root/'cli.py').write_text('# changed code')
            with patch.object(module.subprocess,'run',side_effect=AssertionError('changed code executed')):
                self.assertEqual(bridge.status()['availability'],'unavailable')


if __name__=='__main__':unittest.main(verbosity=2)
