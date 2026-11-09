#!/usr/bin/env python3
"""Supply a saved token reference to one explicit local command, never stdout/files."""
import argparse
import os
import re
import subprocess
import sys
import configuration as cfg
import auth

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--reference',required=True);parser.add_argument('command',nargs=argparse.REMAINDER);args=parser.parse_args()
    command=args.command[1:] if args.command[:1]==['--'] else args.command
    if not command:raise ValueError('-- 뒤에 토큰을 사용할 프로그램과 인수를 지정하세요.')
    state=cfg.validate(cfg.read_settings()[0]);ref=next((ref for ref in state['credentials'] if ref['id']==args.reference),None)
    if not ref or ref.get('purpose')!='token':raise ValueError('저장한 토큰 참조를 선택하세요.')
    variable=ref.get('deliveryVariable','')
    if not re.fullmatch('[A-Z][A-Z0-9_]*_TOKEN',variable):raise ValueError('토큰 공급 환경변수 이름을 설정하세요. 예: SERVICE_TOKEN')
    token=auth.value(ref)
    try:
        if not token or len(token)>65536 or any(c in token for c in ('\n','\r','\0')):raise ValueError('한 줄 토큰이 아닙니다.')
        env=dict(os.environ);env[variable]=token
        for name in list(env):
            if name in ('BW_SESSION','BW_CLIENTSECRET','DOTFILES_VAULT_PASSWORD') or name.endswith('_TOKEN') and name!=variable:env.pop(name,None)
        return subprocess.run(command,env=env).returncode
    finally:del token
if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,RuntimeError,OSError):print('토큰 공급 실패. 저장한 참조·대상 프로그램·로그인 터미널 상태를 확인하세요.',file=sys.stderr);sys.exit(1)
