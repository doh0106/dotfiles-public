#!/usr/bin/env python3
"""Ensure setup review/apply acknowledgements survive reload without claiming live auth."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bin'))
import configuration as cfg
import setup_progress as progress

class SetupProgressTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.saved=(cfg.DATA,cfg.SETTINGS)
        cfg.DATA=Path(self.tmp.name)/'dashboard';cfg.SETTINGS=cfg.DATA/'settings.json';self.state=cfg.defaults()
    def tearDown(self):
        cfg.DATA,cfg.SETTINGS=self.saved;self.tmp.cleanup()
    def test_read_never_writes_or_assumes_default_is_reviewed(self):
        self.assertFalse(any(item['done'] for item in progress.status(self.state).values()))
        self.assertFalse(cfg.DATA.exists())
    def test_reviews_survive_reload_and_only_relevant_changes_invalidate(self):
        progress.record('appearance',True,self.state,'new');progress.record('tools',True,self.state,'new')
        self.assertFalse(cfg.SETTINGS.exists())
        changed=copy.deepcopy(self.state);changed['features']['fzf']['enabled']=True
        result=progress.status(changed)
        self.assertTrue(result['appearance']['done']);self.assertFalse(result['tools']['done'])
        self.assertTrue(progress.status(self.state)['tools']['done'])
        self.assertEqual((cfg.DATA/'setup-progress.json').stat().st_mode&0o777,0o600)
    def test_application_requires_saved_exact_state_and_stale_revision_rejected(self):
        with self.assertRaises(ValueError):progress.record('apply',True,self.state,'new')
        revision=cfg.generate(self.state,'new')
        progress.record('apply',True,self.state,revision)
        changed=copy.deepcopy(self.state);changed['features']['fzf']['enabled']=True
        self.assertFalse(progress.status(changed)['apply']['done'])
        with self.assertRaises(ValueError):progress.record('shell',True,changed,revision)
        with self.assertRaises(ValueError):progress.record('auth',True,self.state,'stale')
        progress.record('apply',False,self.state,revision)
        self.assertFalse(progress.status(self.state)['apply']['done'])
    def test_preview_ignores_real_progress(self):
        progress.record('appearance',True,self.state,'new')
        self.assertFalse(progress.status(self.state,True)['appearance']['done'])
    def test_connection_then_optional_folder_rule_does_not_repeat_connection_review(self):
        connection=cfg.new_connection('', 'public-git')
        connection.update(enabled=True,method='https')
        self.state['connections']=[connection]
        progress.record('connections',True,self.state,'new')
        self.state['profiles'][0].update(path='~/projects/',author='Example',email='example@example.org')
        connection['profile']='personal'
        self.assertTrue(progress.status(self.state)['connections']['done'])
        progress.record('profiles',True,self.state,'new')
        result=progress.status(self.state)
        self.assertTrue(result['connections']['done']);self.assertTrue(result['profiles']['done'])
        connection['profile']=''
        self.assertFalse(progress.status(self.state)['profiles']['done'])
        self.assertTrue(progress.status(self.state)['connections']['done'])
        connection['host']='other.example.org'
        self.assertFalse(progress.status(self.state)['connections']['done'])
    def test_legacy_writer_review_survives_until_a_folder_assignment_is_added(self):
        old=hashlib.sha256(json.dumps({k:self.state[k] for k in ('git','profiles')},sort_keys=True,separators=(',',':')).encode()).hexdigest()
        cfg.DATA.mkdir()
        (cfg.DATA/'setup-progress.json').write_text(json.dumps({'schema':1,'steps':{'profiles':{'fingerprint':old}}}))
        self.assertTrue(progress.status(self.state)['profiles']['done'])
        self.state['connections']=[cfg.new_connection('personal','scoped')]
        self.assertFalse(progress.status(self.state)['profiles']['done'])

if __name__=='__main__':unittest.main(verbosity=2)
