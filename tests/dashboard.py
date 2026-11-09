#!/usr/bin/env python3
"""Real HTTP + real Git configuration in an isolated HOME, no authentication/network."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.error
import urllib.request

repo=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='dotfiles-dashboard-') as temporary:
    home=Path(temporary);env=dict(os.environ,HOME=temporary,GIT_CONFIG_NOSYSTEM='1');env.pop('GIT_CONFIG_GLOBAL',None)
    server=subprocess.Popen(['python3',str(repo/'bin/dashboard.py'),'--no-browser'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        url=server.stdout.readline().strip();origin=url.rstrip('/');rev='new'
        assert url.startswith('http://127.0.0.1:'),server.stderr.read()
        def request(path,body=None,origin_header=origin,revision=None):
            headers={} if body is None else {'Origin':origin_header,'Content-Type':'application/json','If-Match':rev if revision is None else revision}
            req=urllib.request.Request(url+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
            with urllib.request.urlopen(req) as response:return json.load(response)
        def rejected(path,state,origin_header=origin,revision=None):
            try:request(path,state,origin_header,revision)
            except urllib.error.HTTPError as exc:assert exc.code in (400,403);return json.load(exc)['error']
            raise AssertionError('invalid request accepted')
        data=request('api/state');state=data['state'];assert state['schema']==3
        assert state['connections']==[] and all(not v['enabled'] for v in state['features'].values())
        assert not (home/'.config/dotfiles').exists(),'GET must not install or persist settings'
        control=request('api/control',{'action':'status'});assert not control['busy'];assert not (home/'.config/dotfiles').exists()
        rejected('api/control',{'action':'status'},origin_header='http://evil.invalid')
        for asset in ('','app.js','secret-workflows.js','control-center.js','style.css','navigation.js','inventory.js','record-picker.js','change-center.js','onboarding.js','environment.js','tailscale.js'):
            with urllib.request.urlopen(url+asset) as response:assert response.status==200
        state['git']['enabled']=True;state['profiles'][0].update(path=str(home/'개인 space'),author='Example',email='example@example.org')
        state['features']['zellij']['enabled']=True;state['features']['zellij']['values']['session']='example'
        state['features']['ohmyzsh']['enabled']=True
        framework=home/'.oh-my-zsh';framework.mkdir();(framework/'oh-my-zsh.sh').write_text('export OMZ_LOADED=yes\n')
        # Preview is read-only, saving generates local data, configure links only selected features.
        preview=request('api/preview',state);assert 'profile-personal.gitconfig' in preview['files'];assert not (home/'.config/dotfiles').exists()
        saved=request('api/settings',state);rev=saved['revision'];data_dir=home/'.config/dotfiles/dashboard'
        assert (data_dir/'settings.json').stat().st_mode&0o777==0o600
        assert '3600' in (data_dir/'profiles.json').read_text()
        assert not (home/'.zshrc').exists()
        subprocess.run(['python3',str(repo/'bin/dashboard.py'),'configure'],env=env,check=True,stdout=subprocess.DEVNULL)
        personal=home/'개인 space'/'project';personal.mkdir(parents=True);subprocess.run(['git','init','-q',str(personal)],env=env,check=True)
        assert subprocess.check_output(['git','-C',str(personal),'config','--get','user.email'],env=env,text=True).strip()=='example@example.org'
        assert (home/'.config/zellij/config.kdl').is_symlink();assert not (home/'.config/yazi/yazi.toml').exists()
        subprocess.run(['zsh','-c','source "$HOME/.zshrc"; [[ "$OMZ_LOADED" == yes && "$ZSH_THEME" == robbyrussell && "$DOTFILES_ZELLIJ_SESSION" == example ]]'],env=env,check=True)
        # Update/disable without reinstalling; preserve existing global identity when managed identities off.
        state['features']['zellij']['values']['session']='updated';rev=request('api/settings',state)['revision']
        result=subprocess.check_output(['zsh','-c','source "$HOME/.zshrc"; print -r -- "$DOTFILES_ZELLIJ_SESSION"'],env=env,text=True);assert result.strip()=='updated'
        state['features']['zellij']['enabled']=False;state['git']['enabled']=False;rev=request('api/settings',state)['revision']
        subprocess.run(['python3',str(repo/'bin/dashboard.py'),'configure'],env=env,check=True,stdout=subprocess.DEVNULL)
        assert not (home/'.config/zellij/config.kdl').exists()
        subprocess.run(['git','config','--global','user.email','existing@example.org'],env=env,check=True)
        assert subprocess.check_output(['git','-C',str(personal),'config','--get','user.email'],env=env,text=True).strip()=='existing@example.org'
        # Malformed fields, nested roots, command injection fields, CSRF, and stale writers fail before writes.
        before=(data_dir/'settings.json').read_bytes()
        rejected('api/settings',state,'https://example.org');rejected('api/settings',state,revision='stale')
        bad=copy.deepcopy(state);bad['session']['keyLifetime']=0;rejected('api/settings',bad)
        bad=copy.deepcopy(state);p=copy.deepcopy(bad['profiles'][0]);p.update(id='nested',path=str(personal));bad['profiles'].append(p);rejected('api/settings',bad)
        bad=copy.deepcopy(state);bad['profiles'][0]['path']='~/bad*';rejected('api/settings',bad)
        assert (data_dir/'settings.json').read_bytes()==before
        # Existing flat settings migrate without changing data on GET; preserve company OFF and personal refs.
        legacy=dict(git={'enabled':True,'values':{'personal_dir':str(home/'personal space'),'name':'Migrated','email':'migrated@example.org','personal_key':'~/.ssh/keys/personal.pub','work_mode':'off'}},bitwarden={'enabled':True,'values':{'item':'personal-key','type':'note','lifetime':'3600'}},gh={'enabled':True,'values':{'personal_item':'personal-token','type':'note'}})
        (data_dir/'settings.json').write_text(json.dumps(legacy));original=(data_dir/'settings.json').read_bytes()
        migrated=request('api/state');assert migrated['migration_notice'];assert len(migrated['state']['profiles'])==1 and migrated['state']['profiles'][0]['id']=='personal';assert (data_dir/'settings.json').read_bytes()==original
        assert migrated['state']['connections'][0]['api']['enabled']
        rev=migrated['revision'];request('api/settings',migrated['state']);assert list(data_dir.glob('settings.json.bak.*'))
        # Compile failure during a later write must restore earlier outputs and the saved model.
        rollback='''from pathlib import Path
import sys
sys.path.insert(0,sys.argv[1])
import configuration as cfg
state,_,revision=cfg.read_settings();before={p.name:p.read_bytes() for p in cfg.DATA.iterdir() if p.is_file()}
original=cfg.atomic;failed=False
def fail_once(path,contents):
 global failed
 if path.name=='ghostty.conf' and not failed:
  failed=True;raise OSError('simulated write failure')
 original(path,contents)
cfg.atomic=fail_once;state['features']['ohmyzsh']['enabled']=not state['features']['ohmyzsh']['enabled']
try:cfg.generate(state,revision)
except OSError:pass
else:raise AssertionError('expected failure')
assert all((cfg.DATA/name).read_bytes()==value for name,value in before.items())
legacy={'ssh':{'enabled':True,'values':{'alias':'dev.old-host','host':'dev.example.org','user':'deploy','key':'~/.ssh/dev.pub'}}}
converted,_=cfg.migrate(legacy);assert 'Host dev.old-host' in cfg.compile(converted)['ssh.config']
try:cfg.migrate({'schema':999})
except ValueError:pass
else:raise AssertionError('future schema must not reset silently')
'''
        subprocess.run(['python3','-c',rollback,str(repo/'bin')],env=env,check=True)
        print('PASS: real HTTP assets/preview/save; Git identity; optional tools; migration/backup; validation; origin; stale-write protection; write rollback; server alias migration; modes')
    finally:
        server.terminate();_,errors=server.communicate(timeout=5)
        if errors:print(errors)
