"""Read-only dependency checks and explicit, individually selected installation commands."""
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import features

DOCS={
 'ohmyzsh':'https://github.com/ohmyzsh/ohmyzsh#basic-installation',
 'nvm':'https://github.com/nvm-sh/nvm#installing-and-updating',
 'zoxide':'https://github.com/ajeetdsouza/zoxide#installation',
 'fzf':'https://github.com/junegunn/fzf#installation',
 'uv':'https://docs.astral.sh/uv/getting-started/installation/',
 'aws':'https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html',
 'claude':'https://code.claude.com/docs/en/setup',
 'gemini':'https://github.com/google-gemini/gemini-cli',
 'ngrok':'https://ngrok.com/download',
 'zellij':'https://zellij.dev/documentation/installation',
 'yazi':'https://yazi-rs.github.io/docs/installation/',
}
INSTALLABLE={'ohmyzsh','nvm','node','zoxide','fzf','ripgrep','fd','bat','buildtools','unzip','uv','aws','claude','gemini','ngrok','gitlfs'}

def node_ready(state):
    values=state['features']['nvm']['values'];script=Path(values['dir']).expanduser()/'nvm.sh'
    if not script.is_file():return False
    try:
        p=subprocess.run(['bash','-c','source "$1" --no-use; v=$(nvm version "$2"); [[ "$v" == v* ]]','_',str(script),values['node']],capture_output=True,text=True,timeout=4)
        return p.returncode==0
    except (OSError,subprocess.TimeoutExpired):return False

def system_node_ready():
    if not shutil.which('npm'):return False
    try:
        p=subprocess.run(['node','--version'],capture_output=True,text=True,timeout=2)
        return p.returncode==0 and int(p.stdout.strip().lstrip('v').split('.')[0])>=20
    except (OSError,ValueError,subprocess.TimeoutExpired):return False

def status(ident,state):
    if ident=='zoxide':return [dict(name='fzf',installed=bool(shutil.which('fzf')),reason='zi의 대화형 선택에 필요 · 함께 설치 안내')]
    if ident=='nvm':return [dict(name='Node.js '+state['features']['nvm']['values']['node'],installed=node_ready(state),reason='nvm 설치 여부와 별도로 선택한 Node 버전을 확인')]
    if ident=='gemini':return [dict(name='Node.js 20+ · npm',installed=node_ready(state) if state['features']['nvm']['enabled'] else system_node_ready(),reason='Node.js · nvm을 선택하거나 시스템 Node.js를 먼저 준비')]
    return []

def plan(state,repo):
    rows=[];seen=set()
    values=state['features']['nvm']['values']
    def add(ident,name,ready,note=''):
        if ident in seen:return
        seen.add(ident)
        command=shlex.join(['bash',str(repo/'bin/install-tool.sh'),ident,str(Path(state['features']['ohmyzsh']['values']['dir'] if ident=='ohmyzsh' else values['dir']).expanduser()),'system' if ident=='gemini' and not state['features']['nvm']['enabled'] else values['node']])
        rows.append(dict(id=ident,name=name,installed=bool(ready),steps=([('설치 안내: '+DOCS[ident])] if ident in DOCS and not ready else []),commands=[command] if not ready and ident in INSTALLABLE else [],note=note))
    # Runtime must be prepared before tools installed with npm.
    ordered=sorted(features.DEFINITIONS,key=lambda f:0 if f['id']=='nvm' else 1)
    for f in ordered:
        if not state['features'][f['id']]['enabled']:continue
        ident=f['id'];ready=features.installed(f,state['features'])
        if ident=='aws' and not ready and sys.platform!='darwin':add('unzip','unzip · AWS 설치 의존성',shutil.which('unzip'),'Linux AWS CLI 설치 파일을 풀 때 필요합니다.')
        add(ident,f['name'],ready)
        if not ready and ident not in INSTALLABLE and ident!='colors':rows[-1]['steps']=['설치 안내: '+DOCS.get(ident,'OS 패키지 관리자로 '+f['name']+' 설치')]
        if ident=='nvm':add('node','Node.js '+values['node'],node_ready(state),'nvm이 있어도 선택한 Node 버전이 없으면 설치합니다. 기존 버전을 자동 업그레이드하지 않습니다.')
        if ident=='zoxide':add('fzf','fzf · zi 의존성',shutil.which('fzf'),'z는 zoxide만으로, zi는 fzf와 함께 사용합니다.')
        if ident=='gemini' and not state['features']['nvm']['enabled'] and not system_node_ready():
            rows.append(dict(id='node-system',name='Node.js 20+ · npm',installed=False,steps=['먼저 선택 도구에서 Node.js · nvm을 켜고 버전을 고르거나 시스템 Node.js 20 이상과 npm을 준비하세요. 이후 Gemini CLI 설치 명령을 실행하세요.'],commands=[]))
    return rows
