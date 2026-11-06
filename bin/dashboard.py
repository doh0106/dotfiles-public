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
import tool_catalog
import runbook
import setup_progress
import tailscale_setup
from environment_bridge import bridge

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
    if any(c['method']=='ssh' for c in active):required.update(('ssh','ssh-add','ssh-keygen'))
    if any(creds.get(ref,{}).get('source')=='bitwarden' for ref in references):required.add('bw')
    required.update(c['api']['tool'] for c in active if c['api']['enabled'])
    rows=[]
    for command in sorted(required):
        ready=shutil.which(command) is not None
        instructions=[]
        if not ready:
            packages={'git':'git','bash':'bash','zsh':'zsh','gh':'gh','ssh':'openssh-client','ssh-add':'openssh-client','ssh-keygen':'openssh-client'}
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
    rows.extend(tool_catalog.plan(state,REPO))
    configure=shlex.join(['python3',str(REPO/'bin/dashboard.py'),'configure'])
    return dict(dependencies=rows,configure=configure,workflow=runbook.build(state,rows,REPO,DATA),notes=[
        '저장은 로컬 설정 파일을 생성합니다. 설치·configure·로그인은 사람이 또는 AI가 안내에 따라 실행합니다.',
        'Bitwarden 상태는 서버에서 자동 조회하지 않습니다. 터미널의 bw status 결과에 맞는 분기만 실행하세요.',
        '기존 remote URL은 자동 변경하지 않습니다. SSH/HTTPS 방식을 바꾸면 git remote set-url origin URL로 별도 변경하세요.',
        'linked worktree는 원본 저장소의 gitdir 프로필을 따릅니다.',
    ])


def auth_status():
    try:
        probe=subprocess.run(['ssh-add','-l'],capture_output=True,text=True,timeout=2)
        agent='키 있음' if probe.returncode==0 else '연결됨 · 키 없음' if probe.returncode==1 else '연결 안 됨'
    except (OSError,subprocess.TimeoutExpired):agent='조회 불가'
    return dict(agent=agent,vault='자동 조회 안 함',scope='이 대시보드 서버 프로세스 기준입니다. 다른 터미널의 agent·vault 상태와 다를 수 있습니다.')


def snapshot(state=None,migrated=None,revision=None,design_preview=False,catalog_url=None):
    if state is None and design_preview:
        state=defaults();revision='design-preview'
        state['profiles'][0].update(name='개인 프로젝트 · 예시',path='~/personal/',author='Example',email='example@example.org')
        state['connections']=[dict(id='example-github',name='개인 GitHub · 예시',profile=state['profiles'][0]['id'],provider='github',host='github.com',kind='git',enabled=False,method='ssh',sshUser='git',publicKey='~/.ssh/keys/example.pub',credential='',api=dict(enabled=False,tool='gh',credential='',host=''))]
    if state is None:state,migrated,revision=cfg.read_settings()
    try:files=cfg.compile(state);validation_error=''
    except (ValueError,TypeError,KeyError) as exc:files={};validation_error=str(exc)
    definitions=copy.deepcopy(features.DEFINITIONS)
    for f in definitions:
        f['installed']=features.installed(f,state['features'])
        f['dependencies']=tool_catalog.status(f['id'],state)
    return dict(state=state,revision=revision if revision is not None else cfg.revision(),definitions=definitions,plan=plan(state),files=files,environment='설계 미리보기 · 예시 설정' if design_preview else platform.node()+' · '+platform.system(),data_directory='메모리의 예시 설정 · 저장 불가' if design_preview else str(DATA),auth_status=dict(agent='미리보기 · 조회 안 함',vault='미리보기 · 조회 안 함',scope='실제 인증 상태를 조회하지 않습니다.') if design_preview else auth_status(),shared_environment=dict(availability='unavailable') if design_preview else bridge.status(),tailscale=tailscale_setup.snapshot(design_preview),tailscale_apply_command=shlex.join(["python3",str(REPO/"bin/tailscale_setup.py"),"apply-ssh"]),setup_progress=setup_progress.status(state,design_preview),design_preview=design_preview,design_catalog_url=catalog_url,migration_notice='기존 설정을 새 구조로 불러왔습니다. 저장 전 검토하세요. 첫 저장 시 원본 설정을 백업합니다.' if migrated else '',validation_error=validation_error)


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
            if path=='/api/state':self.reply(200,snapshot(design_preview=getattr(self.server,'design_preview',False),catalog_url=getattr(self.server,'design_catalog_url',None)))
            elif path in ('/','/index.html','/app.js','/environment.js','/desktop.js','/style.css','/design/dashboard-design.js','/design/preview.js','/design/preview.css','/onboarding.js','/tailscale.js','/design/design-inspector.js','/design/design-inspector.css'):
                file=REPO/'dashboard'/('index.html' if path in ('/','/index.html') else path[1:]);self.reply(200,file.read_bytes(),{'html':'text/html','js':'application/javascript','css':'text/css'}[file.suffix[1:]]+'; charset=utf-8')
            else:self.reply(404,{'error':'찾을 수 없습니다.'})
        except (ValueError,OSError,KeyError,TypeError) as exc:self.reply(400,{'error':'설정 읽기 실패: '+str(exc)})
    def do_POST(self):
        origin='http://127.0.0.1:'+str(self.server.server_port)
        if not self.valid_host() or self.headers.get('Origin')!=origin:self.reply(403,{'error':'이 대시보드의 동일 출처 요청만 허용합니다.'});return
        if getattr(self.server,'design_preview',False) and self.path!='/api/preview':
            self.reply(403,{'error':'설계 미리보기에서는 설정 저장·인증 실행을 하지 않습니다.'});return
        if self.path=='/api/tailscale':
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=16384:raise ValueError('요청 크기 오류')
                request=json.loads(self.rfile.read(size))
                if not isinstance(request,dict):raise ValueError('요청 형식 오류')
                action=request.get('action')
                if action=='import' and set(request)=={'action','repository','ref'}:result=tailscale_setup.import_private(request['repository'],request['ref'])
                elif action=='save' and set(request)=={'action','target','revision','source'}:result=tailscale_setup.save(request['target'],request['revision'],request['source'])
                elif action=='acknowledge' and set(request)=={'action','step','completed','revision'}:result=tailscale_setup.acknowledge(request['step'],request['completed'],request['revision'])
                elif action=='observe' and set(request)=={'action'}:result=tailscale_setup.observe()
                else:raise ValueError('지원하지 않는 Tailscale 요청')
                self.reply(200,result)
            except ValueError as exc:self.reply(400,{'error':str(exc)})
            except (KeyError,TypeError,OSError,subprocess.TimeoutExpired):self.reply(400,{'error':'Tailscale 요청을 처리하지 못했습니다. 설정·출처·앞 단계·다른 창의 변경 여부를 확인하세요.'})
            return
        if self.path=='/api/setup-progress':
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=262144:raise ValueError('요청 크기 오류')
                request=json.loads(self.rfile.read(size))
                if not isinstance(request,dict) or set(request)!={'step','completed','state'}:raise ValueError('설정 단계 요청 형식 오류')
                result=setup_progress.record(request['step'],request['completed'],request['state'],self.headers.get('If-Match'))
                self.reply(200,{'setup_progress':result})
            except (ValueError,TypeError,KeyError,OSError) as exc:self.reply(400,{'error':str(exc)})
            return
        if self.path=='/api/environment':
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=8192:raise ValueError('invalid_environment_request')
                request=json.loads(self.rfile.read(size))
                if not isinstance(request,dict) or set(request)-{'action','workspace'}:raise ValueError('invalid_environment_request')
                if request.get('action')=='observe':result=bridge.status(request.get('workspace'))
                elif request.get('action')=='open_services' and 'workspace' not in request:result=bridge.open_services()
                else:raise ValueError('invalid_environment_action')
                self.reply(200,result)
            except (ValueError,OSError):self.reply(400,{'error':'환경 요청을 처리하지 못했습니다.'})
            return
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
            self.reply(200,snapshot(state,revision=saved_revision,design_preview=getattr(self.server,'design_preview',False),catalog_url=getattr(self.server,'design_catalog_url',None)))
        except (ValueError,TypeError,KeyError,OSError) as exc:self.reply(400,{'error':str(exc)})


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',nargs='?',default='serve',choices=['serve','configure','plan']);parser.add_argument('--port',type=int,default=0);parser.add_argument('--no-browser',action='store_true');parser.add_argument('--design-preview',action='store_true');parser.add_argument('--design-catalog-url');args=parser.parse_args()
    if args.design_preview and (args.action!='serve' or not args.design_catalog_url):parser.error('--design-preview requires serve and --design-catalog-url')
    if args.design_catalog_url:
        parsed=urlsplit(args.design_catalog_url)
        if parsed.scheme not in ('http','https') or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:parser.error('Use an HTTP(S) catalog URL without credentials, query or fragment')
    if args.action in ('configure','plan'):
        state,_,revision=cfg.read_settings();cfg.validate(state)
        if args.action=='configure':
            cfg.generate(state,revision);subprocess.run(['bash',str(REPO/'bin/bootstrap.sh')],check=True)
        else:print(json.dumps(plan(state),ensure_ascii=False,indent=2))
        return
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler);url='http://127.0.0.1:'+str(server.server_port)+'/'
    server.design_preview=args.design_preview;server.design_catalog_url=args.design_catalog_url
    print(url,flush=True)
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close();bridge.close()

if __name__=='__main__':main()
