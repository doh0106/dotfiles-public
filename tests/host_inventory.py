#!/usr/bin/env python3
"""Existing configuration adoption must never rewrite policy or touch credentials."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
import host_inventory as inventory


class HostInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name).resolve()
        self.env=patch.dict(os.environ,{'HOME':str(self.home),'GIT_CONFIG_NOSYSTEM':'1'});self.env.start();self.addCleanup(self.env.stop)
        self.files={}
        self.write('.gitconfig','[include]\n path = policy/config\n')
        self.write('policy/config','''[user]
 name =
 email =
 useConfigOnly = true
[includeIf "hasconfig:remote.*.url:https://git.example.org/personal/**"]
 path = personal.gitconfig
[includeIf "hasconfig:remote.*.url:git@personal-git:personal/**"]
 path = personal.gitconfig
[includeIf "gitdir/i:~/Work/"]
 path = work.gitconfig
''')
        self.write('policy/personal.gitconfig','[user]\n name = Personal Example\n email = personal@example.org\n')
        self.write('policy/work.gitconfig','[user]\n name = Work Example\n email = work@example.org\n')
        self.write('.ssh/config','''Host personal-git
 HostName git.example.org
 User git
 IdentityFile ~/.ssh/private-secret
Host server
 HostName server.example.org
 User dev
 ProxyCommand touch SHOULD_NOT_RUN
Include ~/.ssh/config.d/*.conf
Host *
 IdentitiesOnly yes
Match exec "touch SHOULD_NOT_RUN"
 User unexpected
''')
        self.write('.ssh/config.d/additional.conf','Host other-server\n HostName other.example.org\n User example\n')
        self.write('.ssh/private-secret','DO_NOT_READ_PRIVATE_KEY')
        self.write('.zshrc','''export ZSH="$HOME/.oh-my-zsh"
ZSH_THEME="robbyrussell"
export A_SECRET_VALUE=DO_NOT_EXPOSE_THIS
source "$(touch SHOULD_NOT_RUN)"
''')

    def write(self,name,text):
        path=self.home/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
        self.files[path]=path.read_bytes()
        return path

    def assert_sources_unchanged(self):
        for path,contents in self.files.items():self.assertEqual(path.read_bytes(),contents,str(path))
        self.assertFalse((self.home/'SHOULD_NOT_RUN').exists())

    def test_discovery_keeps_remote_and_folder_rules_and_never_executes_configs(self):
        original_read=Path.read_text
        def guarded(path,*args,**kwargs):
            if path.name=='private-secret':raise AssertionError('private key was read')
            return original_read(path,*args,**kwargs)
        with patch.object(Path,'read_text',guarded):state=inventory.observe()
        git=[item for item in state['candidates'] if item['category']=='git']
        self.assertEqual(len(git),2)
        self.assertTrue(all(item['label']=='Git 작성자' for item in git))
        personal=next(item for item in git if item['details']['author']=='Personal Example')
        self.assertEqual(len(personal['details']['conditions']),2)
        self.assertTrue(all(rule.startswith('hasconfig:remote.') for rule in personal['details']['conditions']))
        work=next(item for item in git if item['details']['author']=='Work Example')
        self.assertEqual(work['details']['conditions'],['gitdir/i:~/Work/'])
        self.assertNotIn('DO_NOT_EXPOSE_THIS',json.dumps(state));self.assertNotIn('DO_NOT_READ_PRIVATE_KEY',json.dumps(state))
        self.assertFalse(inventory.store().parent.exists())
        self.assertTrue(state['ssh']['warnings'])
        self.assert_sources_unchanged()

    def test_import_remove_and_repeat_only_update_protected_reference_registry(self):
        state=inventory.observe();ids=[item['id'] for item in state['candidates']]
        imported=inventory.register(ids,state['revision'])
        self.assertEqual(len(imported['references']),len(ids))
        self.assertTrue(all(ref['status']=='current' for ref in imported['references']))
        self.assertEqual(inventory.store().stat().st_mode&0o777,0o600)
        self.assertEqual(inventory.store().parent.stat().st_mode&0o777,0o700)
        self.assertFalse((inventory.store().parent/'settings.json').exists())
        stored=json.loads(inventory.store().read_text())
        self.assertNotIn('details',stored['references'][0])
        repeated=inventory.register(ids,imported['revision'])
        self.assertEqual(len(repeated['references']),len(ids))
        removed=inventory.register(ids,repeated['revision'],remove=True)
        self.assertEqual(removed['references'],[])
        self.assert_sources_unchanged()

    def test_stale_source_and_stale_window_are_rejected_and_changed_source_visible(self):
        state=inventory.observe();ident=state['candidates'][0]['id']
        imported=inventory.register([ident],state['revision'])
        with self.assertRaises(ValueError):inventory.register([ident],state['revision'])
        path=self.home/'policy/personal.gitconfig';path.write_text('[user]\n name = Updated\n email = personal@example.org\n')
        changed=inventory.observe()
        self.assertEqual(changed['references'][0]['status'],'changed')
        with self.assertRaises(ValueError):inventory.register([ident],imported['revision'])
        updated=inventory.register([ident],changed['revision'])
        self.assertEqual(updated['references'][0]['status'],'current')

    def test_missing_sources_and_corrupt_registry_fail_closed_without_destroying_data(self):
        state=inventory.observe();item=next(c for c in state['candidates'] if c['category']=='shell')
        imported=inventory.register([item['id']],state['revision'])
        (self.home/'.zshrc').unlink()
        self.assertEqual(inventory.observe()['references'][0]['status'],'missing')
        inventory.store().write_text('corrupt registry');before=inventory.store().read_bytes()
        state=inventory.observe();self.assertTrue(state['warnings'])
        with self.assertRaises(ValueError):inventory.register([state['candidates'][0]['id']],state['revision'])
        self.assertEqual(inventory.store().read_bytes(),before)

    def test_design_preview_never_discovers_real_configuration(self):
        with patch.object(inventory,'git_configuration',side_effect=AssertionError('real discovery')):
            state=inventory.observe(preview=True)
        self.assertEqual(state['candidates'],[]);self.assertEqual(state['tools'],[])

    def test_credential_include_outside_home_and_arbitrary_ids_not_read_or_imported(self):
        self.write('secret.netrc','NOT_A_CONFIG_SECRET')
        self.write('.gitconfig','[include]\n path = secret.netrc\n')
        state=inventory.observe();self.assertNotIn('NOT_A_CONFIG_SECRET',json.dumps(state))
        for bad in ([{}],['arbitrary-path'],['a'*20,'a'*20]):
            with self.assertRaises(ValueError):inventory.register(bad,state['revision'])
        self.assertFalse(inventory.store().exists())

    def test_http_import_csrf_and_read_only_source_boundary(self):
        repo=Path(__file__).resolve().parents[1]
        env=dict(os.environ);env.pop('GIT_CONFIG_GLOBAL',None)
        server=subprocess.Popen([sys.executable,str(repo/'bin/dashboard.py'),'--no-browser'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        import urllib.request,urllib.error
        try:
            url=server.stdout.readline().strip();self.assertTrue(url.startswith('http://127.0.0.1:'))
            with urllib.request.urlopen(url+'api/state') as response:data=json.load(response)
            state=data['host_state'];self.assertTrue(state['candidates'])
            body=json.dumps(dict(action='import',ids=[state['candidates'][0]['id']],revision=state['revision'])).encode()
            request=urllib.request.Request(url+'api/existing-settings',data=body,headers={'Content-Type':'application/json','Origin':'https://example.org'})
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
            self.assertEqual(error.exception.code,403);error.exception.close();self.assertFalse(inventory.store().exists())
            request=urllib.request.Request(url+'api/existing-settings',data=body,headers={'Content-Type':'application/json','Origin':url.rstrip('/')})
            with urllib.request.urlopen(request) as response:imported=json.load(response)
            self.assertEqual(len(imported['references']),1)
            self.assertFalse((inventory.store().parent/'settings.json').exists())
            self.assert_sources_unchanged()
        finally:server.terminate();server.communicate(timeout=5)

    def test_later_explicit_configure_preserves_legacy_shell_and_ssh_policy(self):
        repo=Path(__file__).resolve().parents[1]
        source=self.home/'legacy/links/zsh/zshrc';source.parent.mkdir(parents=True)
        source.write_text('export ORIGINAL_SHELL_SETTING=yes\nsource "$HOME/.config/dotfiles/shell.zsh"\n')
        (self.home/'.zshrc').unlink();(self.home/'.zshrc').symlink_to(source)
        integration=self.home/'legacy/shell.zsh';integration.write_text('export ORIGINAL_INTEGRATION=yes\n')
        linked=self.home/'.config/dotfiles/shell.zsh';linked.parent.mkdir(parents=True);linked.symlink_to(integration)
        ssh=self.home/'legacy/links/ssh/config';ssh.parent.mkdir(parents=True)
        ssh.write_text('Host legacy\n HostName legacy.example.org\n User original\nHost *\n AddKeysToAgent yes\n')
        (self.home/'.ssh/config').unlink();(self.home/'.ssh/config').symlink_to(ssh)
        state=inventory.observe();inventory.register([c['id'] for c in state['candidates']],state['revision'])
        before=source.read_bytes(),integration.read_bytes(),ssh.read_bytes()
        env=dict(os.environ);env.pop('GIT_CONFIG_GLOBAL',None)
        for _ in range(2):
            subprocess.run(['python3',str(repo/'bin/dashboard.py'),'configure'],env=env,capture_output=True,check=True)
        self.assertEqual(before,(source.read_bytes(),integration.read_bytes(),ssh.read_bytes()))
        self.assertTrue(linked.is_symlink());self.assertEqual(linked.resolve(),integration)
        shell=subprocess.run(['zsh','-c','source "$HOME/.zshrc"; test "$ORIGINAL_SHELL_SETTING:$ORIGINAL_INTEGRATION" = yes:yes'],env=env,capture_output=True)
        self.assertEqual(shell.returncode,0,shell.stderr)
        # OpenSSH expands ~ from the OS account, not the test HOME. Keep every
        # generated Include inside the fixture before asking it to parse config.
        for generated in [self.home/'.ssh/config',self.home/'.ssh/config.d/dotfiles.conf']:
            generated.write_text(generated.read_text().replace('~/',str(self.home)+'/'))
        effective=subprocess.check_output(['ssh','-F',str(self.home/'.ssh/config'),'-G','legacy'],env=env,text=True,stderr=subprocess.DEVNULL)
        self.assertIn('user original\n',effective);self.assertIn('addkeystoagent true\n',effective)
        self.assertEqual((self.home/'.zshrc').read_text().count('# >>> dotfiles dashboard extras >>>'),1)


if __name__=='__main__':unittest.main(verbosity=2)
