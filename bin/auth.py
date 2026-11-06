#!/usr/bin/env python3
"""Credential routing for SSH, HTTPS Git and service API clients. No secret files."""
import argparse
import errno
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from configuration import endpoint,host_parts

DATA=Path.home()/'.config/dotfiles/dashboard'


def run(args, **kw):
    try:return subprocess.run(args, capture_output=True, text=True, **kw)
    except OSError:raise RuntimeError('필요한 명령을 찾을 수 없습니다: '+args[0]) from None


def configuration():
    try:
        data=json.loads((DATA/'profiles.json').read_text())
        if data.get('schema')!=3:raise RuntimeError('인증 설정을 새 형식으로 생성해야 합니다. dashboard.py configure를 실행하세요.')
        return data
    except (OSError,ValueError):raise RuntimeError('대시보드에서 프로필과 연결을 저장하고 configure하세요.') from None


def choose(config, explicit=None):
    if explicit:
        if explicit not in config['profiles']:raise RuntimeError('설정되지 않은 프로필입니다.')
        return explicit,config['profiles'][explicit]
    common=run(['git','rev-parse','--path-format=absolute','--git-common-dir'])
    if common.returncode:raise RuntimeError('저장소 밖에서는 --connection ID 또는 --profile ID를 명시하세요.')
    gitdir=Path(common.stdout.strip()).resolve()
    matches=[name for name,p in config['profiles'].items() if Path(p['directory']).resolve() in (gitdir,*gitdir.parents)]
    if len(matches)!=1:raise RuntimeError('이 저장소의 Git 폴더 프로필이 없습니다. 대시보드의 프로필 폴더를 확인하세요.')
    profile=run(['git','config','--get','dotfiles.profile'])
    if profile.returncode or profile.stdout.strip()!=matches[0]:raise RuntimeError('폴더와 Git 프로필이 일치하지 않습니다. configure 또는 로컬 Git override를 확인하세요.')
    return matches[0],config['profiles'][matches[0]]


def fetch(item, kind, private=False):
    if not item:raise RuntimeError('Bitwarden 항목 이름이 설정되지 않았습니다.')
    verb='item' if kind=='sshkey' else 'password' if kind=='login' else 'notes'
    result=run(['bw','get',verb,item,'--nointeraction'])
    if result.returncode:raise RuntimeError('Bitwarden 항목 조회 실패. 항목 이름·형식·잠금 상태를 확인하세요.')
    value=result.stdout.rstrip('\n')
    if kind=='sshkey':
        try:value=json.loads(value)['sshKey']['privateKey']
        except (ValueError,KeyError,TypeError):raise RuntimeError('SSH Key 항목 형식이 올바르지 않습니다.') from None
    if not isinstance(value,str) or not value.strip():raise RuntimeError('Bitwarden 항목이 비어 있습니다.')
    return value


def keys():
    result=run(['ssh-add','-L'])
    if result.returncode not in (0,1):raise RuntimeError('SSH agent에 연결할 수 없습니다.')
    # Keep public key type+blob; comments are not identity and may differ.
    return {' '.join(line.split()[:2]) for line in result.stdout.splitlines() if len(line.split())>=2}


def derive_public(value):
    """OpenSSH reads a 0600 FIFO; key bytes stay in the kernel pipe, never a regular file.

    macOS can give anonymous stdin pipes mode 0660, which ssh-keygen correctly rejects.
    Establish the private pipe permissions before starting the key reader.
    """
    if len(value.encode())>131072:raise RuntimeError('SSH 개인키 입력 크기를 확인하세요.')
    with tempfile.TemporaryDirectory(prefix='dotfiles-key-pipe-') as directory:
        path=Path(directory)/'input';os.mkfifo(path,0o600)
        process=subprocess.Popen(['ssh-keygen','-y','-P','','-f',str(path)],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        descriptor=None
        try:
            deadline=time.monotonic()+5
            while descriptor is None:
                try:descriptor=os.open(path,os.O_WRONLY|os.O_NONBLOCK)
                except OSError as error:
                    if error.errno!=errno.ENXIO or process.poll() is not None or time.monotonic()>deadline:
                        raise RuntimeError('개인키에서 공개키를 확인하지 못했습니다.') from None
                    time.sleep(.01)
            os.set_blocking(descriptor,True)
            material=memoryview((value+'\n').encode())
            while material:material=material[os.write(descriptor,material):]
            os.close(descriptor);descriptor=None
            output,diagnostic=process.communicate(timeout=5)
            return subprocess.CompletedProcess(process.args,process.returncode,output,'')
        except (OSError,subprocess.TimeoutExpired):
            raise RuntimeError('개인키에서 공개키를 확인하지 못했습니다.') from None
        finally:
            if descriptor is not None:os.close(descriptor)
            if process.poll() is None:process.kill()
            process.communicate()


def add(item, kind, lifetime, public_path=None):
    before=keys();expected=None
    if public_path:
        try:parts=Path(public_path).expanduser().read_text().split()
        except OSError:raise RuntimeError('프로필의 공개키 파일을 먼저 준비하세요.') from None
        if len(parts)<2:raise RuntimeError('공개키 파일 형식이 올바르지 않습니다.')
        expected=' '.join(parts[:2])
        if expected in before:
            print('이미 agent에 있는 키를 재사용합니다. 기존 키의 만료시간은 변경하지 않습니다.',file=sys.stderr)
            return []
    value=fetch(item,kind,private=True)
    try:
        # Validate before ssh-add so a mismatched vault item cannot reset the TTL
        # of a different identity already present in a shared agent.
        derived=derive_public(value)
        public=' '.join(derived.stdout.split()[:2])
        if derived.returncode or not public:raise RuntimeError('개인키에서 공개키를 확인하지 못했습니다. 추가 passphrase가 필요한 키는 기존 agent에서 준비하세요.')
        if expected and public!=expected:raise RuntimeError('Bitwarden 키와 공개키가 다릅니다. agent에 키를 추가하지 않았습니다.')
        if public in before:
            print('이미 agent에 있는 키를 재사용합니다. 기존 TTL은 변경하지 않습니다.',file=sys.stderr)
            return []
        result=run(['ssh-add','-t',str(lifetime),'-'],input=value+'\n')
    finally:del value
    after=keys();added=after-before
    if result.returncode or (expected and expected not in after):
        for public in added:run(['ssh-add','-d','-'],input=public+'\n')
        raise RuntimeError('키 로드 실패 또는 공개키 불일치. 새로 추가된 키는 제거했습니다.')
    return sorted(added)


def selection(config, explicit=None, connection=None, tool=None, https_host=None):
    if connection:
        selected=config['connections'].get(connection)
        if not selected:raise RuntimeError('활성 연결을 찾을 수 없습니다.')
        if explicit and explicit!=selected['profile']:raise RuntimeError('프로필과 연결이 일치하지 않습니다.')
        explicit=selected['profile']
    name,profile=choose(config,explicit)
    candidates=[c for c in config['connections'].values() if c['profile']==name]
    if connection:candidates=[c for c in candidates if c['id']==connection]
    if tool:candidates=[c for c in candidates if c['api']['enabled'] and c['api']['tool']==tool]
    if https_host is not None:
        candidates=[c for c in candidates if c['kind']=='git' and c['method']=='https' and endpoint(c['host'],'https')==endpoint(https_host,'https') and c['credential']]
    elif not connection:
        origin=run(['git','remote','get-url','origin'])
        if origin.returncode==0:
            host,method=remote_endpoint(origin.stdout.strip())
            if host:
                # Never fall back to an unrelated service when origin is known.
                candidates=[c for c in candidates if endpoint(c['host'],c['method'])==endpoint(host,method) and (tool or c['method']==method)]
    if len(candidates)!=1:raise RuntimeError('연결을 하나로 고를 수 없습니다. --connection ID를 명시하거나 현재 remote/프로필을 확인하세요.')
    return name,profile,candidates[0]


def remote_endpoint(url):
    from urllib.parse import urlsplit
    if url.startswith(('ssh://','https://')):
        parsed=urlsplit(url);return parsed.netloc.split('@')[-1], 'https' if parsed.scheme=='https' else 'ssh'
    import re
    match=re.fullmatch(r'(?:[^/@:]+@)?([^/:]+):.+',url)
    return (match.group(1),'ssh') if match else (None,None)


def value(credential):
    if credential['source']=='bitwarden':return fetch(credential['item'],credential['kind'])
    if credential['source']=='environment':
        token=os.environ.get(credential['variable'],'')
        if not token:raise RuntimeError('선택한 토큰 환경변수가 현재 셸에 없습니다.')
        return token
    raise RuntimeError('이 인증 공급자는 토큰 조회를 지원하지 않습니다.')


def cli_arguments(arguments):
    explicit=connection=None;rest=list(arguments)
    while rest and rest[0] in ('--profile','--connection'):
        if len(rest)<2:raise RuntimeError('옵션 값이 필요합니다.')
        if rest[0]=='--profile':explicit=rest[1]
        else:connection=rest[1]
        rest=rest[2:]
    if rest and rest[0]=='--':rest=rest[1:]
    return explicit,connection,rest


def api_arguments(rest,connection):
    host=endpoint(connection['api'].get('host') or connection['host'],'https')
    if len(rest)>1 and rest[:2]==['auth','status'] and any(arg=='--show-token' or arg.startswith('--show-token=') or (arg.startswith('-') and not arg.startswith('--') and 't' in arg) for arg in rest[2:]):raise RuntimeError('토큰 출력 옵션은 이 wrapper에서 사용하지 않습니다.')
    origin=run(['git','remote','get-url','origin'])
    if origin.returncode==0:
        actual,method=remote_endpoint(origin.stdout.strip())
        if actual and endpoint(actual,method)!=endpoint(connection['host'],connection['method']):raise RuntimeError('현재 저장소와 선택한 API 연결의 호스트가 다릅니다. 저장소 밖에서 실행하거나 해당 호스트의 폴더로 이동하세요.')
    for i,arg in enumerate(rest):
        target=None
        if (arg in ('--hostname','--host') or (rest[:2]==['auth','status'] and arg=='-h')) and i+1<len(rest):target=rest[i+1]
        if arg.startswith(('--hostname=','--host=')):target=arg.split('=',1)[1]
        if target and endpoint(target,'https')!=host:raise RuntimeError('CLI 대상 호스트가 선택한 연결과 다릅니다.')
        repo=None
        if arg.startswith('-R') and arg!='-R':repo=arg[2:]
        if arg in ('-R','--repo') and i+1<len(rest):repo=rest[i+1]
        if arg.startswith('--repo='):repo=arg.split('=',1)[1]
        if repo:
            from urllib.parse import urlsplit
            target=urlsplit(repo).netloc if '://' in repo else repo.split('/')[0] if repo.count('/')>=2 else None
            if target and endpoint(target,'https')!=host:raise RuntimeError('다른 호스트의 저장소에는 해당 연결을 명시하세요.')
        if arg.startswith('http://'):raise RuntimeError('API는 HTTPS URL만 지원합니다.')
        if arg.startswith('https://'):
            from urllib.parse import urlsplit
            if endpoint(urlsplit(arg).netloc,'https')!=host:raise RuntimeError('URL 대상 호스트가 선택한 연결과 다릅니다.')
    if len(rest)>1 and rest[0]=='auth' and rest[1] not in ('status',):raise RuntimeError('명령별 토큰 주입에서는 auth 로그인/저장/토큰 출력 명령을 사용하지 않습니다.')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['load','prepare','needs-vault','needs-gh','needs-glab','extras','gh','glab','credential','check','vault-status'])
    parser.add_argument('arguments',nargs=argparse.REMAINDER)
    args=parser.parse_args();explicit,connection,rest=cli_arguments(args.arguments)
    if args.action=='vault-status':
        result=run(['bw','status'])
        try:state=json.loads(result.stdout)['status']
        except (ValueError,KeyError,TypeError):state=None
        if result.returncode or state not in ('locked','unlocked','unauthenticated'):raise RuntimeError('Bitwarden 상태 오류. unset BW_SESSION 후 다시 시도하세요. invalid_grant가 반복되면 bw logout 후 bwl로 재로그인하세요.')
        print(state);return
    config=configuration()
    if args.action=='extras':
        if run(['bw','sync','--nointeraction']).returncode:raise RuntimeError('Bitwarden 동기화 실패. 로그인/네트워크 상태를 확인하세요.')
        path=Path.home()/'.config/dotfiles/private/secrets.json'
        try:items=json.loads(path.read_text())['secrets']
        except (OSError,ValueError,KeyError):raise RuntimeError('비공개 SSH 추가 목록을 읽을 수 없습니다.') from None
        if any(i.get('action')!='ssh-add' or i.get('bw_type') not in ('note','sshkey') for i in items):raise RuntimeError('--extras는 SSH 키 항목만 지원합니다.')
        for item in items:
            for key in add(item['bw_name'],item['bw_type'],config['lifetime']):print(key,flush=True)
        return
    if args.action=='credential':
        operation=rest[0] if rest else ''
        if operation not in ('get','store','erase'):raise RuntimeError('Git credential helper 작업 오류')
        # Git sends credential data to store/erase: consume it without persisting/logging.
        payload=sys.stdin.read(65537)
        if operation!='get':return
        if len(payload)>65536:raise RuntimeError('credential 요청이 너무 큽니다.')
        request=dict(line.split('=',1) for line in payload.splitlines() if '=' in line)
        if request.get('protocol')!='https' or not request.get('host'):return
        try:name,profile,selected=selection(config,explicit,connection,https_host=request['host'])
        except (RuntimeError,ValueError):return
        credential=config['credentials'][selected['credential']]
        if credential['source']!='bitwarden':return
        token=value(credential)
        try:
            if any(x in token for x in ('\n','\r','\0')):raise RuntimeError('토큰은 한 줄이어야 합니다.')
            # The only secret stdout channel is Git's private helper pipe, never a file.
            print('username='+credential['username']+'\npassword='+token+'\n')
        finally:del token
        return
    tool=(rest.pop(0) if rest else None) if args.action=='needs-vault' else args.action.removeprefix('needs-') if args.action in ('needs-gh','needs-glab') else args.action if args.action in ('gh','glab') else None
    name,profile,selected=selection(config,explicit,connection,tool=tool)
    ref=selected['api']['credential'] if tool else selected['credential']
    credential=config['credentials'].get(ref)
    if args.action in ('needs-vault','needs-gh','needs-glab'):print('bitwarden' if credential and credential['source']=='bitwarden' else 'none');return
    if args.action=='prepare':
        print(selected['method']+'-'+(credential['source'] if credential else 'anonymous'));return
    if args.action in ('load','check'):
        if selected['method']=='https':
            print('HTTPS 인증은 Git credential helper가 요청 시 조회합니다. SSH 키를 로드하지 않습니다.',file=sys.stderr);return
        if args.action=='check' or credential['source']=='agent':
            try:expected=' '.join(Path(selected['publicKey']).expanduser().read_text().split()[:2])
            except OSError:raise RuntimeError('연결의 공개키 파일을 찾을 수 없습니다.') from None
            if expected not in keys():raise RuntimeError('선택한 키가 agent에 없습니다. 공급자 agent에 키를 준비하거나 Bitwarden 로드를 선택하세요.')
            print(selected['id']+': key present (남은 TTL은 조회 불가)',file=sys.stderr);return
        if run(['bw','sync','--nointeraction']).returncode:raise RuntimeError('Bitwarden 동기화 실패. invalid_grant라면 unset BW_SESSION → bw logout → bwl로 복구하세요.')
        for key in add(credential['item'],credential['kind'],config['lifetime'],selected['publicKey']):print(key,flush=True)
        return
    if not rest:rest=['help']
    api_arguments(rest,selected)
    api_host=endpoint(selected['api'].get('host') or selected['host'],'https')
    if rest[:2]==['auth','status']:
        if tool=='glab' and any(arg in ('--all','-a') or arg.startswith('--all=') for arg in rest[2:]):raise RuntimeError('다른 호스트를 함께 조회하지 않습니다. 연결별 auth status를 사용하세요.')
        rest=[*rest,'--hostname',api_host]
    elif rest and rest[0]=='api':rest=[*rest,'--hostname',api_host]
    executable=shutil.which(tool)
    if not executable:raise RuntimeError(tool+' 명령을 먼저 설치하세요.')
    token=value(credential)
    if any(x in token for x in ('\n','\r','\0')):raise RuntimeError('토큰 항목에는 토큰 한 줄만 저장하세요.')
    env=dict(os.environ)
    for key in ('GH_TOKEN','GITHUB_TOKEN','GH_ENTERPRISE_TOKEN','GITHUB_ENTERPRISE_TOKEN','GITLAB_TOKEN','GLAB_TOKEN','GITLAB_ACCESS_TOKEN','OAUTH_TOKEN','CI_JOB_TOKEN','GH_REPO','GITLAB_REPO','GLAB_REPO','GH_DEBUG','DEBUG','GLAB_DEBUG','GLAB_DEBUG_HTTP','GITLAB_API_HOST','GITLAB_URI','GL_HOST','BW_SESSION','BW_PASSWORD','BW_CLIENTSECRET','BW_CLIENTID'):env.pop(key,None)
    for reference in config['credentials'].values():
        if reference['source']=='environment':env.pop(reference['variable'],None)
    api_host=endpoint(selected['api'].get('host') or selected['host'],'https')
    if tool=='gh':
        env['GH_HOST']=api_host;token_key='GH_TOKEN' if (endpoint(api_host,'https')=='github.com' or host_parts(api_host)[0].endswith('.ghe.com')) else 'GH_ENTERPRISE_TOKEN'
    else:
        env['GITLAB_HOST']=api_host;env['GITLAB_API_HOST']=api_host;env['GLAB_API_PROTOCOL']='https';env['GLAB_ENABLE_CI_AUTOLOGIN']='false';token_key='GITLAB_TOKEN'
    origin=run(['git','remote','get-url','origin'])
    if origin.returncode==0:
        from urllib.parse import urlsplit
        url=origin.stdout.strip();actual,method=remote_endpoint(url)
        if actual:
            repo_path=(urlsplit(url).path if '://' in url else url.split(':',1)[1]).strip('/').removesuffix('.git')
            env['GH_REPO' if tool=='gh' else 'GITLAB_REPO']=api_host+'/'+repo_path
    env[token_key]=token
    try:result=subprocess.run([executable,*rest],env=env)
    finally:env.pop(token_key,None);del token
    raise SystemExit(result.returncode)

if __name__=='__main__':
    try:main()
    except (RuntimeError,KeyError,TypeError,ValueError,OSError) as exc:
        print('dotfiles: '+str(exc),file=sys.stderr);raise SystemExit(1)
