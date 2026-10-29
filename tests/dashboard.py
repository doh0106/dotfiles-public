#!/usr/bin/env python3
"""Test the real local HTTP API and configuration in an isolated home."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request
import urllib.error

repo=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='dashboard-test-') as directory:
    home=Path(directory);env=dict(os.environ,HOME=directory,GIT_CONFIG_NOSYSTEM='1')
    env.pop('GIT_CONFIG_GLOBAL',None)
    process=subprocess.Popen(['python3',str(repo/'bin/dashboard.py'),'--no-browser'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        url=process.stdout.readline().strip();origin=url.rstrip('/')
        def request(path, body=None, origin_header=origin):
            headers={} if body is None else {'Origin':origin_header,'Content-Type':'application/json'}
            req=urllib.request.Request(url+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
            with urllib.request.urlopen(req) as response:return json.load(response)
        snap=request('api/state');assert all(not f['enabled'] for f in snap['features'])
        assert not (home/'.config/dotfiles').exists(),'opening dashboard must not install settings'
        state={f['id']:{'enabled':False,'values':{x['key']:x['value'] for x in f['fields']}} for f in snap['features']}
        state['git']['enabled']=True;state['git']['values'].update(name='Example Developer',email='dev@example.com')
        state['zellij']['enabled']=True;state['zellij']['values']['session']='example'
        state['ssh']['enabled']=True;state['ssh']['values'].update(host='example.org',user='developer')
        # First-install authentication must follow configure and a fresh shell.
        state['bitwarden']['enabled']=True
        saved=request('api/settings',state)
        bitwarden=next(row for row in saved['plan']['features'] if row['name']=='Bitwarden')
        assert not any(line.startswith(('bws','bw login')) for line in bitwarden['steps'])
        assert any(line.startswith('bws') for line in saved['plan']['post_configure'])
        state['bitwarden']['enabled']=False
        saved=request('api/settings',state)
        data=home/'.config/dotfiles/dashboard'
        assert (data/'settings.json').stat().st_mode&0o777==0o600
        assert 'Host workstation' in (data/'ssh.config').read_text()
        assert not (home/'.zshrc').exists(),'save must not run bootstrap'
        for f in saved['features']:
            if f['enabled'] and f['installed']:
                row=next(x for x in saved['plan']['features'] if x['name']==f['name'])
                assert not any('apt-get install' in s or 'brew install' in s for s in row['steps'])
        for bad in [dict(state,bad={}),dict(state,ssh={'enabled':True,'values':dict(state['ssh']['values'],host='example.org\nProxyCommand evil')})]:
            try:request('api/settings',bad);raise AssertionError('invalid configuration accepted')
            except urllib.error.HTTPError as exc:assert exc.code==400
        try:request('api/settings',state,'https://example.com');raise AssertionError('foreign Origin accepted')
        except urllib.error.HTTPError as exc:assert exc.code==403
        subprocess.run(['git','config','--global','user.email','existing@example.com'],env=env,check=True)
        subprocess.run(['python3',str(repo/'bin/dashboard.py'),'configure'],env=env,check=True,stdout=subprocess.DEVNULL)
        email=subprocess.check_output(['git','-C','/tmp','-c','remote.origin.url=https://github.com/doh0106/example.git','config','--get','user.email'],env=env,text=True).strip()
        assert email=='dev@example.com'
        assert (home/'.config/zellij/config.kdl').is_symlink()
        assert not (home/'.config/yazi/yazi.toml').exists()
        result=subprocess.check_output(['zsh','-c','source "$HOME/.zshrc"; print -r -- "$DOTFILES_ZELLIJ_SESSION"; (( ${+functions[zj]} )) && (( ! ${+functions[bws]} ))'],env=env,text=True)
        assert result.strip()=='example'
        # Reconfigure an already-enabled feature and then disable it without reinstalling.
        state['zellij']['values']['session']='updated';request('api/settings',state)
        result=subprocess.check_output(['zsh','-c','source "$HOME/.zshrc"; print -r -- "$DOTFILES_ZELLIJ_SESSION"'],env=env,text=True)
        assert result.strip()=='updated'
        state['zellij']['enabled']=False;request('api/settings',state)
        subprocess.run(['python3',str(repo/'bin/dashboard.py'),'configure'],env=env,check=True,stdout=subprocess.DEVNULL)
        assert not (home/'.config/zellij/config.kdl').exists()
        subprocess.run(['zsh','-c','source "$HOME/.zshrc"; (( ! ${+functions[zj]} ))'],env=env,check=True)
        state['git']['enabled']=False;request('api/settings',state)
        subprocess.run(['python3',str(repo/'bin/dashboard.py'),'configure'],env=env,check=True,stdout=subprocess.DEVNULL)
        existing=subprocess.check_output(['git','-C','/tmp','-c','remote.origin.url=https://github.com/doh0106/example.git','config','--get','user.email'],env=env,text=True).strip()
        assert existing=='existing@example.com','disabled Git feature must preserve existing identity'
        print('PASS: defaults off; HTTP save; local file permissions; configure; feature update/disable; installation detection; input and origin validation')
    finally:
        process.terminate();process.communicate(timeout=5)
