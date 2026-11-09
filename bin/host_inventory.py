"""Read-only host discovery and explicit registration of existing config references.

Never source shell files, evaluate SSH Match/ProxyCommand, read a key/token, or
rewrite the discovered configuration. Imported references keep their original owner.
"""
import fnmatch
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
from datetime import datetime, timezone
import fcntl
import configuration as cfg

LIMIT = 262144
COMMANDS = [('git','Git'),('python3','Python'),('zsh','zsh'),('bw','Bitwarden CLI'),
 ('gh','GitHub CLI'),('glab','GitLab CLI'),('gcloud','Google Cloud CLI'),
 ('docker','Docker CLI'),('devcontainer','Dev Container CLI'),('dev-up','dev-up'),
 ('dev-shell','dev-shell'),('dev-status','dev-status'),('codex','Codex'),
 ('claude','Claude Code'),('gemini','Gemini CLI'),('tailscale','Tailscale')]


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def store():return Path.home()/'.config/dotfiles/dashboard/existing-settings.json'


def safe_file(path):
    """Only bounded user-owned configuration files, not credential material."""
    path=Path(path).expanduser().resolve()
    if not path.is_relative_to(Path.home().resolve()):raise ValueError('outside_home')
    if any(part.lower() in {'secrets','secrets.json','credentials','credentials.json',
        'application_default_credentials.json'} or part.lower().endswith(('.netrc','.pem','.key'))
        or part.lower().startswith(('id_rsa','id_ed25519','id_ecdsa')) for part in path.parts):
        raise ValueError('credential_path_not_configuration')
    info=path.stat()
    if not path.is_file() or info.st_uid!=os.geteuid() or info.st_size>LIMIT:
        raise ValueError('configuration_unavailable')
    return path


def read_config(path):return safe_file(path).read_text()


def expand_path(value,base):
    value=value.replace('${HOME}',str(Path.home())).replace('$HOME',str(Path.home()))
    path=Path(value).expanduser()
    return path if path.is_absolute() else base/path


def candidate(category,label,source,locator,details):
    key=digest([category,str(source),locator])[:20]
    return dict(id=key,category=category,label=label,source=str(source),locator=locator,
                details=details,fingerprint=digest(details))


def git_configuration():
    result=[];warnings=[];visited=set();paths=[]
    def visit(path,condition='global',depth=0):
        try:path=safe_file(path)
        except (OSError,ValueError):return
        key=(str(path),condition)
        if key in visited:return
        if depth>8 or len(visited)>=32:
            warnings.append('Git include 탐색 범위를 넘은 설정은 감지하지 않았습니다.');return
        visited.add(key);paths.append(str(path))
        env={k:v for k,v in os.environ.items() if not k.startswith('GIT_CONFIG_')}
        try:
            p=subprocess.run(['git','config','--file',str(path),'--no-includes','--null',
                '--get-regexp',r'^(user\.(name|email|useconfigonly)|include\.path|includeif\..*\.path)$'],
                capture_output=True,timeout=3,env=env)
            if p.returncode not in (0,1) or len(p.stdout)>LIMIT:return
            rows=[record.decode().split('\n',1) for record in p.stdout.split(b'\0') if b'\n' in record]
        except (OSError,UnicodeError,subprocess.TimeoutExpired):return
        identity={k[5:]:v for k,v in rows if k in ('user.name','user.email')}
        if identity.get('name') or identity.get('email'):
            # Do not flatten hasconfig/remote or case-insensitive gitdir rules.
            result.append(candidate('git','Git 작성자 · '+path.stem,path,condition,
                dict(author=identity.get('name',''),email=identity.get('email',''),condition=condition)))
        for name,value in rows:
            if name=='include.path':visit(expand_path(value,path.parent),condition,depth+1)
            elif name.startswith('includeif.') and name.endswith('.path'):
                rule=name[len('includeif.'):-len('.path')]
                if len(rule)>2048 or any(ord(c)<32 for c in rule):continue
                if re.search(r'https?://[^/\s]+@',rule):
                    warnings.append('인증정보가 포함될 수 있는 Git 조건은 표시하지 않았습니다.');continue
                # Nested conditions must remain a conjunction, not an unconditional include.
                nested=rule if condition=='global' else condition+' AND '+rule
                visit(expand_path(value,path.parent),nested,depth+1)
    explicit=os.environ.get('GIT_CONFIG_GLOBAL')
    for root in ([Path(explicit).expanduser()] if explicit else [Path.home()/'.config/git/config',Path.home()/'.gitconfig']):visit(root)
    grouped={}
    for item in result:
        key=(item['source'],item['details']['author'],item['details']['email'])
        if key not in grouped:grouped[key]=dict(item,details=dict(item['details'],conditions=[]))
        grouped[key]['details']['conditions'].append(item['details']['condition'])
    result=[]
    source_revision=digest([(p,Path(p).stat().st_mtime_ns,Path(p).stat().st_size) for p in sorted(set(paths))])
    for item in grouped.values():
        item['details'].pop('condition',None);item['details']['source_revision']=source_revision
        result.append(candidate('git',item['label'],item['source'],'user-identity',item['details']))
    return result,dict(sources=sorted(set(paths)),warnings=warnings)


def ssh_configuration():
    events=[];aliases={};visited=set();warnings=[]
    def visit(path,depth=0):
        try:path=safe_file(path);text=path.read_text()
        except (OSError,ValueError):return
        if str(path) in visited:return
        if depth>8 or len(visited)>=32:
            warnings.append('SSH Include 탐색 범위를 넘은 설정은 감지하지 않았습니다.');return
        visited.add(str(path))
        for number,line in enumerate(text.splitlines(),1):
            try:parts=shlex.split(line,comments=True)
            except ValueError:continue
            if not parts:continue
            # OpenSSH accepts both "Key value" and "Key=value".
            if '=' in parts[0]:
                key,value=parts[0].split('=',1);parts=[key]+([value] if value else [])+parts[1:]
            name=parts[0].lower();values=parts[1:]
            if name=='include':
                for pattern in values:
                    expanded=expand_path(pattern,Path.home()/'.ssh')
                    for included in sorted(glob.glob(str(expanded)))[:32]:visit(included,depth+1)
                continue
            if name=='host':
                events.append(('host',values))
                for alias in values:
                    if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',alias):aliases.setdefault(alias,path)
            elif name=='match':events.append(('match',[]))
            elif name in ('hostname','user','port','identityfile','identitiesonly','proxycommand','proxyjump','remotecommand','certificatefile'):
                events.append((name,values))
    visit(Path.home()/'.ssh/config')
    result=[]
    def matches(alias,patterns):
        return any(fnmatch.fnmatchcase(alias,p) for p in patterns if not p.startswith('!')) and not any(fnmatch.fnmatchcase(alias,p[1:]) for p in patterns if p.startswith('!'))
    for alias,source in aliases.items():
        active=True;conditional=False;values={};advanced=False;conditional_seen=False
        for key,data in events:
            if key=='host':active=matches(alias,data);conditional=False
            elif key=='match':active=False;conditional=True;conditional_seen=True
            elif active and not conditional:
                if key in ('proxycommand','proxyjump','remotecommand','certificatefile'):advanced=True
                elif key not in values and data:values[key]=' '.join(data)
        hostname=values.get('hostname',alias)
        if re.search(r'://[^/\s]+@',hostname):continue
        details={key:values[key] for key in ('hostname','user','port','identityfile','identitiesonly') if key in values}
        details.update(alias=alias,advanced_options=advanced,conditional_options=conditional_seen,
                       authentication='not_checked_live')
        kind='git-ssh' if values.get('user')=='git' or re.match(r'^(github|gitlab)([.-]|$)',alias) else 'ssh'
        result.append(candidate(kind,alias,source,alias,details))
    if any(key=='match' for key,_ in events):warnings.append('SSH Match 조건은 실행하지 않습니다. 표시된 값은 정적 감지이며 원본 규칙을 유지합니다.')
    source_revision=digest([(p,Path(p).stat().st_mtime_ns,Path(p).stat().st_size) for p in sorted(visited)])
    for item in result:
        item['details']['source_revision']=source_revision;item['fingerprint']=digest(item['details'])
    return result,dict(sources=sorted(visited),warnings=warnings)


def shell_configuration():
    path=Path.home()/'.zshrc'
    try:text=read_config(path)
    except (OSError,ValueError):return [],dict(configured=False,sources=[])
    details=dict(shell='zsh',resolved_source=str(path.resolve()))
    # Whitelisted literal assignments only. No source/eval, substitutions or environment exports.
    for key,label in [('ZSH_THEME','theme'),('ZSH','framework')]:
        found=re.findall(r'(?m)^\s*(?:export\s+)?'+key+r'''\s*=\s*["']?([A-Za-z0-9_./${}~-]+)["']?\s*(?:#.*)?$''',text)
        if found:details[label]=found[-1]
    shell=Path.home()/'.config/dotfiles/shell.zsh'
    if shell.exists():details['integration_source']=str(shell.resolve())
    details['source_revision']=digest([(str(p),p.stat().st_mtime_ns,p.stat().st_size) for p in [path,shell] if p.exists()])
    return [candidate('shell','현재 zsh 설정',path,'zshrc',details)],dict(configured=True,sources=[str(path),str(path.resolve())])


def references():
    path=store()
    try:
        if path.is_symlink() or path.parent.is_symlink():raise ValueError('unsafe_reference_store')
        if not path.exists():return []
        if path.stat().st_mode&0o077 or path.stat().st_uid!=os.geteuid():raise ValueError('unsafe_reference_store')
        data=json.loads(read_config(path))
        if not isinstance(data,dict) or set(data)!={'schema','references'} or data['schema']!=1 or not isinstance(data['references'],list) or len(data['references'])>200:
            raise ValueError('invalid_reference_store')
        for ref in data['references']:
            if not isinstance(ref,dict) or set(ref)!={'id','category','label','source','locator','fingerprint'} or any(not isinstance(v,str) or len(v)>4096 or any(ord(c)<32 for c in v) for v in ref.values()):raise ValueError('invalid_reference_store')
        return data['references']
    except (OSError,TypeError,json.JSONDecodeError):raise ValueError('invalid_reference_store')


def observe(preview=False):
    if preview:return dict(scope='example_only',observed_at=None,revision='preview',tools=[],candidates=[],references=[],git={},ssh={},shell={},warnings=[])
    observations=[]
    for discover in (git_configuration,ssh_configuration,shell_configuration):
        try:observations.append(discover())
        except (OSError,ValueError,UnicodeError):observations.append(([],dict(sources=[],warnings=['일부 기존 설정을 감지하지 못했습니다. 원본 경로와 권한을 확인하세요.'])))
    (git,gmeta),(ssh,smeta),(shell,hmeta)=observations
    candidates=git+ssh+shell
    error=''
    try:registered=references()
    except ValueError:registered=[];error='기존 설정 참조 파일을 읽을 수 없습니다. 원본을 확인한 뒤 다시 시도하세요.'
    current={item['id']:item for item in candidates}
    linked=[]
    for ref in registered:
        item=current.get(ref['id'])
        linked.append(dict(ref,status='missing' if item is None else 'current' if ref['fingerprint']==item['fingerprint'] else 'changed'))
    tools=[]
    for ident,name in COMMANDS:
        executable=shutil.which(ident)
        if ident=='tailscale' and not executable:
            app=Path('/Applications/Tailscale.app/Contents/MacOS/Tailscale')
            if app.is_file():executable=str(app)
        tools.append(dict(id=ident,name=name,installed=bool(executable),path=executable))
    return dict(scope='local_configuration_only',observed_at=datetime.now(timezone.utc).isoformat(),
        revision=digest([candidates,registered,error]),tools=tools,candidates=candidates,references=linked,
        git=gmeta,ssh=smeta,shell=hmeta,warnings=gmeta.get('warnings',[])+smeta.get('warnings',[])+hmeta.get('warnings',[])+([error] if error else []))


def register(ids,revision,remove=False):
    if not isinstance(ids,list) or not ids or len(ids)>200 or any(not isinstance(i,str) or not re.fullmatch('[a-f0-9]{20}',i) for i in ids) or len(set(ids))!=len(ids):raise ValueError('가져올 설정을 선택하세요.')
    if not isinstance(revision,str):raise ValueError('설정 감지 버전이 없습니다.')
    path=store();parent=path.parent
    if any(p.is_symlink() for p in (parent,*parent.parents)):raise ValueError('unsafe_reference_store')
    # Check freshness before making even the reference directory/lock file.
    initial=observe()
    if initial['revision']!=revision:raise ValueError('기존 설정이 바뀌었습니다. 다시 감지한 뒤 검토하세요.')
    parent.mkdir(parents=True,exist_ok=True);parent.chmod(0o700)
    lock=parent/'existing-settings.lock'
    descriptor=os.open(lock,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'w') as output:
        fcntl.flock(output,fcntl.LOCK_EX)
        current=observe()
        if current['revision']!=revision:raise ValueError('다른 창 또는 원본 설정이 바뀌었습니다. 다시 감지하세요.')
        saved=references();available={c['id']:c for c in current['candidates']}
        if remove:
            if not set(ids)<={r['id'] for r in saved}:raise ValueError('등록된 참조가 아닙니다.')
            saved=[r for r in saved if r['id'] not in ids]
        else:
            if not set(ids)<=set(available):raise ValueError('현재 감지된 설정만 가져올 수 있습니다.')
            saved=[r for r in saved if r['id'] not in ids]
            saved += [{key:available[ident][key] for key in ('id','category','label','source','locator','fingerprint')} for ident in ids]
        if len(saved)>200:raise ValueError('최대 200개 참조를 관리할 수 있습니다.')
        cfg.atomic(path,(json.dumps(dict(schema=1,references=saved),ensure_ascii=False,indent=2)+'\n').encode())
    return observe()
