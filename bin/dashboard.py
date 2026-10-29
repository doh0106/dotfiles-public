#!/usr/bin/env python3
"""Local settings editor and instruction generator. Never install packages or run snippets."""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import webbrowser

REPO = Path(__file__).resolve().parents[1]
ROOT = Path.home() / '.config/dotfiles'
DATA = ROOT / 'dashboard'
SETTINGS = DATA / 'settings.json'

def field(key, label, value='', **kw):
    return dict(key=key, label=label, value=value, **kw)

DEFINITIONS = [
 dict(id='git', name='Git identity', category='access', icon='git', command='git', desc='소유자별 커밋 이름·이메일을 선택합니다.', fields=[field('owner','GitHub 소유자','doh0106'),field('name','커밋 작성자 이름',''),field('email','커밋 이메일','',type='email')]),
 dict(id='ssh', name='SSH 연결', category='access', icon='↗', command='ssh', desc='추가 SSH 연결을 구성합니다. 개인 GitHub 별칭은 기본 제공됩니다.',fields=[field('alias','호스트 별칭','workstation'),field('host','호스트 주소'),field('user','로그인 사용자'),field('key','공개키 경로','~/.ssh/keys/workstation.pub')]),
 dict(id='bitwarden', name='Bitwarden', category='secret', icon='◇', command='bw', desc='Bitwarden 참조로 개인 SSH 키를 불러옵니다.',fields=[field('item','Bitwarden 항목 이름','personal-github-ssh-key'),field('type','항목 형식','note',options=['note','sshkey'])]),
 dict(id='zoxide', name='zoxide',category='shell',icon='z',command='zoxide',desc='z 명령으로 자주 가는 디렉터리로 이동합니다.',fields=[]),
 dict(id='zellij', name='Zellij',category='terminal',icon='▥',command='zellij',desc='zj 명령으로 프로젝트 세션을 만들거나 재연결합니다.',fields=[field('session','기본 세션 이름','',hint='비워두면 현재 폴더 이름을 사용합니다.')]),
 dict(id='colors',name='프로젝트 색상',category='terminal',icon='◐',command=None,desc='한 프로젝트의 Ghostty·iTerm2 색상 규칙을 구성합니다.',fields=[field('path','프로젝트 경로 또는 glob'),field('background','배경색','#172a36',type='color'),field('foreground','글자색','#d6edf8',type='color')]),
 dict(id='yazi',name='Yazi',category='terminal',icon='▤',command='yazi',desc='기본 탐색기 설정과 종료 위치로 이동하는 y 함수를 연결합니다.',fields=[]),
 dict(id='nvm',name='Node.js · nvm',category='shell',icon='n',command=None,desc='지정한 경로에 설치된 nvm을 읽습니다.',fields=[field('dir','nvm 설치 경로','~/.nvm')]),
]

def defaults():
    return {f['id']: {'enabled':False,'values':{x['key']:x['value'] for x in f['fields']}} for f in DEFINITIONS}

def load():
    return validate(json.loads(SETTINGS.read_text())) if SETTINGS.exists() else defaults()

def validate(raw):
    if not isinstance(raw,dict) or set(raw)!=set(defaults()): raise ValueError('기능 목록이 올바르지 않습니다.')
    for f in DEFINITIONS:
        item=raw[f['id']]
        if not isinstance(item,dict) or type(item.get('enabled')) is not bool or not isinstance(item.get('values'),dict): raise ValueError('잘못된 설정 형식')
        if set(item['values'])!={x['key'] for x in f['fields']}: raise ValueError('알 수 없는 설정 항목')
        for x in f['fields']:
            v=item['values'][x['key']]
            if not isinstance(v,str) or len(v)>1024 or any(ord(c)<32 or ord(c)==127 for c in v): raise ValueError('설정에 제어 문자 또는 너무 긴 값이 있습니다.')
            if x.get('options') and v not in x['options']: raise ValueError('지원하지 않는 옵션')
        v=item['values']
        if not item['enabled']: continue
        optional={'zellij':{'session'}}.get(f['id'],set())
        if any(not val.strip() for k,val in v.items() if k not in optional): raise ValueError(f"{f['name']}: 비어 있는 항목을 입력하세요.")
        if f['id']=='git' and (not re.fullmatch(r'[A-Za-z0-9_-]+',v['owner']) or '@' not in v['email']): raise ValueError('Git 소유자 또는 이메일을 확인하세요.')
        if f['id']=='ssh':
            for k in ('alias','host','user'):
                if not re.fullmatch(r'[A-Za-z0-9_.:@-]+',v[k]) or v[k].startswith('-'): raise ValueError('SSH 별칭·주소·사용자 형식을 확인하세요.')
            if v['alias'].lower() in ('github-personal','github-work'): raise ValueError('기본 SSH 별칭은 추가 연결에서 사용할 수 없습니다.')
            if any(c in v['key'] for c in '"\\%$'): raise ValueError('공개키 경로에 지원하지 않는 문자가 있습니다.')
        if f['id']=='colors':
            for k in ('background','foreground'):
                if not re.fullmatch(r'#[0-9A-Fa-f]{6}',v[k]): raise ValueError('색상은 #RRGGBB 형식입니다.')
    return copy.deepcopy(raw)

def write(path, text):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.dashboard-')
    try:
        with os.fdopen(fd,'w') as stream: stream.write(text)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def generate(state):
    # Every output path is fixed; values cannot select arbitrary files or commands.
    validate(state)
    enabled=[k for k,v in state.items() if v['enabled']]
    runtime='_dotfiles_enabled=('+' '.join(shlex.quote(k) for k in enabled)+')\n'
    v=state['nvm']['values']
    if 'nvm' in enabled:runtime+='export NVM_DIR='+shlex.quote(str(Path(v['dir']).expanduser()))+'\n'
    if 'zellij' in enabled:runtime+='export DOTFILES_ZELLIJ_SESSION='+shlex.quote(state['zellij']['values']['session'])+'\n'
    if 'colors' in enabled:
        runtime+='export DOTFILES_GHOSTTY_COLORS='+shlex.quote(str(DATA/'ghostty.conf'))+'\n'
        runtime+='export DOTFILES_ITERM_COLORS='+shlex.quote(str(DATA/'iterm.conf'))+'\n'
    git='# Generated local identity configuration\n'
    if 'git' in enabled:
        v=state['git']['values']
        for prefix in (f'https://github.com/{v["owner"]}/**',f'git@github.com:{v["owner"]}/**',f'git@github-personal:{v["owner"]}/**'):
            git+='[includeIf '+json.dumps('hasconfig:remote.*.url:'+prefix)+']\n    path = personal.gitconfig\n'
        write(DATA/'personal.gitconfig','[user]\n    name = '+json.dumps(v['name'],ensure_ascii=False)+'\n    email = '+json.dumps(v['email'])+'\n')
    else:write(DATA/'personal.gitconfig','# Disabled\n')
    ssh='# Generated local additional hosts\n'
    if 'ssh' in enabled:
        v=state['ssh']['values']
        ssh+=f'Host {v["alias"]}\n    HostName {v["host"]}\n    User {v["user"]}\n    IdentitiesOnly yes\n    IdentityFile "{v["key"]}"\n'
    ssh+='Host *\n'
    manifest={'secrets':[]}
    if 'bitwarden' in enabled:
        v=state['bitwarden']['values'];manifest['secrets']=[dict(bw_name=v['item'],bw_type=v['type'],action='ssh-add')]
    colors=state['colors']['values']
    write(DATA/'ghostty.conf',f'{colors["path"]}|{colors["background"]}|{colors["foreground"]}\n' if 'colors' in enabled else '# Disabled\n')
    write(DATA/'iterm.conf',f'{colors["path"]}|{colors["background"]}\n' if 'colors' in enabled else '# Disabled\n')
    write(DATA/'secrets.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    write(DATA/'git.config',git);write(DATA/'ssh.config',ssh);write(DATA/'enabled.zsh',runtime)
    write(SETTINGS,json.dumps(state,ensure_ascii=False,indent=2)+'\n')

def installed(f,state):
    if f['id']=='nvm':return (Path(state['nvm']['values']['dir']).expanduser()/'nvm.sh').is_file()
    if f['id']=='colors':return True
    return shutil.which(f['command']) is not None

def plan(state):
    rows=[]
    darwin=sys.platform=='darwin';apt=shutil.which('apt-get') is not None
    packages={'git':'git','ssh':'openssh-client','zoxide':'zoxide','zellij':'zellij','yazi':'yazi'}
    brew={'git':'git','ssh':'openssh','zoxide':'zoxide','zellij':'zellij','yazi':'yazi','bitwarden':'bitwarden-cli'}
    for f in DEFINITIONS:
        if not state[f['id']]['enabled']:continue
        steps=[];ready=installed(f,state)
        if not ready:
            if darwin and shutil.which('brew') and f['id'] in brew:steps.append('command -v '+shlex.quote(f['command'])+' >/dev/null 2>&1 || brew install '+brew[f['id']])
            elif apt and f['id'] in ('git','ssh','zoxide'):
                steps.append('command -v '+shlex.quote(f['command'])+' >/dev/null 2>&1 || (sudo apt-get update && sudo apt-get install -y '+packages[f['id']]+')')
            else:steps.append({'bitwarden':'설치 안내: https://bitwarden.com/help/cli/','nvm':'설치 안내: https://github.com/nvm-sh/nvm#installing-and-updating','zellij':'설치 안내: https://zellij.dev/documentation/installation','yazi':'설치 안내: https://yazi-rs.github.io/docs/installation/'}.get(f['id'],f['name']+' 설치 필요: OS 패키지 관리자로 준비하세요.'))
        if f['id']=='bitwarden':
            if not shutil.which('jq'):steps.append('jq 설치 필요: brew install jq (macOS) / sudo apt-get install jq (Debian·Ubuntu)')
            steps+=['bw login  # 최초 로그인일 때만','bws  # 새 zsh에서 실행; 사용자 인증 필요']
        if f['id']=='ssh' and not Path(state['ssh']['values']['key']).expanduser().is_file():steps.append('공개키 파일을 지정한 경로에 준비하세요. 개인키는 agent에 별도로 로드합니다.')
        if f['id']=='colors':steps.append('색상은 Ghostty 또는 iTerm2에서 적용됩니다. WSL의 다른 터미널에는 적용되지 않습니다.')
        rows.append(dict(name=f['name'],installed=ready,steps=steps or ['이미 설치됨 · 재설치 없이 설정만 갱신합니다.']))
    prerequisites=[]
    for command in ('git','zsh','bash'):
        if not shutil.which(command):prerequisites.append(command+' 설치 필요: OS 패키지 관리자로 준비한 뒤 configure를 실행하세요.')
    return dict(prerequisites=prerequisites,features=rows,configure=shlex.join(['python3',str(REPO/'bin/dashboard.py'),'configure']),after='새 zsh를 열어 셸 설정을 반영하세요. 비활성화 전 셸에 로드된 함수·alias는 새 셸부터 사라집니다.')

def snapshot():
    state=load();features=[]
    for original in DEFINITIONS:
        f=copy.deepcopy(original);f['enabled']=state[f['id']]['enabled'];f['installed']=installed(f,state)
        f['scope']='기기 로컬 설정';f['source']=str(DATA);f['note']='설정만 저장합니다. 필요한 설치·연결 명령은 적용 안내에서 확인하세요.'
        for x in f['fields']:x['value']=state[f['id']]['values'][x['key']]
        features.append(f)
    return dict(features=features,plan=plan(state),environment=platform.node()+' · '+platform.system())

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def respond(self,code,data,kind='application/json'):
        body=(json.dumps(data,ensure_ascii=False).encode() if kind=='application/json' else data)
        self.send_response(code);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
    def valid_host(self):return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'
    def do_GET(self):
        if not self.valid_host():return self.respond(403,{'error':'Invalid host'})
        if self.path=='/api/state':return self.respond(200,snapshot())
        if self.path=='/':return self.respond(200,(REPO/'dashboard/index.html').read_bytes(),'text/html')
        self.respond(404,{'error':'Not found'})
    def do_POST(self):
        if not self.valid_host() or self.headers.get('Origin')!=f'http://127.0.0.1:{self.server.server_port}':return self.respond(403,{'error':'Invalid origin'})
        if self.path!='/api/settings':return self.respond(404,{'error':'Not found'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<65536:raise ValueError('요청 크기가 올바르지 않습니다.')
            state=validate(json.loads(self.rfile.read(length)))
            generate(state);self.respond(200,snapshot())
        except (ValueError,KeyError,TypeError,OSError) as exc:self.respond(400,{'error':str(exc)})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',nargs='?',default='serve',choices=['serve','configure','plan']);parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    if args.action=='plan':print(json.dumps(plan(load()),ensure_ascii=False,indent=2));return
    if args.action=='configure':
        if not SETTINGS.exists():raise SystemExit('대시보드에서 설정을 먼저 저장하세요.')
        generate(load())
        subprocess.run(['bash',str(REPO/'bin/bootstrap.sh')],check=True)
        print('설정 연결 완료. 새 zsh를 여세요. 도구 설치는 실행하지 않았습니다.');return
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    url=f'http://127.0.0.1:{server.server_port}/';print(url,flush=True)
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
