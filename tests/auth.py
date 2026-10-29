#!/usr/bin/env python3
"""Real OpenSSH agent + synthetic keys, fake vault/gh, isolated HOME. No network."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

REPO=Path(__file__).resolve().parents[1]

def run(args,env,ok=True,cwd=None):
    p=subprocess.run([str(a) for a in args],env=env,cwd=cwd,capture_output=True,text=True)
    if ok and p.returncode:raise AssertionError(f'{args}: {p.returncode}\n{p.stdout}\n{p.stderr}')
    return p

with tempfile.TemporaryDirectory(prefix='dotfiles-auth-') as temporary:
    home=Path(temporary);fixtures=home/'fixtures';fixtures.mkdir();mocks=home/'mocks';mocks.mkdir()
    env=dict(os.environ,HOME=str(home),GIT_CONFIG_NOSYSTEM='1',FIXTURES=str(fixtures))
    for k in ('GIT_CONFIG_GLOBAL','SSH_AUTH_SOCK','SSH_AGENT_PID','BW_SESSION','GH_TOKEN','GITHUB_TOKEN'):env.pop(k,None)
    for name in ('personal','work','existing'):
        run(['ssh-keygen','-q','-t','ed25519','-N','','-f',fixtures/name],env)
    (mocks/'bw').write_text('''#!/usr/bin/env python3
import sys,os,json
from pathlib import Path
args=sys.argv[1:];d=Path(os.environ['FIXTURES'])
if args==['status']:
 if os.environ.get('FAKE_BW_BAD_STATUS'):
  print('fixture-sensitive-status',file=sys.stderr);sys.exit(1)
 print(json.dumps({'status':os.environ.get('FAKE_BW_STATE','unlocked')}))
elif args==['login','--raw']:print('fixture-login-session')
elif args==['lock']:pass
elif args==['sync']:pass
elif args[:2]==['get','notes']:
 item=args[2]
 if item.endswith('-key'):print((d/item.removesuffix('-key')).read_text())
 elif item in ('personal-token','work-token'):print('fixture-'+item)
 else:sys.exit(1)
else:sys.exit(2)
''')
    (mocks/'gh').write_text('''#!/usr/bin/env python3
import os,sys,json
from pathlib import Path
with (Path(os.environ['FIXTURES'])/'gh-log').open('a') as f:f.write(json.dumps({'token':os.environ.get('GH_TOKEN'),'args':sys.argv[1:],'vault_session':os.environ.get('BW_SESSION')})+'\\n')
sys.exit(7 if sys.argv[1:]==['fail'] else 0)
''')
    agent_binary=shutil.which('ssh-agent')
    (mocks/'ssh-agent').write_text('''#!/usr/bin/env python3
import os,sys,json
from pathlib import Path
if '-s' in sys.argv:
 with (Path(os.environ['FIXTURES'])/'agent-env-log').open('a') as f:f.write(json.dumps({'vault':'BW_SESSION' in os.environ,'github':'GH_TOKEN' in os.environ})+'\\n')
os.execv('''+repr(agent_binary)+''', ['''+repr(agent_binary)+''',*sys.argv[1:]])
''')
    for f in mocks.iterdir():f.chmod(0o755)
    env['PATH']=str(mocks)+':'+env['PATH']
    # Generate using the same validated path as the dashboard without importing into the user's HOME.
    generate='''import importlib.util,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('dashboard',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
s=m.defaults();h=Path.home();f=h/'fixtures'
s['git']['enabled']=True;s['git']['values'].update(personal_dir=str(h/'personal space'),name='Personal',email='personal@example.com',personal_key=str(f/'personal.pub'),work_mode='on',work_dir=str(h/'work'),work_name='Work',work_email='work@example.com',work_key=str(f/'work.pub'))
s['bitwarden']['enabled']=True;s['bitwarden']['values'].update(item='personal-key',work_item='work-key')
s['gh']['enabled']=True;s['gh']['values'].update(personal_item='personal-token',work_item='work-token')
m.generate(s)
'''
    run(['python3','-c',generate,REPO/'bin/dashboard.py'],env)
    run(['python3',REPO/'bin/dashboard.py','configure'],env)
    personal=home/'personal space/project';work=home/'work/project';unknown=home/'unknown'
    for p in (personal,work,unknown):p.mkdir(parents=True);run(['git','init','-q',p],env)
    for p,expected in [(personal,'personal'),(work,'work')]:
        assert run(['git','config','--get','user.email'],env,cwd=p).stdout.strip()==expected+'@example.com'
        ssh=run(['git','config','--get','core.sshCommand'],env,cwd=p).stdout
        assert str(fixtures/(expected+'.pub')) in ssh and 'IdentitiesOnly=yes' in ssh
    assert not run(['git','config','--get','user.email'],env,False,cwd=unknown).stdout.strip()
    # Linked worktrees follow the main repository's Git common directory.
    run(['git','-c','commit.gpgsign=false','commit','--allow-empty','-qm','fixture'],env,cwd=personal)
    linked=home/'elsewhere'
    run(['git','worktree','add','-q','-b','linked',linked],env,cwd=personal)
    assert run(['git','config','--get','dotfiles.profile'],env,cwd=linked).stdout.strip()=='personal'
    assert run(['python3',REPO/'bin/auth.py','gh','pr','list'],env,cwd=linked).returncode==0
    login=run(['zsh','-c','source "$HOME/.zshrc"; bwl && [[ "$BW_SESSION" == fixture-login-session ]]'],env)
    assert 'fixture-login-session' not in login.stdout and 'fixture-login-session' not in login.stderr
    bad=run(['zsh','-c','source "$HOME/.zshrc"; bwu'],dict(env,FAKE_BW_BAD_STATUS='1'),False)
    assert bad.returncode!=0 and 'fixture-sensitive-status' not in bad.stderr and 'bwl' in bad.stderr
    missing=run(['zsh','-c','source "$HOME/.zshrc"; bwu'],dict(env,FAKE_BW_STATE='unauthenticated'),False)
    assert missing.returncode!=0 and 'bwl' in missing.stderr
    # Set up a shared agent with an unrelated pre-existing key.
    agent=run(['ssh-agent','-s'],env).stdout
    sock=re.search(r'SSH_AUTH_SOCK=([^;]+)',agent).group(1);pid=re.search(r'SSH_AGENT_PID=(\d+)',agent).group(1)
    shared=dict(env,SSH_AUTH_SOCK=sock,SSH_AGENT_PID=pid)
    try:
        run(['ssh-add',fixtures/'existing'],shared)
        script='''source "$HOME/.zshrc"
export BW_SESSION=fixture-session GH_TOKEN=ambient-do-not-reuse
cd "$HOME/personal space/project"
bws || exit 1
gh pr list || exit 2
[[ "$GH_TOKEN" == ambient-do-not-reuse ]] || exit 3
cd "$HOME/work/project"
bws || exit 4
gh issue list || exit 5
gh fail
[[ $? == 7 ]] || exit 6
cd "$HOME/unknown"
gh pr list >/dev/null 2>&1
[[ $? != 0 ]] || exit 7
bwgh --profile personal repo list || exit 8
bwe || exit 9
[[ -z "${BW_SESSION:-}" && -z "${GH_TOKEN:-}" && "$SSH_AUTH_SOCK" == "$EXPECTED_SOCKET" ]] || exit 10
'''
        run(['zsh','-c',script],dict(shared,EXPECTED_SOCKET=sock))
        public=run(['ssh-add','-L'],shared).stdout.splitlines()
        assert len(public)==1 and (fixtures/'existing.pub').read_text().split()[1] in public[0]
        logs=[json.loads(x) for x in (fixtures/'gh-log').read_text().splitlines()]
        assert all(x['vault_session'] is None for x in logs)
        assert [x['token'] for x in logs]==['fixture-personal-token','fixture-personal-token','fixture-work-token','fixture-work-token','fixture-personal-token']
        # Fail closed on vault lookup failure despite an ambient token.
        config=home/'.config/dotfiles/dashboard/profiles.json';data=json.loads(config.read_text());data['profiles']['personal']['token_item']='missing';config.write_text(json.dumps(data))
        old_log=(fixtures/'gh-log').read_text()
        failed=run(['zsh','-c','source "$HOME/.zshrc"; gh pr list'],dict(shared,GH_TOKEN='ambient'),False,cwd=personal)
        assert failed.returncode!=0 and (fixtures/'gh-log').read_text()==old_log
        # OpenSSH expiration really removes the newly loaded key, while retaining the existing key.
        data['lifetime']=1;config.write_text(json.dumps(data))
        run(['zsh','-c','source "$HOME/.zshrc"; bws personal'],shared)
        assert len(run(['ssh-add','-L'],shared).stdout.splitlines())==2
        time.sleep(2)
        assert len(run(['ssh-add','-L'],shared).stdout.splitlines())==1
        # Cleanup never removes a matching key that was already in the shared agent.
        run(['ssh-add',fixtures/'personal'],shared)
        run(['zsh','-c','source "$HOME/.zshrc"; bws personal && bwe'],shared)
        assert len(run(['ssh-add','-L'],shared).stdout.splitlines())==2
    finally:run(['ssh-agent','-k'],shared,False)
    # A shell-created empty agent is stopped on cleanup.
    owned_script='''source "$HOME/.zshrc"
export BW_SESSION=fixture-session GH_TOKEN=ambient
bws personal || exit 1
own_pid=$SSH_AGENT_PID
bwe || exit 2
[[ -z "${SSH_AUTH_SOCK:-}" ]]
! kill -0 "$own_pid" 2>/dev/null
'''
    result=run(['zsh','-c',owned_script],env)
    startup=json.loads((fixtures/'agent-env-log').read_text().splitlines()[-1])
    assert startup=={'vault':False,'github':False},'agent must not inherit vault or gh session credentials'
    # No secret material is persisted by the implementation (only our fixtures contain secrets).
    for p in (home/'.config/dotfiles').rglob('*'):
        if p.is_file():
            text=p.read_text()
            assert 'BEGIN OPENSSH PRIVATE KEY' not in text and 'fixture-personal-token' not in text
    print('PASS: gitdir personal/work/worktree; per-command gh token isolation; fail-closed lookup; real key expiry; shared-key preservation; owned-agent cleanup; no secret files')
