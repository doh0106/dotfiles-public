#!/usr/bin/env python3
"""Real launcher processes: concurrency, stale records, origin checks and cleanup."""
import concurrent.futures
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

REPO=Path(__file__).resolve().parents[1]
SCRIPT=REPO/'bin/desktop.py'
class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='dotfiles desktop ')
        self.env=dict(os.environ,HOME=self.temp.name,BW_SESSION='do-not-inherit',GH_TOKEN='do-not-inherit')
    def command(self,*args):
        return subprocess.check_output([sys.executable,str(SCRIPT),*args],env=self.env,text=True,timeout=20).strip()
    def statefile(self):return next((Path(self.temp.name)/'.local/state/dotfiles-app').glob('*/server.json'))
    def metadata(self,url):return json.load(urllib.request.urlopen(url+'api/desktop',timeout=3))
    def post(self,url,action,instance,origin=None):
        r=urllib.request.Request(url+'api/desktop/'+action,data=b'',headers={'Origin':origin or url.rstrip('/'),'X-Dotfiles-Instance':instance})
        return urllib.request.urlopen(r,timeout=3)
    def tearDown(self):
        self.command('stop')
        time.sleep(.3)
        self.temp.cleanup()
    def test_concurrent_launch_reuses_server_and_explicit_stop(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            urls=list(pool.map(lambda _:self.command('launch','--no-open'),range(2)))
        self.assertEqual(urls[0],urls[1]);url=urls[0];meta=self.metadata(url)
        state=json.loads(self.statefile().read_text())
        self.assertEqual(self.statefile().stat().st_mode&0o777,0o600)
        self.assertFalse((Path(self.temp.name)/'.config/dotfiles/dashboard/settings.json').exists())
        env=Path('/proc')/str(state['pid'])/'environ'
        if env.is_file():
            raw=env.read_bytes();self.assertNotIn(b'BW_SESSION=',raw);self.assertNotIn(b'GH_TOKEN=',raw)
        with self.assertRaises(urllib.error.HTTPError) as rejected:self.post(url,'stop',meta['instance'],'https://other.example')
        self.assertEqual(rejected.exception.code,403)
        with self.assertRaises(urllib.error.HTTPError):self.post(url,'stop','wrong-instance')
        self.metadata(url)
        self.command('stop')
        for _ in range(30):
            if not list((Path(self.temp.name)/'.local/state/dotfiles-app').glob('*/server.json')):break
            time.sleep(.1)
        new=self.command('launch','--no-open')
        self.assertNotEqual(meta['instance'],self.metadata(new)['instance'])
    def test_stale_record_replaced_and_idle_server_exits(self):
        url=self.command('launch','--no-open');statefile=self.statefile();self.command('stop');time.sleep(.4)
        statefile.write_text(json.dumps({'port':1,'instance':'stale','repository':str(REPO)}))
        url=self.command('launch','--no-open','--idle-seconds','1')
        self.assertTrue(self.metadata(url)['desktop'])
        for _ in range(40):
            if not statefile.exists():break
            time.sleep(.1)
        self.assertFalse(statefile.exists())

if __name__=='__main__':unittest.main(verbosity=2)
