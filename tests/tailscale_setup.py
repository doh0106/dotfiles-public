#!/usr/bin/env python3
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
import configuration as cfg
import tailscale_setup as ts

class TailscaleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.home=Path(self.tmp.name);self.old=(cfg.DATA,cfg.SETTINGS)
        cfg.DATA=self.home/'.config/dotfiles/dashboard';cfg.SETTINGS=cfg.DATA/'settings.json'
        self.target=dict(alias='example-wsl',host='example.test.ts.net',user='example',account='example@github',client='macos',fingerprints='SHA256:'+'A'*43)
    def tearDown(self):cfg.DATA,cfg.SETTINGS=self.old;self.tmp.cleanup()
    def save(self):return ts.save(self.target,ts.snapshot()['revision'])
    def test_status_read_only_and_save_does_not_touch_ssh_or_main_settings(self):
        with patch('tailscale_setup.subprocess.run') as runner:
            self.assertIsNone(ts.snapshot()['target']);runner.assert_not_called()
        self.assertFalse(self.home.joinpath('.config').exists())
        data=self.save()
        self.assertEqual(data['target'],self.target)
        self.assertFalse((self.home/'.ssh').exists());self.assertFalse(cfg.SETTINGS.exists())
        self.assertNotIn('IdentityFile',data['ssh_config']);self.assertIn('ForwardAgent no',data['ssh_config'])
        self.assertEqual((ts.root()/'settings.json').stat().st_mode&0o777,0o600)
    def test_step_order_stale_write_and_target_change_invalidation(self):
        data=self.save()
        with self.assertRaises(ValueError):ts.acknowledge('connect',True,data['revision'])
        for step in ts.STEPS:data=ts.acknowledge(step,True,data['revision'])
        self.assertEqual(len(ts.snapshot()['records']),4)
        with self.assertRaises(ValueError):ts.save(self.target,'stale')
        other=copy.deepcopy(self.target);other['host']='another.test.ts.net'
        self.assertEqual(ts.save(other,data['revision'])['records'],{})
    def test_corrupt_optional_config_does_not_break_dashboard_snapshot_or_get_overwritten(self):
        ts.root().mkdir(parents=True);path=ts.root()/'settings.json';path.write_text('invalid json')
        self.assertEqual(ts.snapshot()['revision'],'unreadable')
        with self.assertRaises(ValueError):ts.save(self.target,'unreadable')
        self.assertEqual(path.read_text(),'invalid json')
    def test_cancel_invalidates_later_steps(self):
        data=self.save()
        for step in ts.STEPS:data=ts.acknowledge(step,True,data['revision'])
        data=ts.acknowledge('login',False,data['revision'])
        self.assertEqual(set(data['records']),{'install'})
    def test_unsafe_target_and_symlink_rejected(self):
        for key,value in [('host','x\nProxyCommand bad'),('alias','-oProxyCommand=bad'),('user','x;uname'),('fingerprints','no fingerprint')]:
            target=dict(self.target,**{key:value})
            with self.assertRaises(ValueError):ts.validate(target)
        ts.root().parent.mkdir(parents=True);ts.root().symlink_to(self.home,target_is_directory=True)
        with self.assertRaises(ValueError):ts.read()
        self.assertEqual(ts.snapshot()['revision'],'unreadable')
    def test_observation_has_fixed_read_only_args_and_does_not_leak_auth_url_or_peers(self):
        self.save()
        response=subprocess.CompletedProcess([],0,json.dumps({'BackendState':'Running','Self':{'UserID':7},'User':{'7':{'LoginName':'example@github'}},'AuthURL':'SECRET_URL','Peer':{'SECRET_PEER':{}}}), 'SECRET_DIAGNOSTIC')
        with patch('tailscale_setup.sys.platform','darwin'),patch('tailscale_setup.shutil.which',return_value='/test/tailscale'),patch('tailscale_setup.subprocess.run',return_value=response) as runner:
            result=ts.observe()
        self.assertEqual(runner.call_args.args[0],['/test/tailscale','status','--json'])
        self.assertTrue(result['account_matches']);self.assertNotIn('SECRET',json.dumps(result))
        self.assertEqual(ts.snapshot()['records'],{})
    def test_ssh_apply_preserves_user_config_and_is_idempotent(self):
        self.save();ssh=self.home/'.ssh';ssh.mkdir();existing='Host existing\n    HostName existing.example\n';(ssh/'config').write_text(existing)
        with patch('tailscale_setup.Path.home',return_value=self.home):
            ts.apply_ssh();once=(ssh/'config').read_text();ts.apply_ssh()
        self.assertIn(existing,once);self.assertEqual((ssh/'config').read_text(),once)
        self.assertTrue(list(ssh.glob('config.bak.*')))
        self.assertIn('Include ~/.config/dotfiles/tailscale/ssh.config',(ssh/'config').read_text())
    def test_apply_preserves_existing_legacy_symlink_contents_and_source(self):
        self.save();source=self.home/'private-repo/links/ssh/config';source.parent.mkdir(parents=True)
        contents='Host old-server\n    HostName old.example\n    User olduser\n'
        source.write_text(contents);ssh=self.home/'.ssh';ssh.mkdir();(ssh/'config').symlink_to(source)
        with patch('tailscale_setup.Path.home',return_value=self.home):ts.apply_ssh()
        self.assertFalse((ssh/'config').is_symlink())
        self.assertIn(contents,(ssh/'config').read_text())
        self.assertEqual(source.read_text(),contents)
        self.assertTrue(any(item.is_symlink() for item in ssh.glob('config.bak.*')))
    def test_import_exact_commit_no_network_and_no_extra_state_leak(self):
        outputs=['a'*40,'Host example-wsl\n HostName example.test.ts.net\n User example\n',json.dumps({'tailscale':{'login':'example@github','token':'SECRET'}}),'256 SHA256:'+'A'*43+' (ED25519)']
        with patch('tailscale_setup.subprocess.run',side_effect=[subprocess.CompletedProcess([],0,value,'') for value in outputs]) as runner:
            result=ts.import_private(str(self.home),'origin/main')
        self.assertEqual(result['source']['commit'],'a'*40)
        self.assertNotIn('SECRET',json.dumps(result))
        for call in runner.call_args_list:self.assertNotIn('fetch',call.args[0])
        self.assertFalse(ts.root().exists())
if __name__=='__main__':unittest.main(verbosity=2)
