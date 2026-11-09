#!/usr/bin/env python3
"""Preview reads examples instead of real settings and cannot mutate credentials/settings."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.error
import urllib.request

repo=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='dotfiles-design-') as temporary:
    home=Path(temporary)
    settings=home/'.config/dotfiles/dashboard/settings.json'
    settings.parent.mkdir(parents=True)
    settings.write_text('real settings must not be read by preview')
    before=settings.read_bytes()
    server=subprocess.Popen(['python3',str(repo/'bin/dashboard.py'),'--design-preview','--design-catalog-url','http://127.0.0.1:8767/catalog-v4/','--no-browser'],env=dict(os.environ,HOME=temporary),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        url=server.stdout.readline().strip();assert url.startswith('http://127.0.0.1:')
        with urllib.request.urlopen(url+'api/state') as response:data=json.load(response)
        assert data['design_preview'] and data['state']['connections'][0]['id']=='example-github'
        assert data['shared_environment']['availability']=='unavailable'
        assert data['host_state']['scope']=='example_only' and not data['host_state']['candidates']
        for target in ('api/settings','api/environment','api/existing-settings'):
            request=urllib.request.Request(url+target,data=b'{}',headers={'Origin':url.rstrip('/'),'Content-Type':'application/json'})
            try:urllib.request.urlopen(request)
            except urllib.error.HTTPError as error:
                assert error.code==403
                assert '설계 미리보기' in json.load(error)['error']
            else:raise AssertionError('Preview mutation accepted')
        request=urllib.request.Request(url+'api/preview',data=json.dumps(data['state']).encode(),headers={'Origin':url.rstrip('/'),'Content-Type':'application/json'})
        with urllib.request.urlopen(request) as response:assert json.load(response)['design_preview']
        for asset in ('design/dashboard-design.js','design/design-inspector.js','design/preview.js','design/preview.css'):
            with urllib.request.urlopen(url+asset) as response:assert response.status==200
        assert settings.read_bytes()==before
        assert list(settings.parent.iterdir())==[settings]
        print('PASS: example-only preview, compile allowed, writes/service actions rejected, original settings untouched')
    finally:
        server.terminate();server.communicate(timeout=5)
