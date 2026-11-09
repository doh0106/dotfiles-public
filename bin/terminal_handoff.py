"""Input-only terminal handoff. Never submit a login command with Return."""
import json,os,plistlib,subprocess,sys,tempfile
from pathlib import Path
import configuration as cfg
APPS={'terminal':('Terminal','com.apple.Terminal',['/System/Applications/Utilities/Terminal.app','/Applications/Utilities/Terminal.app']), 'iterm2':('iTerm2','com.googlecode.iterm2',['/Applications/iTerm.app','~/Applications/iTerm.app']), 'ghostty':('Ghostty','com.mitchellh.ghostty',['/Applications/Ghostty.app','~/Applications/Ghostty.app'])}
ITERM='''on run argv
tell application id "com.googlecode.iterm2"
activate
set newWindow to (create window with default profile)
tell current session of newWindow
write text (item 1 of argv) newline false
end tell
end tell
end run'''
def available():
    result=[]
    if sys.platform!='darwin':return result
    for ident,(title,bundle,paths) in APPS.items():
        for path in paths:
            try:
                target=Path(path).expanduser();info=target/'Contents/Info.plist'
                if info.stat().st_size>1048576:continue
                with info.open('rb') as stream:data=plistlib.load(stream)
                if data.get('CFBundleIdentifier')==bundle:result.append(dict(id=ident,title=title));break
            except (OSError,ValueError,plistlib.InvalidFileException):continue
    return result
def settings():
    try:
        path=cfg.DATA/'terminal-preferences.json'
        if path.is_symlink() or path.stat().st_size>4096:return ''
        selected=json.loads(path.read_text()).get('default_terminal','')
        return selected if selected in {item['id'] for item in available()} else ''
    except (OSError,ValueError,TypeError,AttributeError):return ''
def save(terminal):
    if terminal not in {item['id'] for item in available()}:raise ValueError('설치된 터미널 앱을 선택하세요.')
    cfg.DATA.mkdir(parents=True,exist_ok=True,mode=0o700)
    target=cfg.DATA/'terminal-preferences.json'
    if target.is_symlink():raise ValueError('터미널 설정 파일의 링크를 확인하세요.')
    descriptor,name=tempfile.mkstemp(dir=cfg.DATA,prefix='.terminal-')
    try:
        with os.fdopen(descriptor,'w') as output:json.dump(dict(default_terminal=terminal),output)
        os.replace(name,target)
    finally:
        if os.path.exists(name):os.unlink(name)
    return dict(default_terminal=terminal)
def open_input(command,terminal,run):
    if '\n' in command or '\r' in command:raise ValueError('한 줄 명령만 입력할 수 있습니다.')
    if terminal not in {item['id'] for item in available()}:raise ValueError('기본 터미널 앱을 먼저 선택하세요.')
    if terminal=='iterm2':
        result=run(['/usr/bin/osascript','-e',ITERM,command])
        if not result.returncode:return 'input'
        raise ValueError('iTerm2 명령 입력에 실패했습니다. 자동화 권한을 확인하거나 명령을 직접 복사하세요.')
    # Terminal/Ghostty have no equivalent supported input-only text API.
    # Copy and open a clean window rather than executing a script or sending Return.
    result=run(['/usr/bin/pbcopy'],input=command)
    if result.returncode:raise ValueError('명령 복사에 실패했습니다.')
    bundle=APPS[terminal][1]
    if terminal=='terminal':
        result=run(['/usr/bin/osascript','-e','tell application id "com.apple.Terminal"\nactivate\ndo script ""\nend tell'])
    else:result=run(['/usr/bin/open','-b',bundle])
    if result.returncode:raise ValueError('터미널을 열지 못했습니다. 복사된 명령을 원하는 터미널에 붙여넣으세요.')
    return 'clipboard'
