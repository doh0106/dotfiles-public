#!/usr/bin/env python3
"""Optional tools: selection, transitive dependencies, safe migration and installer guards."""
import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
import configuration as cfg
import features
import tool_catalog as tools
import runbook
REPO=Path(__file__).resolve().parents[1]

class ToolTests(unittest.TestCase):
    def test_old_schema3_preserves_settings_and_disables_new_tools(self):
        original=cfg.defaults()
        for key in list(original['features']):
            if key not in ('ohmyzsh','zoxide','zellij','colors','yazi','nvm'):del original['features'][key]
        del original['features']['nvm']['values']['node']
        original['features']['zoxide']['enabled']=True
        before=copy.deepcopy(original);upgraded,changed=cfg.migrate(original)
        self.assertTrue(changed);self.assertEqual(original,before);cfg.validate(upgraded)
        self.assertTrue(upgraded['features']['zoxide']['enabled'])
        self.assertTrue(all(not upgraded['features'][k]['enabled'] for k in set(upgraded['features'])-set(before['features'])))
        self.assertEqual(upgraded['features']['nvm']['values']['node'],'lts/*')
        self.assertFalse(cfg.migrate(upgraded)[1])
    def test_only_selected_tools_and_zi_dependency(self):
        state=cfg.defaults()
        self.assertEqual(tools.plan(state,REPO),[])
        state['features']['zoxide']['enabled']=True
        with patch.object(tools.shutil,'which',side_effect=lambda c:'/bin/zoxide' if c=='zoxide' else None):
            rows=tools.plan(state,REPO)
        self.assertEqual([r['id'] for r in rows],['zoxide','fzf'])
        self.assertTrue(rows[0]['installed']);self.assertFalse(rows[1]['installed'])
        self.assertIn('install-tool.sh fzf',rows[1]['commands'][0])
        state['features']['fzf']['enabled']=True
        with patch.object(tools.shutil,'which',return_value='/bin/fake'):
            rows=tools.plan(state,REPO)
        self.assertEqual(sum(r['id']=='fzf' for r in rows),1)
        self.assertTrue(all(not r['commands'] for r in rows))
    def test_existing_nvm_missing_node_gets_install_step(self):
        state=cfg.defaults();state['features']['nvm']['enabled']=True;state['features']['gemini']['enabled']=True
        with patch.object(features,'installed',side_effect=lambda f,s:f['id']=='nvm'),patch.object(tools,'node_ready',return_value=False):
            rows=tools.plan(state,REPO)
        ids=[r['id'] for r in rows]
        self.assertLess(ids.index('node'),ids.index('gemini'))
        self.assertTrue(rows[0]['installed']);self.assertTrue(next(r for r in rows if r['id']=='node')['commands'])
        self.assertIn('DOTFILES_NODE_VERSION',features.compile(state['features'],Path('/tmp'),False,set())['enabled.zsh'])
    def test_ohmyzsh_uses_selected_directory_and_cli_can_use_system_node(self):
        state=cfg.defaults();state['features']['ohmyzsh'].update(enabled=True,values={'dir':'/tmp/framework space','theme':'minimal'})
        state['features']['gemini']['enabled']=True
        with patch.object(features,'installed',return_value=False),patch.object(tools,'system_node_ready',return_value=True):rows=tools.plan(state,REPO)
        self.assertIn("'/tmp/framework space'",rows[0]['commands'][0]);self.assertTrue(rows[1]['commands'][0].endswith(' system'))
    def test_install_commands_reach_human_and_ai_runbook(self):
        state=cfg.defaults();state['features']['fzf']['enabled']=True
        with patch.object(features,'installed',return_value=False):rows=tools.plan(state,REPO)
        workflow=runbook.build(state,rows,REPO,Path('/tmp/settings'))
        installation=next(x for x in workflow if x['id']=='install')
        self.assertIn(rows[0]['commands'][0],[c for b in installation['blocks'] for c in b['commands']])
    def test_installer_skips_installed_tool_without_sudo_or_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);binary=home/'.local/bin/fzf';binary.parent.mkdir(parents=True);binary.write_text('#!/bin/sh\nexit 0\n');binary.chmod(0o755)
            env=dict(os.environ,HOME=tmp)
            subprocess.run(['bash',str(REPO/'bin/install-tool.sh'),'fzf'],env=env,check=True,timeout=5)
            result=subprocess.run(['bash',str(REPO/'bin/install-tool.sh'),'not-a-tool'],env=env,capture_output=True,timeout=5)
            self.assertEqual(result.returncode,2)

if __name__=='__main__':unittest.main(verbosity=2)
