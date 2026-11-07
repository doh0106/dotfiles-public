#!/usr/bin/env python3
"""Instructions follow active settings and preserve authentication/cleanup order."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
import configuration as cfg
import runbook


class RunbookTests(unittest.TestCase):
    def setUp(self):
        self.state=cfg.defaults();self.state['git']['enabled']=True
        self.state['profiles'][0].update(author='Test',email='test@example.org',path='/tmp/example-personal')
        self.state['credentials']=[dict(id='ssh-ref',source='bitwarden',kind='note',item='my-key-item',variable='',helper='cache',username='')]
        c=cfg.new_connection('personal','my-service');c.update(name='My service',enabled=True,credential='ssh-ref',publicKey='/tmp/example-key.pub');self.state['connections']=[c]
        self.dependencies=[dict(id='git',name='git',installed=True,steps=['already installed'])]
    def build(self):
        cfg.validate(self.state)
        with patch('subprocess.run',side_effect=AssertionError('runbook must not probe/login to vault or execute commands')):
            return runbook.build(self.state,self.dependencies,Path('/tmp/repo'),Path('/tmp/settings'))
    def commands(self,stages):return [cmd for stage in stages for block in stage['blocks'] for cmd in block['commands']]
    def test_personal_bitwarden_order_and_branches(self):
        steps=self.build();ids=[s['id'] for s in steps]
        for earlier,later in zip(['save','install','configure','shell','vault','credentials','verify','cleanup'],['install','configure','shell','vault','credentials','verify','cleanup',None]):
            if later: self.assertLess(ids.index(earlier),ids.index(later))
        self.assertEqual(ids[-1],'cleanup')
        self.assertNotIn('bwe',self.commands(steps[:-1]))
        login=next(s for s in steps if s['id']=='vault')
        branches={b['when']:b['commands'] for b in login['blocks']}
        self.assertEqual(branches['status가 unauthenticated'],['bwl'])
        self.assertEqual(branches['status가 locked'],['bwu'])
        self.assertEqual(branches['status가 unlocked'],[])
        self.assertTrue(next(b for b in login['blocks'] if 'bw logout' in b['commands'])['optional'])
        commands=self.commands(steps)
        self.assertIn('bws --connection my-service',commands)
        self.assertTrue(any('ssh -F /tmp/settings/ssh-personal.config -T git@github.com'==c for c in commands))
        self.assertFalse(any(c.startswith(('gh ','bwgh ','glab ','bwglab ')) for c in commands))
        self.assertTrue(all(b['example'] for s in steps if s['id']=='clone' for b in s['blocks']))
    def test_shell_only_omits_authentication(self):
        self.state['connections']=[];self.state['credentials']=[]
        ids=[s['id'] for s in self.build()]
        self.assertFalse(set(ids)&{'vault','materials','credentials','verify','clone','cleanup'})
    def test_auth_materials_link_uses_the_connection_domain(self):
        c=self.state['connections'][0]
        self.assertEqual(next(s for s in self.build() if s['id']=='materials')['view'],'connections')
        c.update(kind='server',provider='generic',sshUser='dev',profile='')
        self.assertEqual(next(s for s in self.build() if s['id']=='materials')['view'],'servers')
        git=cfg.new_connection('personal','other-git');git.update(enabled=True,credential='ssh-ref')
        self.state['connections'].append(git)
        self.assertEqual(next(s for s in self.build() if s['id']=='materials')['view'],'overview')
    def test_https_does_not_load_or_test_ssh_keys(self):
        c=self.state['connections'][0];c.update(provider='gitlab',host='gitlab.example.org',method='https')
        self.state['credentials'][0]['username']='oauth2'
        commands=self.commands(self.build())
        self.assertIn('bws --connection my-service',commands)
        self.assertFalse(any(c.startswith(('ssh ','ssh-add ','ssh-keygen ')) for c in commands))
    def test_environment_api_needs_no_bitwarden(self):
        c=self.state['connections'][0];c.update(provider='gitlab',host='gitlab.example.org',method='https',credential='')
        c['api'].update(enabled=True,tool='glab',credential='api-env')
        self.state['credentials']=[dict(id='api-env',source='environment',kind='note',item='',variable='MY_API_TOKEN',helper='cache',username='')]
        stages=self.build();commands=self.commands(stages)
        self.assertNotIn('vault',[s['id'] for s in stages]);self.assertIn('bwglab --connection my-service auth status',commands)
        self.assertIn('unset MY_API_TOKEN',stages[-1]['blocks'][0]['commands'])
        self.assertNotIn('bwl',commands)
    def test_missing_tools_only_receive_install_instructions(self):
        command='command -v bw >/dev/null 2>&1 || brew install bitwarden-cli'
        self.dependencies.append(dict(id='bw',name='bw',installed=False,steps=[command]))
        installation=next(s for s in self.build() if s['id']=='install')
        self.assertEqual(self.commands([installation]),[command])
    def test_custom_ssh_host_and_port(self):
        self.state['connections'][0].update(provider='generic',host='code.example.org:2222',sshUser='vcs')
        stages=self.build();commands=self.commands(stages)
        self.assertIn('ssh -F /tmp/settings/ssh-personal.config -T -p 2222 vcs@code.example.org',commands)
        self.assertFalse(any('github.com' in link['url'] for s in stages for b in s['blocks'] for link in b['links']))


if __name__=='__main__':unittest.main(verbosity=2)
