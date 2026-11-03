"""Optional shell/tool definitions and config compilation, independent of services."""
import copy
from pathlib import Path
import shutil
import shlex
import subprocess

def field(key,label,value='',**kw):return dict(key=key,label=label,value=value,**kw)
DEFINITIONS=[
dict(id='ohmyzsh',name='Oh My Zsh',category='shell',icon='›_',command=None,desc='설치된 Oh My Zsh의 테마와 git 플러그인을 읽습니다.',fields=[field('dir','Oh My Zsh 경로','~/.oh-my-zsh'),field('theme','테마','robbyrussell',options=['robbyrussell','agnoster','minimal'])]),
dict(id='zoxide', name='zoxide',category='shell',icon='z',command='zoxide',desc='z로 바로 이동하고 zi로 방문 기록을 골라 이동합니다. zi에는 fzf가 필요합니다.',fields=[]),
dict(id='zellij', name='Zellij',category='terminal',icon='▥',command='zellij',desc='zj 명령으로 프로젝트 세션을 만들거나 재연결합니다.',fields=[field('session','기본 세션 이름','',hint='비워두면 현재 폴더 이름을 사용합니다.')]),
dict(id='colors',name='프로젝트 색상',category='terminal',icon='◐',command=None,desc='한 프로젝트의 Ghostty·iTerm2 색상 규칙을 구성합니다.',fields=[field('path','프로젝트 경로 또는 glob'),field('background','배경색','#172a36',type='color'),field('foreground','글자색','#d6edf8',type='color')]),
dict(id='yazi',name='Yazi',category='terminal',icon='▤',command='yazi',desc='기본 탐색기 설정과 종료 위치로 이동하는 y 함수를 연결합니다.',fields=[]),
dict(id='nvm',name='Node.js · nvm',category='shell',icon='n',command=None,desc='nvm과 사용할 Node.js 버전을 선택합니다. 설치 여부는 각각 확인합니다.',fields=[field('dir','nvm 설치 경로','~/.nvm'),field('node','Node.js 버전','lts/*',options=['lts/*','22','24'])])]

# Standalone tools are optional installation choices; they do not load shell integrations.
for ident,name,category,commands,description in [
 ('fzf','fzf','navigation',['fzf'],'목록에서 대화형으로 선택합니다. zoxide의 zi에 필요합니다.'),
 ('ripgrep','ripgrep · rg','search',['rg'],'파일 내용을 빠르게 검색합니다.'),
 ('fd','fd','search',['fd','fdfind'],'파일 이름을 검색합니다. Ubuntu에서는 fdfind 명령을 사용합니다.'),
 ('bat','bat','search',['bat','batcat'],'문법 강조로 파일을 읽습니다. Ubuntu에서는 batcat 명령을 사용합니다.'),
 ('buildtools','C/C++ 빌드 도구','development',['make','cc','c++'],'컴파일러와 make를 준비합니다.'),
 ('unzip','unzip','development',['unzip'],'ZIP 파일을 풉니다.'),
 ('uv','uv','runtime',['uv'],'Python 프로젝트·패키지·실행 환경을 관리합니다. pip 별칭은 바꾸지 않습니다.'),
 ('aws','AWS CLI','services',['aws'],'AWS 작업용 CLI만 설치합니다. 로그인과 인증은 별도입니다.'),
 ('claude','Claude Code','ai',['claude'],'공식 native 설치를 사용합니다. Node.js와 로그인은 요구하지 않습니다.'),
 ('gemini','Gemini CLI','ai',['gemini'],'Node.js 20 이상과 npm이 필요합니다. nvm 선택 시 해당 Node 버전을 사용합니다.'),
 ('ngrok','ngrok','services',['ngrok'],'로컬 서버 연결 도구만 설치합니다. 토큰 등록과 터널 실행은 별도입니다.'),
 ('gitlfs','Git LFS','development',['git-lfs'],'대용량 Git 파일용 도구만 설치합니다. 저장소에서 git lfs install --local로 별도 설정합니다.')]:
    DEFINITIONS.append(dict(id=ident,name=name,category=category,icon='›',command=commands[0],alternatives=commands if ident in ('fd','bat') else [],required_commands=commands if ident=='buildtools' else [],desc=description,fields=[]))

def upgrade(state):
    if not isinstance(state,dict) or not {'ohmyzsh','zoxide','zellij','colors','yazi','nvm'}<=set(state):
        raise ValueError('기존 선택 도구 설정이 누락되었거나 올바르지 않습니다. 원본 설정을 확인하세요.')
    result=copy.deepcopy(state)
    for ident,value in defaults().items():
        if ident not in result:result[ident]=value
        elif isinstance(result[ident],dict) and isinstance(result[ident].get('values'),dict):
            for key,default in value['values'].items():result[ident]['values'].setdefault(key,default)
    return result

def defaults():
    return {f['id']:{'enabled':False,'values':{x['key']:x['value'] for x in f['fields']}} for f in DEFINITIONS}

def validate(state):
    if not isinstance(state,dict) or set(state)!=set(defaults()):raise ValueError('선택 도구 목록이 올바르지 않습니다.')
    for f in DEFINITIONS:
        item=state[f['id']]
        if not isinstance(item,dict) or set(item)!={'enabled','values'} or type(item['enabled']) is not bool or not isinstance(item['values'],dict):raise ValueError('도구 설정 형식 오류')
        if set(item['values'])!={x['key'] for x in f['fields']}:raise ValueError('알 수 없는 도구 설정 항목')
        for x in f['fields']:
            value=item['values'][x['key']]
            if not isinstance(value,str) or len(value)>1024 or any(ord(c)<32 for c in value):raise ValueError('도구 설정에 잘못된 문자열이 있습니다.')
            if x.get('options') and value not in x['options']:raise ValueError('지원하지 않는 도구 옵션')
            if item['enabled'] and not value.strip() and not (f['id']=='zellij' and x['key']=='session'):raise ValueError(f['name']+': 필수 항목이 비었습니다.')
        if f['id']=='colors' and item['enabled']:
            if '|' in item['values']['path']:raise ValueError('프로젝트 색상 경로에 | 구분자는 사용할 수 없습니다.')
            import re
            for key in ('background','foreground'):
                if not re.fullmatch(r'#[0-9A-Fa-f]{6}',item['values'][key]):raise ValueError('색상은 #RRGGBB 형식입니다.')
    return copy.deepcopy(state)

def installed(f,state):
    if f['id']=='ohmyzsh':return (Path(state['ohmyzsh']['values']['dir']).expanduser()/'oh-my-zsh.sh').is_file()
    if f['id']=='nvm':return (Path(state['nvm']['values']['dir']).expanduser()/'nvm.sh').is_file()
    if f['id']=='colors':return True
    if f['id']=='gemini' and state['nvm']['enabled']:
        values=state['nvm']['values'];script=Path(values['dir']).expanduser()/'nvm.sh'
        if not script.is_file():return False
        try:
            result=subprocess.run(['bash','-c','source "$1" --no-use; nvm use --silent "$2" >/dev/null && command -v gemini >/dev/null','_',str(script),values['node']],capture_output=True,timeout=4)
            return result.returncode==0
        except (OSError,subprocess.TimeoutExpired):return False
    if f.get('alternatives'):return any(shutil.which(c) for c in f['alternatives'])
    if f.get('required_commands'):return all(shutil.which(c) for c in f['required_commands'])
    return shutil.which(f['command']) is not None

def compile(state,data,auth,api_tools):
    enabled=[f['id'] for f in DEFINITIONS if state[f['id']]['enabled']]
    if auth:enabled+=['authentication']
    enabled+=sorted(api_tools)
    runtime='_dotfiles_enabled=('+' '.join(shlex.quote(k) for k in enabled)+')\n'
    for feature,key,variable in [('ohmyzsh','dir','ZSH'),('ohmyzsh','theme','ZSH_THEME'),('nvm','dir','NVM_DIR'),('nvm','node','DOTFILES_NODE_VERSION'),('zellij','session','DOTFILES_ZELLIJ_SESSION')]:
        if feature in enabled:
            value=state[feature]['values'][key]
            if key=='dir':value=str(Path(value).expanduser())
            runtime+='export '+variable+'='+shlex.quote(value)+'\n'
    colors=state['colors']['values']
    if 'colors' in enabled:
        runtime+='export DOTFILES_GHOSTTY_COLORS='+shlex.quote(str(data/'ghostty.conf'))+'\nexport DOTFILES_ITERM_COLORS='+shlex.quote(str(data/'iterm.conf'))+'\n'
    return {'enabled.zsh':runtime,'ghostty.conf':f"{colors['path']}|{colors['background']}|{colors['foreground']}\n" if 'colors' in enabled else '# Disabled\n','iterm.conf':f"{colors['path']}|{colors['background']}\n" if 'colors' in enabled else '# Disabled\n'}
