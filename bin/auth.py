#!/usr/bin/env python3
"""Memory-only Bitwarden -> OpenSSH/gh bridge. Never print or write secret values."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

DATA=Path.home()/'.config/dotfiles/dashboard'


def run(args, **kw):
    try:return subprocess.run(args, capture_output=True, text=True, **kw)
    except OSError:raise RuntimeError('필요한 명령을 찾을 수 없습니다: '+args[0]) from None


def configuration():
    try:return json.loads((DATA/'profiles.json').read_text())
    except (OSError,ValueError):raise RuntimeError('대시보드에서 Git 폴더 프로필을 저장하고 configure하세요.') from None


def choose(config, explicit=None):
    if explicit:
        if explicit not in config['profiles']:raise RuntimeError('설정되지 않은 프로필입니다.')
        return explicit,config['profiles'][explicit]
    common=run(['git','rev-parse','--path-format=absolute','--git-common-dir'])
    if common.returncode:raise RuntimeError('저장소 밖에서는 프로필을 명시하세요: bws personal / bwgh --profile personal …')
    gitdir=Path(common.stdout.strip()).resolve()
    matches=[name for name,p in config['profiles'].items() if Path(p['directory']).resolve() in (gitdir,*gitdir.parents)]
    if len(matches)!=1:raise RuntimeError('이 저장소의 Git 폴더 프로필이 없습니다. 대시보드의 개인·회사 폴더를 확인하세요.')
    profile=run(['git','config','--get','dotfiles.profile'])
    if profile.returncode or profile.stdout.strip()!=matches[0]:raise RuntimeError('폴더와 Git 프로필이 일치하지 않습니다. configure 또는 로컬 Git override를 확인하세요.')
    return matches[0],config['profiles'][matches[0]]


def fetch(item, kind, private=False):
    if not item:raise RuntimeError('Bitwarden 항목 이름이 설정되지 않았습니다.')
    verb='item' if kind=='sshkey' else 'password' if kind=='login' else 'notes'
    result=run(['bw','get',verb,item])
    if result.returncode:raise RuntimeError('Bitwarden 항목 조회 실패. 항목 이름·형식·잠금 상태를 확인하세요.')
    value=result.stdout.rstrip('\n')
    if kind=='sshkey':
        try:value=json.loads(value)['sshKey']['privateKey']
        except (ValueError,KeyError,TypeError):raise RuntimeError('SSH Key 항목 형식이 올바르지 않습니다.') from None
    if not isinstance(value,str) or not value.strip():raise RuntimeError('Bitwarden 항목이 비어 있습니다.')
    return value


def keys():
    result=run(['ssh-add','-L'])
    if result.returncode not in (0,1):raise RuntimeError('SSH agent에 연결할 수 없습니다.')
    # Keep public key type+blob; comments are not identity and may differ.
    return {' '.join(line.split()[:2]) for line in result.stdout.splitlines() if len(line.split())>=2}


def add(item, kind, lifetime, public_path=None):
    before=keys();expected=None
    if public_path:
        try:parts=Path(public_path).expanduser().read_text().split()
        except OSError:raise RuntimeError('프로필의 공개키 파일을 먼저 준비하세요.') from None
        if len(parts)<2:raise RuntimeError('공개키 파일 형식이 올바르지 않습니다.')
        expected=' '.join(parts[:2])
        if expected in before:
            print('이미 agent에 있는 키를 재사용합니다. 기존 키의 만료시간은 변경하지 않습니다.',file=sys.stderr)
            return []
    value=fetch(item,kind,private=True)
    try:result=run(['ssh-add','-t',str(lifetime),'-'],input=value+'\n')
    finally:del value
    after=keys();added=after-before
    if result.returncode or (expected and expected not in after):
        for public in added:run(['ssh-add','-d','-'],input=public+'\n')
        raise RuntimeError('키 로드 실패 또는 공개키 불일치. 새로 추가된 키는 제거했습니다.')
    return sorted(added)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['load','extras','gh','check']);parser.add_argument('--profile',choices=['personal','work']);parser.add_argument('arguments',nargs=argparse.REMAINDER);args=parser.parse_args()
    # REMAINDER captures options following action; parse the bridge's own prefix explicitly.
    rest=args.arguments
    explicit=args.profile
    if len(rest)>=2 and rest[0]=='--profile':explicit,rest=rest[1],rest[2:]
    if rest and rest[0]=='--':rest=rest[1:]
    config=configuration()
    if args.action in ('load','extras'):
        if run(['bw','sync']).returncode:raise RuntimeError('Bitwarden 동기화 실패. 네트워크와 로그인 상태를 확인하세요.')
    if args.action=='extras':
        path=Path.home()/'.config/dotfiles/private/secrets.json'
        try:items=json.loads(path.read_text())['secrets']
        except (OSError,ValueError,KeyError):raise RuntimeError('비공개 SSH 추가 목록을 읽을 수 없습니다.') from None
        if any(i.get('action')!='ssh-add' or i.get('bw_type') not in ('note','sshkey') for i in items):raise RuntimeError('--extras는 SSH 키 항목만 지원합니다. 파일·환경변수 복원은 고급 로더를 명시적으로 사용하세요.')
        # Stream each success so the shell can track partial successes even on failure.
        for item in items:
            for key in add(item['bw_name'],item['bw_type'],config['lifetime']):print(key,flush=True)
        return
    name,profile=choose(config,explicit)
    if args.action=='check':
        try:expected=' '.join(Path(profile['key']).expanduser().read_text().split()[:2])
        except OSError:raise RuntimeError('프로필 공개키 파일을 찾을 수 없습니다.') from None
        if expected not in keys():raise RuntimeError('선택 프로필의 키가 agent에 없습니다. bws를 실행하거나 키 만료를 확인하세요.')
        print(name+': key present (남은 TTL은 조회 불가)');return
    if args.action=='load':
        for key in add(profile['key_item'],profile['key_type'],config['lifetime'],profile['key']):print(key,flush=True)
        return
    if not config.get('gh_enabled'):raise RuntimeError('GitHub CLI 기능을 활성화하세요.')
    if not rest:rest=['help']
    if len(rest)>1 and rest[0]=='auth' and rest[1] in ('login','setup-git','refresh','switch','token'):
        raise RuntimeError('이 wrapper는 명령별 토큰 주입을 사용합니다. gh auth login/setup-git/refresh/switch/token은 실행하지 않습니다.')
    executable=shutil.which('gh')
    if not executable:raise RuntimeError('GitHub CLI(gh)를 먼저 설치하세요.')
    token=fetch(profile['token_item'],profile['token_type'])
    if '\n' in token or '\r' in token:raise RuntimeError('토큰 항목에는 토큰 한 줄만 저장하세요.')
    env=dict(os.environ)
    # Override ambient credentials so moving between profiles cannot reuse a stale token.
    for key in ('GH_TOKEN','GITHUB_TOKEN','GH_ENTERPRISE_TOKEN','GITHUB_ENTERPRISE_TOKEN','BW_SESSION','BW_PASSWORD','BW_CLIENTSECRET','BW_CLIENTID'):env.pop(key,None)
    env['GH_TOKEN']=token;env['GH_HOST']='github.com'
    try:
        result=subprocess.run([executable,*rest],env=env)
    finally:
        env.pop('GH_TOKEN',None);del token
    raise SystemExit(result.returncode)

if __name__=='__main__':
    try:main()
    except (RuntimeError,KeyError,TypeError) as exc:
        print('dotfiles: '+str(exc),file=sys.stderr);raise SystemExit(1)
