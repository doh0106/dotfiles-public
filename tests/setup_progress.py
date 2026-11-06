#!/usr/bin/env python3
"""Ensure setup review/apply acknowledgements survive reload without claiming live auth."""
import copy
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

if __name__=='__main__':unittest.main(verbosity=2)
