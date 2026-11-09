#!/usr/bin/env python3
"""Real Git updates and setup subprocesses in isolated HOME; no user account operations."""
import json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
import configuration as cfg
from environment_control import Control,Attention
REPO=cfg.REPO
class ControlTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='environment-control-');self.home=Path(self.temp.name)
  self.env=patch.dict(os.environ,HOME=str(self.home));self.env.start()
  self.paths=patch.multiple(cfg,DATA=self.home/'.config/dotfiles/dashboard',SETTINGS=self.home/'.config/dotfiles/dashboard/settings.json');self.paths.start()
  self.control=Control(lambda state:dict(dependencies=[]))
 def tearDown(self):self.paths.stop();self.env.stop();self.temp.cleanup()
 def wait(self):
  self.control.thread.join(15);self.assertFalse(self.control.thread.is_alive());return self.control.status()['job']
 def command(self,*args,cwd=None):return subprocess.check_output(args,cwd=cwd,stderr=subprocess.DEVNULL,text=True).strip()
 def repository(self):
  remote=self.home/'remote.git';publisher=self.home/'publisher';client=self.home/'client'
  self.command('git','init','--bare','-q',str(remote));self.command('git','clone','-q',str(remote),str(publisher))
  self.command('git','config','user.name','Test',cwd=publisher);self.command('git','config','user.email','test@example.invalid',cwd=publisher)
  self.command('git','checkout','-b','main',cwd=publisher);(publisher/'config.txt').write_text('first');self.command('git','add','.',cwd=publisher);self.command('git','commit','-qm','initial',cwd=publisher);self.command('git','push','-qu','origin','main',cwd=publisher)
  self.command('git','clone','-q','--branch','main',str(remote),str(client));return publisher,client
 def advance(self,publisher):
  (publisher/'config.txt').write_text('second');self.command('git','add','.',cwd=publisher);self.command('git','commit','-qm','update',cwd=publisher);self.command('git','push','-q',cwd=publisher)
 def test_status_is_read_only_and_unknown_action_is_rejected(self):
  self.assertFalse(self.control.status()['busy']);self.assertFalse(cfg.DATA.exists())
  with self.assertRaises(Attention):self.control.start('run arbitrary command')
 def test_apply_runs_real_configure_and_preserves_existing_auth(self):
  cfg.DATA.mkdir(parents=True);cfg.SETTINGS.write_text(json.dumps(cfg.defaults()));(self.home/'.zshrc').write_text('export ORIGINAL=preserved\n')
  ssh=self.home/'.ssh';ssh.mkdir();(ssh/'config').write_text('Host original\n    HostName example.invalid\n');before=(ssh/'config').read_bytes()
  token=self.home/'original.netrc';token.write_text('synthetic-existing-auth');settings=cfg.SETTINGS.read_bytes()
  with patch('environment_control.shutil.which',return_value='/installed'):
   self.control.start('apply',cfg.revision());job=self.wait()
  self.assertEqual(job['status'],'done',job);self.assertIn('ORIGINAL=preserved',(self.home/'.zshrc').read_text());self.assertTrue((ssh/'config').read_bytes().endswith(before));self.assertEqual((ssh/'config').read_bytes().count(before),1);self.assertEqual(token.read_text(),'synthetic-existing-auth');self.assertEqual(json.loads(cfg.SETTINGS.read_bytes()),json.loads(settings))
 def test_apply_requires_current_saved_revision(self):
  with self.assertRaises(Attention):self.control.start('apply','new')
  with self.assertRaises(Attention):self.control.start('apply','stale')
 def test_update_checks_then_fast_forwards_without_touching_settings(self):
  publisher,client=self.repository();self.advance(publisher)
  with patch.object(cfg,'REPO',client):
   self.control.start('check_update');self.assertEqual(self.wait()['status'],'done');self.assertEqual(self.control.update['behind'],1);self.assertEqual((client/'config.txt').read_text(),'first')
   self.control.start('update');job=self.wait();self.assertEqual(job['status'],'done',job);self.assertTrue(job['restart_required']);self.assertEqual((client/'config.txt').read_text(),'second')
 def test_dirty_checkout_and_divergence_are_never_reset_or_merged(self):
  publisher,client=self.repository();self.advance(publisher);(client/'local.txt').write_text('keep me')
  with patch.object(cfg,'REPO',client):
   self.control.start('update');self.assertEqual(self.wait()['status'],'needs_action');self.assertEqual((client/'local.txt').read_text(),'keep me');self.assertEqual((client/'config.txt').read_text(),'first')
   self.command('git','config','user.name','Test',cwd=client);self.command('git','config','user.email','test@example.invalid',cwd=client);self.command('git','add','.',cwd=client);self.command('git','commit','-qm','local',cwd=client);before=self.command('git','rev-parse','HEAD',cwd=client)
   self.control.start('update');self.assertEqual(self.wait()['status'],'needs_action');self.assertEqual(self.command('git','rev-parse','HEAD',cwd=client),before)
 def test_module_install_refuses_to_execute_an_unrelated_existing_checkout(self):
  root=self.home/'personal/environment-core';root.mkdir(parents=True);(root/'cli.py').write_text('raise RuntimeError("must not execute")')
  self.command('git','init','-q',str(root));self.command('git','remote','add','origin','https://example.invalid/unknown.git',cwd=root)
  with patch('environment_bridge.registered_locations',return_value={}),patch.object(self.control,'run',side_effect=AssertionError('must not run unrelated code')):
   with self.assertRaises(Attention):self.control.install_module('services')
 def test_git_install_token_is_child_scoped_and_only_used_for_known_module_clones(self):
  credentials=lambda:{'GIT_CONFIG_COUNT':'1','GIT_CONFIG_KEY_0':'http.https://github.com/.extraheader','GIT_CONFIG_VALUE_0':'synthetic-authorization'}
  control=Control(self.control.planner,credentials)
  with patch('environment_control.subprocess.run',return_value=subprocess.CompletedProcess([],0)) as execute:
   control.run(['git','clone','https://github.com/doh0106/environment-core.git','/tmp/fixture']);self.assertEqual(execute.call_args.kwargs['env']['GIT_CONFIG_VALUE_0'],'synthetic-authorization');self.assertNotIn('synthetic-authorization',str(execute.call_args.args))
   control.run(['git','clone','https://example.invalid/repo.git','/tmp/fixture']);self.assertNotIn('GIT_CONFIG_VALUE_0',execute.call_args.kwargs['env'])
   control.run(['bash','install-tool.sh']);self.assertNotIn('GIT_CONFIG_VALUE_0',execute.call_args.kwargs['env'])
  self.assertNotIn('GIT_CONFIG_VALUE_0',os.environ)
 def test_update_preserves_an_ignored_local_file_when_remote_adds_that_path(self):
  publisher,client=self.repository();(client/'.git/info/exclude').write_text('private-settings.json\n');(client/'private-settings.json').write_text('keep local metadata')
  (publisher/'private-settings.json').write_text('remote defaults');self.command('git','add','.',cwd=publisher);self.command('git','commit','-qm','new default file',cwd=publisher);self.command('git','push','-q',cwd=publisher)
  with patch.object(cfg,'REPO',client):
   self.control.start('update');self.assertEqual(self.wait()['status'],'needs_action');self.assertEqual((client/'private-settings.json').read_text(),'keep local metadata')
 def test_interrupted_run_is_reported_without_marking_complete(self):
  cfg.DATA.mkdir(parents=True);(cfg.DATA/'environment-run.json').write_text(json.dumps(dict(status='running',steps=[])))
  self.assertEqual(self.control.status()['job']['status'],'interrupted')
if __name__=='__main__':unittest.main(verbosity=2)
