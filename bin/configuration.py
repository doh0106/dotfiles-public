"""Versioned model: environment features, identities, services, transports, credentials."""
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import tempfile
import fcntl
from urllib.parse import urlsplit
import features

REPO=Path(__file__).resolve().parents[1]
DATA=Path.home()/'.config/dotfiles/dashboard'
SETTINGS=DATA/'settings.json'
SCHEMA=3


def defaults():
    return dict(schema=SCHEMA,features=features.defaults(),git=dict(enabled=False,blockUnclassified=True),profiles=[dict(id='personal',name='개인 작업',path='~/personal/',author='',email='',enabled=True)],connections=[],credentials=[],session=dict(keyLifetime=3600))


def new_connection(profile='personal',ident='connection'):
    return dict(id=ident,name='새 연결',profile=profile,provider='github',host='github.com',kind='git',enabled=False,method='ssh',sshUser='git',publicKey='~/.ssh/keys/github-personal.pub',credential='',api=dict(enabled=False,tool='gh',credential='',host=''))


def migrate(raw):
    if not isinstance(raw,dict):raise ValueError('설정 형식 오류')
    if raw.get('schema')==SCHEMA:
        state=copy.deepcopy(raw);state['features']=features.upgrade(state.get('features',{}))
        return state,state!=raw
    if 'schema' in raw:raise ValueError('지원하지 않는 설정 버전입니다. 원본 설정은 변경하지 않았습니다.')
    state=defaults()
    for name in state['features']:
        if name in raw:state['features'][name]=copy.deepcopy(raw[name])
    git=raw.get('git',{'enabled':False,'values':{}});g=git.get('values',{})
    state['git']['enabled']=git.get('enabled',False)
    state['profiles']=[]
    bw=raw.get('bitwarden',{'enabled':False,'values':{}});b=bw.get('values',{})
    gh=raw.get('gh',{'enabled':False,'values':{}});h=gh.get('values',{})
    for name in ['personal']+(['work'] if g.get('work_mode')=='on' else []):
        pre='' if name=='personal' else 'work_'
        state['profiles'].append(dict(id=name,name='개인 작업' if name=='personal' else '회사 작업',path=g.get(name+'_dir','~/personal/' if name=='personal' else '~/work/'),author=g.get(pre+'name',''),email=g.get(pre+'email',''),enabled=True))
        if git.get('enabled') or bw.get('enabled') or gh.get('enabled'):
            conn=new_connection(name,name+'-github');conn.update(name='GitHub · '+name,enabled=True,publicKey=g.get(name+'_key','~/.ssh/keys/github-personal.pub' if name=='personal' else '~/.config/dotfiles/private/ssh/keys/github-work.pub'))
            key_id=name+'-ssh';state['credentials'].append(dict(id=key_id,source='bitwarden' if bw.get('enabled') else 'agent',kind=b.get('type' if name=='personal' else 'work_type','note'),item=b.get('item' if name=='personal' else 'work_item',''),variable='',helper='cache',username=''))
            conn['credential']=key_id
            if gh.get('enabled'):
                ident=name+'-api';state['credentials'].append(dict(id=ident,source='bitwarden',kind=h.get('type' if name=='personal' else 'work_type','note'),item=h.get('personal_item' if name=='personal' else 'work_item',''),variable='',helper='cache',username=''))
                conn['api'].update(enabled=True,credential=ident)
            state['connections'].append(conn)
    ssh=raw.get('ssh',{})
    if ssh.get('enabled'):
        values=ssh['values'];conn=new_connection('personal','legacy-server');conn.update(name=values['alias'],sshAlias=values['alias'],provider='generic',kind='server',host=values['host'],sshUser=values['user'],publicKey=values['key'],enabled=True,credential='legacy-server-agent');state['connections'].append(conn)
        state['credentials'].append(dict(id='legacy-server-agent',source='agent',kind='note',item='',variable='',helper='cache',username=''))
    state['session']['keyLifetime']=int(b.get('lifetime','3600'))
    return state,True


def read_settings():
    try:raw=SETTINGS.read_bytes()
    except FileNotFoundError:return defaults(),False,'new'
    state,migrated=migrate(json.loads(raw))
    return state,migrated,hashlib.sha256(raw).hexdigest()


def load():
    state,migrated,_=read_settings()
    return state,migrated


def revision():
    try:return hashlib.sha256(SETTINGS.read_bytes()).hexdigest()
    except FileNotFoundError:return 'new'


def string(value,label,required=False):
    if not isinstance(value,str) or len(value)>2048 or any(ord(c)<32 or ord(c)==127 for c in value):raise ValueError(label+': 문자열 형식 오류')
    if required and not value.strip():raise ValueError(label+': 필수 항목입니다.')


def ident(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}',value):raise ValueError('ID는 소문자·숫자·하이픈으로 지정하세요.')


def path(value,label,required=True):
    string(value,label,required)
    if not value and not required:return
    if not value.startswith(('/','~/')) or any(c in value for c in '*?[]\\%$"'):raise ValueError(label+': glob 없는 절대 경로 또는 ~/ 경로를 사용하세요.')


def host_parts(value):
    string(value,'호스트',True)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*(?::[0-9]{1,5})?',value):raise ValueError('호스트는 도메인 또는 도메인:포트 형식입니다. URL·사용자명·경로는 따로 입력하세요.')
    parsed=urlsplit('https://'+value)
    try:port=parsed.port
    except ValueError:raise ValueError('호스트 포트 오류') from None
    if port is not None and not 1<=port<=65535:raise ValueError('포트 범위 오류')
    return parsed.hostname.lower(),port


def endpoint(value,method):
    name,port=host_parts(value)
    if port in (None,443 if method=='https' else 22):return name
    return name+':'+str(port)


def ssh_mode(connection):
    # Absent means the old explicit-key behavior. Reading never rewrites old settings.
    return connection.get('sshMode','key')

def connection_refs(connection):
    refs=[]
    if connection['method']!='ssh' or ssh_mode(connection)!='system':refs.append(connection['credential'])
    if connection['api']['enabled']:refs.append(connection['api']['credential'])
    return [ref for ref in refs if ref]

def validate(state):
    if not isinstance(state,dict) or set(state)!={'schema','features','git','profiles','connections','credentials','session'} or state['schema']!=SCHEMA:raise ValueError('설정 버전/최상위 항목이 올바르지 않습니다. 화면을 새로고침하세요.')
    features.validate(state['features'])
    if set(state['git'])!={'enabled','blockUnclassified'} or any(type(v) is not bool for v in state['git'].values()):raise ValueError('Git 적용 옵션 오류')
    if set(state['session'])!={'keyLifetime'} or type(state['session']['keyLifetime']) is not int or not 60<=state['session']['keyLifetime']<=86400:raise ValueError('키 수명은 60~86400초입니다.')
    for key in ('profiles','connections','credentials'):
        if not isinstance(state[key],list) or len(state[key])>100:raise ValueError(key+': 최대 100개입니다.')
        ids=[]
        for item in state[key]:
            if not isinstance(item,dict):raise ValueError('설정 항목 형식 오류')
            ident(item.get('id'));ids.append(item['id'])
        if len(set(ids))!=len(ids):raise ValueError(key+': 중복 ID')
    profiles={p['id']:p for p in state['profiles']};credentials={c['id']:c for c in state['credentials']};roots=[]
    for p in state['profiles']:
        if set(p)!={'id','name','path','author','email','enabled'} or type(p['enabled']) is not bool:raise ValueError('프로필 항목 형식 오류')
        for key in ('name','author','email'):string(p[key],'프로필 '+key,key=='name')
        path(p['path'],'프로필 폴더')
        if p['enabled']:
            root=Path(p['path']).expanduser().resolve()
            if any(root==r or root in r.parents or r in root.parents for r in roots):raise ValueError('프로필 폴더가 겹치거나 중첩됩니다.')
            roots.append(root)
            if state['git']['enabled'] and (not p['author'].strip() or '@' not in p['email']):raise ValueError('활성 프로필의 커밋 이름·이메일이 필요합니다.')
    if state['git']['enabled'] and not roots:raise ValueError('Git 신원을 적용할 활성 프로필이 필요합니다.')
    for c in state['credentials']:
        required={'id','source','kind','item','variable','helper','username'}
        if not required<=set(c) or set(c)-required-{'purpose','deliveryVariable'}:raise ValueError('인증 참조 항목 형식 오류')
        string(c.get('deliveryVariable',''),'토큰 공급 환경변수')
        if c.get('deliveryVariable') and (c.get('purpose')!='token' or not re.fullmatch('[A-Z][A-Z0-9_]*_TOKEN',c['deliveryVariable'])):raise ValueError('공급 대상 환경변수는 SERVICE_TOKEN처럼 지정하세요.')
        if c.get('purpose','token') not in ('ssh-key','token','password'):raise ValueError('비밀 항목 용도 오류')
        if c.get('purpose')=='password' and (c['source']!='bitwarden' or c['kind'] not in ('note','login')):raise ValueError('일반 비밀번호는 비밀 저장소의 Login 또는 Secure Note를 참조하세요.')
        for key in ('source','kind','item','variable','helper','username'):string(c[key],'인증 참조 '+key)
        if c['source'] not in ('bitwarden','agent','git-helper','environment') or c['kind'] not in ('note','sshkey','login'):raise ValueError('지원하지 않는 인증 공급 방식')
        if c['helper'] not in ('cache','manager','osxkeychain','libsecret'):raise ValueError('지원하지 않는 외부 credential helper')
        if c['variable'] in ('PATH','HOME','CODEX_HOME','SHELL','USER','PWD','OLDPWD','BW_SESSION','BW_PASSWORD','BW_CLIENTSECRET','BW_CLIENTID','SSH_AUTH_SOCK','SSH_AGENT_PID','GIT_DIR','GIT_WORK_TREE'):raise ValueError('시스템·vault 변수는 API 토큰 참조로 사용할 수 없습니다.')
        if c['variable'] and not re.fullmatch('[A-Z_][A-Z0-9_]*',c['variable']):raise ValueError('환경변수 이름 오류')
    def credential(ref,sources,purpose):
        if ref not in credentials:raise ValueError('인증정보 참조를 선택하세요.')
        value=credentials[ref]
        if value.get('purpose')=='password':raise ValueError('일반 비밀번호 항목은 Git·SSH·API에 자동 공급하지 않습니다.')
        if value.get('purpose') not in (None,purpose):raise ValueError('연동할 비밀 항목의 용도가 맞지 않습니다.')
        if value['source'] not in sources:raise ValueError('선택한 접속 방식에서 사용할 수 없는 인증 공급자입니다.')
        if value['source']=='bitwarden' and not value['item'].strip():raise ValueError('Bitwarden 항목 이름을 입력하세요.')
        if value['source']=='environment' and not value['variable']:raise ValueError('토큰 환경변수 이름을 입력하세요.')
        return value
    seen=set();ssh_hosts=set()
    for c in state['connections']:
        required={'id','name','profile','provider','host','kind','enabled','method','sshUser','publicKey','credential','api'}
        if not required<=set(c) or set(c)-required-{'sshAlias','sshMode','agentSocket'}:raise ValueError('연결 항목 형식 오류')
        if ssh_mode(c) not in ('system','key'):raise ValueError('SSH 인증 방식 오류')
        for k in ('name','profile','provider','host','kind','method','sshUser','publicKey','credential'):string(c[k],'연결 '+k,k=='name')
        if type(c['enabled']) is not bool or (c['profile'] and c['profile'] not in profiles):raise ValueError('연결의 프로필을 확인하세요.')
        if c['provider'] not in ('github','gitlab','generic') or c['method'] not in ('ssh','https') or c['kind'] not in ('git','server'):raise ValueError('지원하지 않는 서비스·통신 방식')
        if set(c['api']) not in ({'enabled','tool','credential'},{'enabled','tool','credential','host'}) or type(c['api']['enabled']) is not bool or c['api']['tool'] not in ('gh','glab','none'):raise ValueError('API 설정 형식 오류')
        string(c.get('agentSocket',''),'SSH agent 소켓')
        if c.get('agentSocket'):path(c['agentSocket'],'SSH agent 소켓')
        string(c.get('sshAlias',''),'SSH 서버 별칭')
        if c.get('sshAlias') and (c['kind']!='server' or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]*',c['sshAlias'])):raise ValueError('SSH 서버 별칭 형식 오류')
        string(c['api']['credential'],'API 인증 참조')
        string(c['api'].get('host',''),'API 서비스 호스트')
        if not c['enabled']:continue
        if c['profile'] and not profiles[c['profile']]['enabled']:raise ValueError('비활성 프로필에 연결을 활성화할 수 없습니다.')
        hostname,port=host_parts(c['host'])
        if c['kind']=='git':
            key=(c['profile'],endpoint(c['host'],c['method']),c['method'])
            if c['profile'] and key in seen:raise ValueError('같은 프로필·호스트·Git 방식의 연결이 중복됩니다.')
            seen.add(key)
        if c['method']=='ssh' and ssh_mode(c)=='key':
            path(c['publicKey'],'공개키 경로')
            if not c['publicKey'].endswith('.pub'):raise ValueError('신원 선택 경로에는 .pub 공개키 파일을 지정하세요.')
            if not re.fullmatch('[A-Za-z0-9_.-]+',c['sshUser']) or c['sshUser'].startswith('-'):raise ValueError('SSH 사용자명 오류')
            value=credential(c['credential'],('bitwarden','agent'),'ssh-key') if c['credential'] else None
            if value and value['source']=='bitwarden' and value['kind'] not in ('note','sshkey'):raise ValueError('SSH 키는 note 또는 sshkey 형식입니다.')
            if c['kind']=='git':
                key=(c['profile'],hostname)
                if c['profile'] and key in ssh_hosts:raise ValueError('한 프로필에서 같은 SSH 호스트에 여러 키를 적용하려면 프로필을 분리하세요.')
                ssh_hosts.add(key)
        elif c['method']=='ssh':pass
        elif c['kind']=='server':raise ValueError('일반 SSH 서버 연결은 SSH 방식을 사용하세요.')
        elif c['credential']:
            value=credential(c['credential'],('bitwarden','git-helper'),'token')
            if value['source']=='bitwarden' and (value['kind']=='sshkey' or not value['username']):raise ValueError('HTTPS에는 토큰 형식과 Git 사용자명이 필요합니다.')
        if c['api']['enabled']:
            if c['api'].get('host'):host_parts(c['api']['host'])
            expected={'github':'gh','gitlab':'glab'}.get(c['provider'])
            if c['api']['tool']!=expected or c['kind']!='git':raise ValueError('이 서비스의 API 도구는 지원하지 않습니다.')
            value=credential(c['api']['credential'],('bitwarden','environment'),'token')
            if value['kind']=='sshkey':raise ValueError('API 토큰에 SSH Key 형식을 사용할 수 없습니다.')
    for profile in profiles:
        ssh=[c for c in state['connections'] if c['enabled'] and c['kind']=='git' and c['method']=='ssh' and c['profile']==profile]
        if profile and len({ssh_mode(c) for c in ssh})>1:raise ValueError('같은 폴더 규칙에서 기존 SSH 설정과 지정 키 방식을 혼합할 수 없습니다. 폴더 규칙을 분리하거나 연결을 직접 선택하세요.')
    return copy.deepcopy(state)


def compile(state):
    state=validate(state);files={};active=[c for c in state['connections'] if c['enabled']];creds={c['id']:c for c in state['credentials']}
    tools={c['api']['tool'] for c in active if c['api']['enabled']}
    files.update(features.compile(state['features'],DATA,bool(active),tools))
    git='# Generated identities and connection policies\n'
    if state['git']['enabled'] and state['git']['blockUnclassified']:git+='[user]\n    name =\n    email =\n    useConfigOnly = true\n'
    runtime=dict(schema=SCHEMA,git_enabled=state['git']['enabled'],profiles={},connections={c['id']:c for c in active},credentials=creds,lifetime=state['session']['keyLifetime'])
    # Connections without a folder profile are explicit opt-in policies, never
    # ambient global credentials. They can be chosen with --connection ID.
    for c in active:
        if c['profile'] or c['kind']!='git':continue
        text='# Explicit connection policy: '+c['id']+'\n'
        if c['method']=='ssh' and ssh_mode(c)=='key':
            hostname,port=host_parts(c['host']);sshfile='ssh-connection-'+c['id']+'.config'
            ssh='Host '+hostname+'\n    HostName '+hostname+'\n    User '+c['sshUser']+'\n    IdentitiesOnly yes\n    IdentityFile '+json.dumps(str(Path(c['publicKey']).expanduser()),ensure_ascii=False)+'\n'
            if c.get('agentSocket'):ssh+='    IdentityAgent '+json.dumps(c['agentSocket'])+'\n'
            if port:ssh+='    Port '+str(port)+'\n'
            files[sshfile]=ssh+'Host *\nInclude ~/.ssh/config\n'
            text+='[core]\n    sshCommand = '+json.dumps(shlex.join(['ssh','-F',str(DATA/sshfile)]),ensure_ascii=False)+'\n'
        elif c['method']=='https' and c['credential']:
            cred=creds[c['credential']]
            text+='[credential '+json.dumps('https://'+c['host'],ensure_ascii=False)+']\n    helper =\n'
            if cred['source']=='git-helper':text+='    helper = '+cred['helper']+'\n'
            else:
                command='!'+shlex.join(['python3',str(REPO/'bin/auth.py'),'credential','--connection',c['id']])
                text+='    helper = '+json.dumps(command,ensure_ascii=False)+'\n'
        files['connection-'+c['id']+'.gitconfig']=text
    for p in state['profiles']:
        if not p['enabled']:continue
        runtime['profiles'][p['id']]=dict(directory=str(Path(p['path']).expanduser().resolve()),name=p['name'])
        filename='profile-'+p['id']+'.gitconfig'
        git+='[includeIf '+json.dumps('gitdir:'+str(Path(p['path']).expanduser().resolve()).rstrip('/')+'/',ensure_ascii=False)+']\n    path = '+json.dumps(str(DATA/filename),ensure_ascii=False)+'\n'
        text='[dotfiles]\n    profile = '+p['id']+'\n'
        if state['git']['enabled']:text+='[user]\n    name = '+json.dumps(p['author'],ensure_ascii=False)+'\n    email = '+json.dumps(p['email'],ensure_ascii=False)+'\n'
        ssh='# Profile-scoped SSH host policy\n'
        ssh_connections=[c for c in active if c['profile']==p['id'] and c['method']=='ssh' and c['kind']=='git' and ssh_mode(c)=='key']
        if ssh_connections:
            sshfile='ssh-'+p['id']+'.config'
            for c in ssh_connections:
                hostname,port=host_parts(c['host']);ssh+='Host '+hostname+'\n    HostName '+hostname+'\n    User '+c['sshUser']+'\n    IdentitiesOnly yes\n    IdentityFile '+json.dumps(str(Path(c['publicKey']).expanduser()),ensure_ascii=False)+'\n'
                if c.get('agentSocket'):ssh+='    IdentityAgent '+json.dumps(c['agentSocket'])+'\n'
                if port:ssh+='    Port '+str(port)+'\n'
            ssh+='Host *\nInclude ~/.ssh/config\n';files[sshfile]=ssh
            text+='[core]\n    sshCommand = '+json.dumps(shlex.join(['ssh','-F',str(DATA/sshfile)]),ensure_ascii=False)+'\n'
        for c in active:
            if c['profile']!=p['id'] or c['method']!='https' or not c['credential']:continue
            cred=creds[c['credential']]
            text+='[credential '+json.dumps('https://'+c['host'],ensure_ascii=False)+']\n    helper =\n'
            if cred['source']=='git-helper':text+='    helper = '+cred['helper']+'\n'
            else:
                command='!'+shlex.join(['python3',str(REPO/'bin/auth.py'),'credential','--profile',p['id']])
                text+='    helper = '+json.dumps(command,ensure_ascii=False)+'\n'
        files[filename]=text
        # Retain old explicit clone-profile paths for personal/work migrations.
        if p['id'] in ('personal','work'):files[p['id']+'.gitconfig']=text
    files['git.config']=git
    ssh='# Additional SSH server aliases\n'
    for c in active:
        if c['kind']!='server' or ssh_mode(c)=='system':continue
        hostname,port=host_parts(c['host']);ssh+='Host '+(c.get('sshAlias') or c['id'])+'\n    HostName '+hostname+'\n    User '+c['sshUser']+'\n    IdentitiesOnly yes\n    IdentityFile '+json.dumps(str(Path(c['publicKey']).expanduser()),ensure_ascii=False)+'\n'
        if c.get('agentSocket'):ssh+='    IdentityAgent '+json.dumps(c['agentSocket'])+'\n'
        if port:ssh+='    Port '+str(port)+'\n'
    files['ssh.config']=ssh+'Host *\n'
    files['profiles.json']=json.dumps(runtime,ensure_ascii=False,indent=2)+'\n'
    files['secrets.json']='{"secrets": []}\n'
    return files


def generate(state,expected=None):
    files=compile(state)
    DATA.mkdir(parents=True,exist_ok=True)
    DATA.chmod(0o700)
    with (DATA/'.settings.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if expected is not None and expected!=revision():raise ValueError('다른 화면에서 설정이 바뀌었습니다. 새로 불러온 뒤 다시 검토하세요.')
        before={name:(DATA/name).read_bytes() if (DATA/name).exists() else None for name in [*files,'settings.json']}
        if SETTINGS.exists() and migrate(json.loads(SETTINGS.read_text()))[1]:
            backup=DATA/('settings.json.bak.'+datetime.datetime.now().strftime('%Y%m%d%H%M%S%f'));atomic(backup,SETTINGS.read_bytes())
        try:
            for name,text in files.items():atomic(DATA/name,text.encode())
            atomic(SETTINGS,(json.dumps(state,ensure_ascii=False,indent=2)+'\n').encode())
            saved_revision=revision()
        except Exception:
            for name,value in before.items():
                if value is None:(DATA/name).unlink(missing_ok=True)
                else:atomic(DATA/name,value)
            raise
        return saved_revision


def atomic(path,contents):
    fd,temp=tempfile.mkstemp(dir=path.parent,prefix='.settings-')
    try:
        with os.fdopen(fd,'wb') as f:f.write(contents)
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
