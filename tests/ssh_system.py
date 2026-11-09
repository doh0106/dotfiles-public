#!/usr/bin/env python3
"""Delegation must leave OpenSSH policy, agents and legacy explicit keys intact."""
import copy,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
import configuration as cfg
import runbook
class SystemSshTests(unittest.TestCase):
 def setUp(self):
  self.state=cfg.defaults();self.state['profiles']=[]
  self.connection=cfg.new_connection('','existing');self.connection.update(enabled=True,sshMode='system',host='my-existing-alias',sshUser='',publicKey='',credential='')
  self.state['connections']=[self.connection]
 def test_system_needs_no_public_key_or_credential_and_emits_no_overrides(self):
  files=cfg.compile(self.state)
  self.assertNotIn('sshCommand',files['connection-existing.gitconfig'])
  self.assertNotIn('ssh-connection-existing.config',files)
  self.assertNotIn('Host my-existing-alias',files['ssh.config'])
  self.assertEqual(cfg.connection_refs(self.connection),[])
 def test_old_connections_keep_their_exact_key_policy(self):
  self.connection.pop('sshMode');self.connection.update(sshUser='git',publicKey='/tmp/example.pub')
  self.state['credentials']=[dict(id='old',source='agent',kind='note',item='',variable='',helper='cache',username='')];self.connection['credential']='old'
  original=cfg.compile(self.state);before=copy.deepcopy(self.state)
  explicit=copy.deepcopy(self.state);explicit['connections'][0]['sshMode']='key';after=cfg.compile(explicit)
  self.assertEqual(self.state,before)
  for name in original:
   if name!='profiles.json':self.assertEqual(original[name],after[name])
 def test_preserved_unused_vault_reference_is_not_activated(self):
  self.connection['credential']='old'
  self.state['credentials']=[dict(id='old',source='bitwarden',kind='sshkey',item='',variable='',helper='cache',username='')]
  cfg.validate(self.state)
  steps=runbook.build(self.state,[],Path('/tmp/repo'),Path('/tmp/data'));text=json.dumps(steps,ensure_ascii=False)
  self.assertNotIn('vault',[s['id'] for s in steps]);self.assertNotIn('ssh-add',text);self.assertNotIn('ssh-keygen',text)
  self.assertNotIn('bws --connection',text);self.assertNotIn('-F',text);self.assertNotIn('ssh://@',text)
 def test_server_uses_existing_alias_not_new_generated_alias(self):
  self.connection.update(kind='server',host='home-existing:2222',sshAlias='unused-new-name')
  files=cfg.compile(self.state);self.assertNotIn('Host unused-new-name',files['ssh.config'])
  text=json.dumps(runbook.build(self.state,[],Path('/tmp/repo'),Path('/tmp/data')))
  self.assertIn('ssh -G -p 2222 home-existing',text)
 def test_mixed_profile_modes_cannot_shadow_existing_ssh(self):
  self.state['profiles']=cfg.defaults()['profiles'];self.connection['profile']='personal'
  other=copy.deepcopy(self.connection);other.update(id='explicit',host='other.example',sshMode='key',sshUser='git',publicKey='/tmp/other.pub');self.state['connections'].append(other)
  with self.assertRaisesRegex(ValueError,'혼합'):cfg.validate(self.state)
 def test_auth_delegation_never_looks_up_a_key_or_vault(self):
  with tempfile.TemporaryDirectory() as temporary:
   home=Path(temporary);data=home/'.config/dotfiles/dashboard';data.mkdir(parents=True)
   runtime=json.loads(cfg.compile(self.state)['profiles.json']);(data/'profiles.json').write_text(json.dumps(runtime))
   mocks=home/'bin';mocks.mkdir()
   for command in ['bw','ssh-add','ssh-agent','ssh-keygen']:
    executable=mocks/command;executable.write_text('#!/bin/sh\necho unexpected-call >&2\nexit 91\n');executable.chmod(0o755)
   env=dict(os.environ,HOME=temporary,PATH=str(mocks))
   for action in ['prepare','load','check','needs-vault']:
    result=subprocess.run([sys.executable,str(cfg.REPO/'bin/auth.py'),action,'--connection','existing'],env=env,capture_output=True,text=True)
    self.assertEqual(result.returncode,0,result.stderr);self.assertNotIn('unexpected-call',result.stderr)
    if action=='prepare':self.assertEqual(result.stdout.strip(),'ssh-system')
    if action=='needs-vault':self.assertEqual(result.stdout.strip(),'none')
 def test_explicit_configure_keeps_original_ssh_file_and_link(self):
  with tempfile.TemporaryDirectory() as temporary:
   home=Path(temporary);data=home/'.config/dotfiles/dashboard';data.mkdir(parents=True)
   (data/'settings.json').write_text(json.dumps(self.state))
   ssh=home/'.ssh';ssh.mkdir();original=home/'original-ssh';original.write_text('Host my-existing-alias\n    HostName example.invalid\n    User existing-user\n    IdentityFile ~/.ssh/existing-key\n');(ssh/'config').symlink_to(original)
   shell=home/'.zshrc';shell.write_text('export ORIGINAL_SHELL=preserved\n')
   env=dict(os.environ,HOME=temporary,GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=str(home/'.gitconfig'))
   before=original.read_bytes()
   result=subprocess.run([sys.executable,str(cfg.REPO/'bin/dashboard.py'),'configure'],env=env,capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   self.assertTrue((ssh/'config').is_symlink());self.assertEqual((ssh/'config').readlink(),original);self.assertEqual(original.read_bytes(),before)
   self.assertNotIn('dotfiles ssh',(ssh/'config').read_text());self.assertIn('ORIGINAL_SHELL=preserved',shell.read_text())
 def test_password_metadata_is_preserved_without_automatic_supply(self):
  ref=dict(id='password',purpose='password',source='bitwarden',kind='login',item='example-login',variable='',helper='cache',username='')
  self.state['credentials']=[ref];before=copy.deepcopy(self.state)
  files=cfg.compile(self.state);self.assertEqual(self.state,before)
  self.assertEqual(json.loads(files['profiles.json'])['credentials']['password'],ref)
  self.connection.update(method='https',credential='password')
  with self.assertRaisesRegex(ValueError,'비밀번호'):cfg.validate(self.state)
 def test_declared_token_cannot_be_loaded_as_an_ssh_key(self):
  self.state['credentials']=[dict(id='token',purpose='token',source='bitwarden',kind='note',item='example-token',variable='',helper='cache',username='')]
  self.connection.update(sshMode='key',sshUser='git',publicKey='/tmp/example.pub',credential='token')
  with self.assertRaisesRegex(ValueError,'용도'):cfg.validate(self.state)
 def test_password_domain_is_not_a_token_supply_source(self):
  import auth
  from unittest.mock import patch
  ref=dict(purpose='password',source='bitwarden',kind='login',item='example-login')
  with patch('auth.fetch',side_effect=AssertionError('must not fetch a general password')):
   with self.assertRaisesRegex(RuntimeError,'토큰 공급'):auth.value(ref)
 def test_system_mode_typo_is_rejected(self):
  self.connection['sshMode']='sytem'
  with self.assertRaises(ValueError):cfg.validate(self.state)
if __name__=='__main__':unittest.main(verbosity=2)
