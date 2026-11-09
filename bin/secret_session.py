#!/usr/bin/env python3
"""Interactive terminal handoff. Vault credentials never enter the browser or files."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import urllib.request
from urllib.parse import urlsplit

def capture(args,env):
    result=subprocess.run(args,env=env,capture_output=True,text=True,timeout=120)
    if result.returncode:raise RuntimeError('Bitwarden 작업 실패. 계정·API 키·비밀번호와 CLI 서버 설정을 확인하세요.')
    return result.stdout.strip()

def connect(path):
    source=Path(path)
    info=source.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077 or info.st_size>16384:raise RuntimeError('안전한 연결 요청 파일이 아닙니다.')
    request=json.loads(source.read_text());origin=request['origin'];parsed=urlsplit(origin)
    if parsed.scheme!='http' or parsed.hostname!='127.0.0.1' or not parsed.port or parsed.path or parsed.query or parsed.fragment or parsed.username:raise RuntimeError('로컬 대시보드 주소가 아닙니다.')
    env=dict(os.environ);env.pop('BITWARDENCLI_DEBUG',None)
    if isinstance(request.get('path'),str):env['PATH']=request['path']
    if request.get('bw_appdata'):env['BITWARDENCLI_APPDATA_DIR']=request['bw_appdata']
    else:env.pop('BITWARDENCLI_APPDATA_DIR',None)
    if not shutil.which('bw',path=env.get('PATH')):raise RuntimeError('Bitwarden CLI가 없습니다. 먼저 설치하세요.')
    try:status=json.loads(capture(['bw','status'],env))['status']
    except (ValueError,KeyError):raise RuntimeError('Bitwarden 상태를 읽지 못했습니다.') from None
    if status=='unauthenticated':
        print('이 터미널에서 Bitwarden CLI에 로그인합니다. 기존에 로그인한 계정은 바꾸지 않습니다.')
        print('첫 로그인은 계정 설정의 개인 API 키를 사용합니다: https://bitwarden.com/help/personal-api-key/')
        env['BW_CLIENTID']=input('client_id: ').strip();env['BW_CLIENTSECRET']=getpass.getpass('client_secret: ')
        try:capture(['bw','login','--apikey','--nointeraction'],env)
        finally:env.pop('BW_CLIENTID',None);env.pop('BW_CLIENTSECRET',None)
        status='locked'
    session=env.get('BW_SESSION') if status=='unlocked' else None
    if not session:
        env['DOTFILES_VAULT_PASSWORD']=getpass.getpass('Bitwarden 마스터 비밀번호 (화면에 표시하지 않음): ')
        try:session=capture(['bw','unlock','--passwordenv','DOTFILES_VAULT_PASSWORD','--raw','--nointeraction'],env)
        finally:env.pop('DOTFILES_VAULT_PASSWORD',None)
    if not re.fullmatch(r'[A-Za-z0-9+/=_-]{16,4096}',session):raise RuntimeError('유효한 세션을 받지 못했습니다.')
    payload=json.dumps(dict(ticket=request['ticket'],session=session)).encode()
    post=urllib.request.Request(origin+'/api/secret-session',data=payload,headers={'Origin':origin,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(post,timeout=35) as response:json.load(response)
    except Exception:raise RuntimeError('대시보드 연결에 실패했습니다. 대시보드에서 연결 요청을 다시 만드세요.') from None
    source.unlink(missing_ok=True)
    print('대시보드 연결 완료. 화면으로 돌아가 연결 상태를 갱신하세요. 세션 값은 출력하거나 저장하지 않았습니다.')
    print('이 터미널은 잠금 해제한 세션을 이어받습니다. 대시보드 연결 해제는 이 터미널을 잠그지 않습니다.')
    env['BW_SESSION']=session;del session
    # User-owned work shell: allows existing bwgh/bwglab helpers to supply tokens.
    shell=os.environ.get('SHELL','/bin/zsh')
    if shell not in ('/bin/zsh','/bin/bash','/usr/bin/zsh','/usr/bin/bash'):shell='/bin/sh'
    os.execve(shell,[shell,'-l'],env)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--request',required=True);args=parser.parse_args()
    if not sys.stdin.isatty():raise RuntimeError('로그인 입력은 대화형 터미널에서만 진행합니다.')
    connect(args.request)
if __name__=='__main__':
    try:main()
    except (RuntimeError,OSError,ValueError,subprocess.TimeoutExpired,KeyboardInterrupt):
        print('연결을 완료하지 못했습니다. 입력값·Bitwarden CLI 상태를 확인하고 대시보드에서 다시 요청하세요.',file=sys.stderr);sys.exit(1)
