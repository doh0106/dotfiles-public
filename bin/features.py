"""Optional shell/tool definitions and config compilation, independent of services."""
import copy
from pathlib import Path
import shutil
import shlex

def field(key,label,value='',**kw):return dict(key=key,label=label,value=value,**kw)
DEFINITIONS=[
dict(id='ohmyzsh',name='Oh My Zsh',category='shell',icon='›_',command=None,desc='설치된 Oh My Zsh의 테마와 git 플러그인을 읽습니다.',fields=[field('dir','Oh My Zsh 경로','~/.oh-my-zsh'),field('theme','테마','robbyrussell',options=['robbyrussell','agnoster','minimal'])]),
dict(id='zoxide', name='zoxide',category='shell',icon='z',command='zoxide',desc='z 명령으로 자주 가는 디렉터리로 이동합니다.',fields=[]),
dict(id='zellij', name='Zellij',category='terminal',icon='▥',command='zellij',desc='zj 명령으로 프로젝트 세션을 만들거나 재연결합니다.',fields=[field('session','기본 세션 이름','',hint='비워두면 현재 폴더 이름을 사용합니다.')]),
dict(id='colors',name='프로젝트 색상',category='terminal',icon='◐',command=None,desc='한 프로젝트의 Ghostty·iTerm2 색상 규칙을 구성합니다.',fields=[field('path','프로젝트 경로 또는 glob'),field('background','배경색','#172a36',type='color'),field('foreground','글자색','#d6edf8',type='color')]),
dict(id='yazi',name='Yazi',category='terminal',icon='▤',command='yazi',desc='기본 탐색기 설정과 종료 위치로 이동하는 y 함수를 연결합니다.',fields=[]),
dict(id='nvm',name='Node.js · nvm',category='shell',icon='n',command=None,desc='지정한 경로에 설치된 nvm을 읽습니다.',fields=[field('dir','nvm 설치 경로','~/.nvm')])]

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
    return shutil.which(f['command']) is not None

def compile(state,data,auth,api_tools):
    enabled=[f['id'] for f in DEFINITIONS if state[f['id']]['enabled']]
    if auth:enabled+=['authentication']
    enabled+=sorted(api_tools)
    runtime='_dotfiles_enabled=('+' '.join(shlex.quote(k) for k in enabled)+')\n'
    for feature,key,variable in [('ohmyzsh','dir','ZSH'),('ohmyzsh','theme','ZSH_THEME'),('nvm','dir','NVM_DIR'),('zellij','session','DOTFILES_ZELLIJ_SESSION')]:
        if feature in enabled:
            value=state[feature]['values'][key]
            if key=='dir':value=str(Path(value).expanduser())
            runtime+='export '+variable+'='+shlex.quote(value)+'\n'
    colors=state['colors']['values']
    if 'colors' in enabled:
        runtime+='export DOTFILES_GHOSTTY_COLORS='+shlex.quote(str(data/'ghostty.conf'))+'\nexport DOTFILES_ITERM_COLORS='+shlex.quote(str(data/'iterm.conf'))+'\n'
    return {'enabled.zsh':runtime,'ghostty.conf':f"{colors['path']}|{colors['background']}|{colors['foreground']}\n" if 'colors' in enabled else '# Disabled\n','iterm.conf':f"{colors['path']}|{colors['background']}\n" if 'colors' in enabled else '# Disabled\n'}
