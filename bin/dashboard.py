#!/usr/bin/env python3
"""Local dashboard. Saving compiles settings; installation/authentication stay explicit."""
import argparse
import copy
import json
import mimetypes
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import webbrowser
from urllib.parse import urlsplit
import configuration as cfg
import features

REPO=cfg.REPO
DATA=cfg.DATA
SETTINGS=cfg.SETTINGS
defaults=cfg.defaults
load=cfg.load
validate=cfg.validate
generate=cfg.generate

DOCS={'bw':'https://bitwarden.com/help/cli/','ohmyzsh':'https://github.com/ohmyzsh/ohmyzsh#basic-installation','gh':'https://github.com/cli/cli#installation','glab':'https://docs.gitlab.com/cli/installation/','zellij':'https://zellij.dev/documentation/installation','yazi':'https://yazi-rs.github.io/docs/installation/','nvm':'https://github.com/nvm-sh/nvm#installing-and-updating'}


def plan(state):
    active=[c for c in state['connections'] if c['enabled']]
    creds={c['id']:c for c in state['credentials']}
    references={ref for c in active for ref in ([c['credential']]+([c['api']['credential']] if c['api']['enabled'] else [])) if ref}
    required={'git','bash','zsh'}
    if any(c['method']=='ssh' for c in active):required.update(('ssh','ssh-add'))
    if any(creds.get(ref,{}).get('source')=='bitwarden' for ref in references):required.add('bw')
    required.update(c['api']['tool'] for c in active if c['api']['enabled'])
    rows=[]
    for command in sorted(required):
        ready=shutil.which(command) is not None
        instructions=[]
        if not ready:
            packages={'git':'git','bash':'bash','zsh':'zsh','ssh':'openssh-client','ssh-add':'openssh-client'}
            if sys.platform=='darwin' and shutil.which('brew') and command in ('gh','glab','bw','zsh'):
                instructions=[f'command -v {command} >/dev/null 2>&1 || brew install '+('bitwarden-cli' if command=='bw' else command)]
            elif shutil.which('apt-get') and command in packages:instructions=[f'command -v {command} >/dev/null 2>&1 || (sudo apt-get update && sudo apt-get install -y {packages[command]})']
            else:instructions=['설치 안내: '+DOCS.get(command,'OS 패키지 관리자로 '+command+' 설치')]
        rows.append(dict(id=command,name=command,installed=ready,steps=instructions or ['설치됨 · 재설치 없이 설정합니다.']))
    helpers={creds[ref]['helper'] for ref in references if creds.get(ref,{}).get('source')=='git-helper'}
    try:
        git_exec=Path(subprocess.run(['git','--exec-path'],capture_output=True,text=True,timeout=2).stdout.strip())
    except (OSError,subprocess.TimeoutExpired):git_exec=Path('/nonexistent')
    helper_docs={'cache':'https://git-scm.com/docs/git-credential-cache','manager':'https://github.com/git-ecosystem/git-credential-manager/blob/main/docs/install.md','osxkeychain':'https://git-scm.com/doc/credential-helpers','libsecret':'https://github.com/git/git/tree/master/contrib/credential/libsecret'}
    for helper in sorted(helpers):
        command='git-credential-'+helper;ready=shutil.which(command) is not None or (git_exec/command).is_file()
        rows.append(dict(id=command,name=command,installed=ready,steps=['설치됨 · 외부 helper의 보관 정책을 확인하세요.'] if ready else ['설치 안내: '+helper_docs[helper]]))
    for f in features.DEFINITIONS:
        if not state['features'][f['id']]['enabled']:continue
        ready=features.installed(f,state['features']);steps=[]
        if not ready:
            if f['id']=='zoxide' and shutil.which('apt-get'):steps=['command -v zoxide >/dev/null 2>&1 || (sudo apt-get update && sudo apt-get install -y zoxide)']
            else:steps=['설치 안내: '+DOCS.get(f['id'],'OS 패키지 관리자로 '+f['name']+' 설치')]
        if f['id']=='colors':steps.append('프로젝트 색상은 Ghostty 또는 iTerm2에서 적용됩니다.')
        rows.append(dict(id=f['id'],name=f['name'],installed=ready,steps=steps or ['설치됨 · 재설치 없이 설정합니다.']))
    connections=[]
    profiles={p['id']:p for p in state['profiles']}
    for c in active:
        prefix=shlex.join(['bws','--connection',c['id']]);steps=[];warnings=[]
        cred=creds.get(c['credential'])
        if c['method']=='ssh' and not Path(c['publicKey']).expanduser().is_file():warnings.append('공개키 파일을 '+c['publicKey']+'에 준비하세요. 이 경로에는 .pub만 두고, 개인키는 선택한 공급자에서 로드합니다.')
        refs=[creds.get(c['credential'])]+([creds.get(c['api']['credential'])] if c['api']['enabled'] else [])
        if any(ref and ref['source']=='bitwarden' for ref in refs):steps.append('bwl  # 최초 로그인/로그인 만료 시. 사용자가 직접 인증합니다.')
        steps.append(prefix+'  # '+('선택 연결의 SSH 키 준비' if c['method']=='ssh' else 'HTTPS helper에 필요한 vault 준비; SSH agent 불필요'))
        if c['kind']=='git':
            if c['method']=='ssh':
                name,port=cfg.host_parts(c['host']);url=('ssh://'+c['sshUser']+'@'+c['host']+'/OWNER/REPO.git') if port else c['sshUser']+'@'+name+':OWNER/REPO.git'
            else:url='https://'+c['host']+'/OWNER/REPO.git'
            target=str(Path(profiles[c['profile']]['path']).expanduser()/'REPO')
            steps.append(shlex.join(['git','-c','include.path='+str(DATA/('profile-'+c['profile']+'.gitconfig')),'clone',url,target]))
            steps.append('저장소 안: git config --show-origin --get user.email; git remote -v; git config --get dotfiles.profile')
        else:steps.append(shlex.join(['ssh',c.get('sshAlias') or c['id']]))
        if c['api']['enabled']:
            reference=creds.get(c['api']['credential'])
            if reference and reference['source']=='environment':warnings.append('현재 셸에 '+reference['variable']+' 토큰 환경변수를 준비하세요. 값은 이 설정에 넣지 않습니다. 작업 후 unset '+reference['variable']+'로 해제하세요.')
            steps.append(shlex.join(['bw'+c['api']['tool'],'--connection',c['id'],'auth','status']))
        if cred and cred['source']=='git-helper':warnings.append('외부 helper의 저장·만료·삭제 정책은 해당 제품에서 관리합니다. bwe가 외부 저장소의 자격증명을 지우지는 않습니다.')
        connections.append(dict(id=c['id'],name=c['name'],warnings=warnings,steps=steps))
    after=['exec zsh  # 새 셸에서 변경한 integration을 읽습니다.']
    if active:after.append('bwe  # 이 셸이 추가한 키/변수를 정리. 토큰 서버 만료·외부 helper 저장소는 별도 관리합니다.')
    return dict(dependencies=rows,connections=connections,configure=shlex.join(['python3',str(REPO/'bin/dashboard.py'),'configure']),after=after,notes=['저장은 로컬 설정 파일을 생성합니다. 설치·configure·로그인은 아래 안내를 사람이 또는 AI가 실행합니다.','Git 연결 방식을 바꿔도 기존 remote URL은 바꾸지 않습니다. git remote set-url origin <선택한 방식의 URL>로 별도 변경하세요.','linked worktree는 원본 저장소의 gitdir 프로필을 따릅니다.','SSH 공개키는 신원 선택용입니다. Git 서버의 호스트 키 신원 확인(known_hosts)은 계속 OpenSSH가 담당합니다.'])


def auth_status():
    try:
        probe=subprocess.run(['ssh-add','-l'],capture_output=True,text=True,timeout=2)
        agent='키 있음' if probe.returncode==0 else '연결됨 · 키 없음' if probe.returncode==1 else '연결 안 됨'
    except (OSError,subprocess.TimeoutExpired):agent='조회 불가'
    return dict(agent=agent,vault='자동 조회 안 함',scope='이 대시보드 서버 프로세스 기준입니다. 다른 터미널의 agent·vault 상태와 다를 수 있습니다.')


def snapshot(state=None,migrated=None,revision=None):
    if state is None:state,migrated,revision=cfg.read_settings()
    try:files=cfg.compile(state);validation_error=''
    except (ValueError,TypeError,KeyError) as exc:files={};validation_error=str(exc)
    definitions=copy.deepcopy(features.DEFINITIONS)
    for f in definitions:f['installed']=features.installed(f,state['features'])
    return dict(state=state,revision=revision if revision is not None else cfg.revision(),definitions=definitions,plan=plan(state),files=files,environment=platform.node()+' · '+platform.system(),data_directory=str(DATA),auth_status=auth_status(),migration_notice='기존 설정을 새 구조로 불러왔습니다. 저장 전 검토하세요. 첫 저장 시 원본 설정을 백업합니다.' if migrated else '',validation_error=validation_error)


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def reply(self,status,payload,kind='application/json; charset=utf-8'):
        raw=json.dumps(payload,ensure_ascii=False).encode() if kind.startswith('application/json') else payload
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Frame-Options','DENY');self.end_headers();self.wfile.write(raw)
    def valid_host(self):return self.headers.get('Host')=='127.0.0.1:'+str(self.server.server_port)
    def do_GET(self):
        if not self.valid_host():self.reply(403,{'error':'로컬 Host만 허용합니다.'});return
        path=urlsplit(self.path).path
        try:
            if path=='/api/state':self.reply(200,snapshot())
            elif path in ('/','/index.html','/app.js','/style.css'):
                file=REPO/'dashboard'/('index.html' if path in ('/','/index.html') else path[1:]);self.reply(200,file.read_bytes(),{'html':'text/html','js':'application/javascript','css':'text/css'}[file.suffix[1:]]+'; charset=utf-8')
            else:self.reply(404,{'error':'찾을 수 없습니다.'})
        except (ValueError,OSError,KeyError,TypeError) as exc:self.reply(400,{'error':'설정 읽기 실패: '+str(exc)})
    def do_POST(self):
        origin='http://127.0.0.1:'+str(self.server.server_port)
        if not self.valid_host() or self.headers.get('Origin')!=origin:self.reply(403,{'error':'이 대시보드의 동일 출처 요청만 허용합니다.'});return
        if self.path not in ('/api/settings','/api/preview'):self.reply(404,{'error':'찾을 수 없습니다.'});return
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=262144:raise ValueError('설정 요청 크기 오류')
            state=cfg.validate(json.loads(self.rfile.read(size)))
            if self.path=='/api/settings':
                expected=self.headers.get('If-Match')
                if expected is None:raise ValueError('설정 버전이 없습니다. 새로고침하세요.')
                saved_revision=cfg.generate(state,expected)
            else:saved_revision=self.headers.get('If-Match')
            self.reply(200,snapshot(state,revision=saved_revision))
        except (ValueError,TypeError,KeyError,OSError) as exc:self.reply(400,{'error':str(exc)})


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',nargs='?',default='serve',choices=['serve','configure','plan']);parser.add_argument('--port',type=int,default=0);parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    if args.action in ('configure','plan'):
        state,_,revision=cfg.read_settings();cfg.validate(state)
        if args.action=='configure':
            cfg.generate(state,revision);subprocess.run(['bash',str(REPO/'bin/bootstrap.sh')],check=True)
        else:print(json.dumps(plan(state),ensure_ascii=False,indent=2))
        return
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler);url='http://127.0.0.1:'+str(server.server_port)+'/'
    print(url,flush=True)
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
