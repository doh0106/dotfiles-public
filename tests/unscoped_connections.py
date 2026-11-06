#!/usr/bin/env python3
"""Profile-free connections require explicit selection and never install global credentials."""
import copy
import json
import os
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
import configuration as cfg
import auth
import runbook

class UnscopedConnectionsTests(unittest.TestCase):
    def setUp(self):
        self.state=cfg.defaults();self.state['profiles']=[]
        self.connection=cfg.new_connection('', 'manual-git');self.connection.update(name='Manual Git',provider='generic',host='git.example.org',method='https',enabled=True)
        self.state['connections']=[self.connection]
    def test_no_profile_and_no_credential_public_git_can_be_saved(self):
        files=cfg.compile(self.state);runtime=json.loads(files['profiles.json'])
        self.assertEqual(runtime['profiles'],{})
        self.assertIn('connection-manual-git.gitconfig',files)
        self.assertNotIn('[credential',files['git.config'])
        self.assertNotIn('includeIf',files['git.config'])
    def test_explicit_https_helper_uses_connection_and_exact_host(self):
        self.state['credentials']=[dict(id='token',source='bitwarden',kind='note',item='synthetic-token',variable='',helper='cache',username='example')]
        self.connection['credential']='token'
        files=cfg.compile(self.state);runtime=json.loads(files['profiles.json'])
        self.assertIn('--connection',files['connection-manual-git.gitconfig'])
        self.assertNotIn('[credential',files['git.config'])
        with patch('auth.choose',side_effect=AssertionError('must not infer folder profile')):
            name,_,selected=auth.selection(runtime,connection='manual-git',https_host='git.example.org')
            self.assertEqual(name,'');self.assertEqual(selected['id'],'manual-git')
            with self.assertRaises(RuntimeError):auth.selection(runtime,connection='manual-git',https_host='other.example.org')
            with self.assertRaises(RuntimeError):auth.selection(runtime,explicit='wrong',connection='manual-git')
    def test_real_git_credential_fill_routes_only_selected_host_without_profile(self):
        self.state['credentials']=[dict(id='token',source='bitwarden',kind='note',item='fixture',variable='',helper='cache',username='example')]
        self.connection['credential']='token'
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory);old=(cfg.DATA,cfg.SETTINGS);cfg.DATA=home/'.config/dotfiles/dashboard';cfg.SETTINGS=cfg.DATA/'settings.json'
            try:cfg.generate(self.state,'new')
            finally:cfg.DATA,cfg.SETTINGS=old
            mocks=home/'bin';mocks.mkdir();bw=mocks/'bw';log=home/'calls'
            bw.write_text('#!/usr/bin/env python3\nimport os,pathlib,sys\npathlib.Path(os.environ["TEST_BW_LOG"]).write_text("called")\nprint("synthetic-token")\n');bw.chmod(0o755)
            env=dict(os.environ,HOME=str(home),PATH=str(mocks)+os.pathsep+os.environ['PATH'],GIT_CONFIG_GLOBAL='/dev/null',GIT_CONFIG_NOSYSTEM='1',GIT_TERMINAL_PROMPT='0',TEST_BW_LOG=str(log))
            command=['git','-c','credential.helper=','-c','include.path='+str(home/'.config/dotfiles/dashboard/connection-manual-git.gitconfig'),'credential','fill']
            result=subprocess.run(command,input='protocol=https\nhost=git.example.org\n\n',capture_output=True,text=True,env=env,cwd=home)
            self.assertEqual(result.returncode,0,result.stderr);self.assertIn('password=synthetic-token',result.stdout);self.assertTrue(log.exists())
            log.unlink()
            result=subprocess.run(command,input='protocol=https\nhost=unrelated.example.org\n\n',capture_output=True,text=True,env=env,cwd=home)
            self.assertNotEqual(result.returncode,0);self.assertFalse(log.exists());self.assertNotIn('synthetic-token',result.stdout+result.stderr)
    def test_two_manual_connections_to_same_host_have_separate_ssh_files(self):
        self.connection.update(method='ssh',credential='agent',publicKey='/tmp/synthetic.pub')
        self.state['credentials']=[dict(id='agent',source='agent',kind='note',item='',variable='',helper='cache',username='')]
        other=copy.deepcopy(self.connection);other.update(id='manual-work',publicKey='/tmp/synthetic-work.pub');self.state['connections'].append(other)
        files=cfg.compile(self.state)
        self.assertIn('ssh-connection-manual-git.config',files)
        self.assertIn('ssh-connection-manual-work.config',files)
        self.assertNotIn('sshCommand',files['git.config'])
    def test_missing_explicit_selection_does_not_fall_back_to_unscoped_connection(self):
        runtime=json.loads(cfg.compile(self.state)['profiles.json'])
        with patch('auth.run',return_value=type('Result',(),{'returncode':1})()):
            with self.assertRaises(RuntimeError):auth.selection(runtime)
    def test_unknown_nonempty_profile_still_rejected(self):
        self.connection['profile']='missing'
        with self.assertRaises(ValueError):cfg.validate(self.state)
    def test_runbook_generates_manual_policy_and_no_empty_profile_paths(self):
        steps=runbook.build(cfg.validate(self.state),[],Path('/tmp/repo'),Path('/tmp/settings'))
        text=json.dumps(steps,ensure_ascii=False)
        self.assertIn('connection-manual-git.gitconfig',text)
        self.assertIn('/PATH/TO/REPO',text)
        self.assertNotIn('profile-.gitconfig',text)
        self.assertNotIn('ssh-.config',text)
if __name__=='__main__':unittest.main(verbosity=2)
