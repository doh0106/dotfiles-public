#!/usr/bin/env python3
"""Client setup metadata and fixed read-only probes; no token storage or host mutation."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import configuration as cfg

STEPS=('install','login','ssh','connect')

def root():return cfg.DATA.parent/'tailscale'
def default_target():return dict(alias='home-wsl',host='',user='',account='',client='macos' if sys.platform=='darwin' else 'linux',fingerprints='')
def validate(value):
    if not isinstance(value,dict) or set(value)!=set(default_target()):raise ValueError('접속 설정 형식 오류')
    for key in ('alias','user'):
        if not isinstance(value[key],str) or not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,63}',value[key]):raise ValueError(('SSH 별칭' if key=='alias' else '집 WSL Linux 사용자명')+'을 입력하세요. 영문자로 시작하고 영문·숫자·밑줄·하이픈을 사용할 수 있습니다.')
    if not isinstance(value['host'],str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9.-]{0,252}',value['host']):raise ValueError('Tailscale DNS 이름 또는 IPv4를 입력하세요.')
    if not isinstance(value['account'],str) or not re.fullmatch(r'[A-Za-z0-9@._+-]{1,200}',value['account']):raise ValueError('호스트와 같은 Tailscale 로그인 신원을 입력하세요.')
    if value['client'] not in ('macos','windows','linux'):raise ValueError('클라이언트 OS를 확인하세요.')
    if not isinstance(value['fingerprints'],str) or len(value['fingerprints'])>4096:raise ValueError('공개 지문 형식 오류')
    if not value['fingerprints'].strip() or any(not re.fullmatch(r'SHA256:[A-Za-z0-9+/]{43}',line.strip()) for line in value['fingerprints'].splitlines()):raise ValueError('신뢰하는 공개 지문을 SHA256:값 형태로 한 줄에 하나씩 입력하세요.')
    return value

def read():
    if root().is_symlink():raise ValueError('설정 디렉터리 symlink는 지원하지 않습니다.')
    try:
        path=root()/'settings.json'
        if path.is_symlink():raise ValueError('설정 symlink는 지원하지 않습니다.')
        value=json.loads(path.read_text())
    except FileNotFoundError:return dict(schema=1,target=None,source=None,records={})
    if not isinstance(value,dict) or value.get('schema')!=1 or not isinstance(value.get('records'),dict):raise ValueError('Tailscale 설정 파일을 확인하세요.')
    validate(value['target']);return value

def revision(data):return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(data):
    if root().is_symlink():raise ValueError('설정 디렉터리 symlink는 지원하지 않습니다.')
    root().mkdir(parents=True,exist_ok=True);root().chmod(0o700)
    cfg.atomic(root()/'settings.json',(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode())

def ssh_config(target):
    t=validate(target)
    return f'# Managed Tailscale SSH client alias\nHost {t["alias"]}\n    HostName {t["host"]}\n    User {t["user"]}\n    Port 22\n    ForwardAgent no\n    StrictHostKeyChecking ask\n    ServerAliveInterval 30\n    ServerAliveCountMax 3\nHost *\n'

def import_private(repo,ref):
    if not isinstance(repo,str) or len(repo)>2048 or ref not in ('origin/main','HEAD'):raise ValueError('비공개 저장소 경로와 ref를 확인하세요.')
    path=Path(repo).expanduser()
    if not path.is_absolute() or not path.is_dir():raise ValueError('로컬 저장소의 절대 경로를 입력하세요.')
    def git(*args):
        result=subprocess.run(['git','--no-pager','-C',str(path),*args],capture_output=True,text=True,timeout=5,env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GIT_CONFIG_NOSYSTEM='1'))
        if result.returncode or len(result.stdout)>131072:raise ValueError('지정한 ref에서 비공개 WSL 설정을 읽지 못했습니다. 저장소를 먼저 동기화하세요.')
        return result.stdout
    commit=git('rev-parse','--verify',ref+'^{commit}').strip()
    if not re.fullmatch(r'[0-9a-f]{40,64}',commit):raise ValueError('커밋 확인 실패')
    base=commit+':docs/wsl-remote-access/'
    ssh=git('show','--no-textconv',base+'config/home-wsl.sshconfig')
    fields={}
    for line in ssh.splitlines():
        parts=line.strip().split(None,1)
        if len(parts)==2 and parts[0].lower() in ('host','hostname','user'):fields[parts[0].lower()]=parts[1]
    state=json.loads(git('show','--no-textconv',base+'config/host-state.json'))
    fingerprints=re.findall(r'SHA256:[A-Za-z0-9+/]{43}',git('show','--no-textconv',base+'config/ssh-host-fingerprints.txt'))
    target=default_target();target.update(alias=fields.get('host',''),host=fields.get('hostname',''),user=fields.get('user',''),account=state.get('tailscale',{}).get('login',''),fingerprints='\n'.join(fingerprints))
    validate(target)
    return dict(target=target,source=dict(commit=commit,ref=ref,imported_at=stamp()))

def snapshot(preview=False):
    error=None
    try:data=dict(schema=1,target=None,source=None,records={}) if preview else read()
    except (ValueError,OSError):data=dict(schema=1,target=None,source=None,records={});error='Tailscale 설정 파일을 읽지 못했습니다. 기존 파일을 확인한 뒤 다시 여세요.'
    target=data['target'];rev='unreadable' if error else revision(data)
    return dict(target=target,error=error,source=data['source'],revision=rev,records=data['records'],ssh_config=ssh_config(target) if target else '',server_platform=platform.system(),server_wsl='microsoft' in platform.release().lower(),config_path=str(root()/'settings.json'))

def save(target,expected,source=None):
    validate(target)
    if source is not None and (not isinstance(source,dict) or set(source)!={'commit','ref','imported_at'} or not re.fullmatch(r'[0-9a-f]{40,64}',source['commit']) or source['ref'] not in ('origin/main','HEAD') or not isinstance(source['imported_at'],str)):raise ValueError('출처 형식 오류')
    if root().is_symlink():raise ValueError('설정 경로를 확인하세요.')
    root().mkdir(parents=True,exist_ok=True)
    with (root()/'.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);data=read()
        if expected!=revision(data):raise ValueError('Tailscale 설정이 바뀌었습니다. 다시 불러오세요.')
        # Any routing/account/client/fingerprint change invalidates historical acknowledgements.
        records=data['records'] if data['target']==target else {}
        write(dict(schema=1,target=target,source=source,records=records))
        cfg.atomic(root()/'ssh.config',ssh_config(target).encode())
    return snapshot()

def acknowledge(step,completed,expected):
    if step not in STEPS or not isinstance(completed,bool):raise ValueError('단계 형식 오류')
    if root().is_symlink():raise ValueError('설정 경로를 확인하세요.')
    root().mkdir(parents=True,exist_ok=True)
    with (root()/'.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX);data=read()
        if expected!=revision(data) or not data['target']:raise ValueError('접속 설정을 먼저 저장하거나 다시 불러오세요.')
        if completed and any(prior not in data['records'] for prior in STEPS[:STEPS.index(step)]):raise ValueError('앞 단계를 먼저 확인하세요.')
        if completed:data['records'][step]=dict(checked_at=stamp(),source='user_acknowledgement')
        else:
            for later in STEPS[STEPS.index(step):]:data['records'].pop(later,None)
        write(data)
    return snapshot()

def observe():
    data=read();target=data['target']
    if not target:raise ValueError('접속 설정을 먼저 저장하세요.')
    actual='macos' if sys.platform=='darwin' else 'windows' if sys.platform=='win32' else 'linux'
    if target['client']!=actual:return dict(scope='dashboard_server',status='different_client_os',observed_at=stamp())
    executable=shutil.which('tailscale')
    app=Path('/Applications/Tailscale.app/Contents/MacOS/Tailscale')
    if not executable and sys.platform=='darwin' and app.is_file():executable=str(app)
    if not executable:return dict(scope='dashboard_server',status='cli_not_found',observed_at=stamp())
    try:
        # Explicit user action only. Never return raw diagnostics, peers or auth URLs.
        result=subprocess.run([executable,'status','--json'],capture_output=True,text=True,timeout=8,env=dict(os.environ,SHLVL='1',TERM='dumb'))
        if len(result.stdout)>2097152:raise ValueError('oversized_status')
        state=json.loads(result.stdout);self_node=state.get('Self') or {};users=state.get('User') or {}
        user=users.get(str(self_node.get('UserID'))) or {};account=user.get('LoginName')
        status='running' if result.returncode==0 and state.get('BackendState')=='Running' else 'not_running'
        return dict(scope='dashboard_server',status=status,account=account if isinstance(account,str) else None,account_matches=account==target['account'],observed_at=stamp())
    except (OSError,ValueError,subprocess.TimeoutExpired):return dict(scope='dashboard_server',status='unavailable',observed_at=stamp())

def apply_ssh():
    data=read()
    if not data['target']:raise ValueError('접속 설정을 먼저 저장하세요.')
    actual='macos' if sys.platform=='darwin' else 'windows' if sys.platform=='win32' else 'linux'
    if data['target']['client']=='windows' or data['target']['client']!=actual:raise ValueError('선택한 클라이언트의 SSH 설정에서 안내 블록을 병합하세요. 이 서버에서는 다른 OS의 SSH 설정을 적용하지 않습니다.')
    cfg.atomic(root()/'ssh.config',ssh_config(data['target']).encode())
    import configure
    home=Path.home();(home/'.ssh').mkdir(parents=True,exist_ok=True);(home/'.ssh').chmod(0o700)
    # A narrow Include preserves the currently active Git/SSH setup. The full
    # configure workflow independently includes the same generated target file.
    configure.block(home/'.ssh/config','tailscale','Include ~/.config/dotfiles/tailscale/ssh.config\nHost *',prepend=True,preserve_legacy_contents=True)
    (home/'.ssh/config').chmod(0o600)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['apply-ssh']);parser.parse_args();apply_ssh();print('SSH Include applied; existing configuration backed up. No login or network operation performed.')
if __name__=='__main__':main()
