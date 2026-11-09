"""Local workflow broker: sessions stay in memory; HTTP returns metadata/public keys only."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
CREATION_LOCK=threading.Lock()

import configuration as cfg
import auth
import terminal_handoff
import legacy_secrets
from secret_store import read_bitwarden

class Workflow:
    def __init__(self,origin):
        self.origin=origin;self.lock=threading.RLock();self.session=None;self.expires=0
        self.generation=None;self.ticket=None;self.ticket_until=0;self.launch_dir=None
        self.items={};self.prepared={};self.agent_env=None;self.dedicated_socket=False;self.owned_pid=None;self.agent_dir=None;self.added={};self.closed=False;self.session_timer=None
    def run(self,args,**kw):
        try:return subprocess.run(args,capture_output=True,text=True,timeout=30,**kw)
        except (OSError,subprocess.TimeoutExpired):raise ValueError('필요한 도구 실행에 실패했습니다. 설치·터미널 상태를 확인하세요.') from None
    def vault_run(self,args,**kw):
        if not self.session or time.monotonic()>=self.expires:
            self.forget();raise ValueError('대시보드 연결이 없거나 만료되었습니다. 터미널에서 다시 연결하세요.')
        env=dict(os.environ,BW_SESSION=self.session);env.pop('BITWARDENCLI_DEBUG',None)
        return self.run(args,env=env,**kw)
    def forget(self):
        if self.session_timer:self.session_timer.cancel();self.session_timer=None
        self.session=None;self.expires=0;self.generation=None;self.items.clear();self.prepared.clear()
    def key_status(self):
        import host_inventory
        try:state=cfg.read_settings()[0]
        except (ValueError,OSError,TypeError):return []
        rows=[]
        for c in state['connections']:
            if c['method']=='ssh' and cfg.ssh_mode(c)=='key':rows.append(dict(id=c['id'],name=c['name'],path=c['publicKey'],socket=c.get('agentSocket'),source='saved'))
        for c in host_inventory.observe().get('candidates',[]):
            path=c.get('details',{}).get('identityfile','')
            if c['category'] in ('ssh','git-ssh') and path.endswith('.pub') and not any(row['name']==c['label'] for row in rows):rows.append(dict(id='existing:'+c['id'],name=c['label'],path=path,socket=None,source='existing'))
        for record in self.prepared.values():
            if record['saved'] and not any(row['path']==record['path'] for row in rows):rows.append(dict(id='prepared:'+record['id'],name=record['name'],path=record['path'],socket=record.get('agent_socket'),source='prepared'))
        cache={}
        for row in rows:
            row['state']='public_missing';row['expires_in']=None
            path=Path(row['path']).expanduser()
            try:
                resolved=path.resolve();info=resolved.stat()
                if not stat.S_ISREG(info.st_mode) or not resolved.is_relative_to(Path.home().resolve()) or info.st_uid!=os.getuid() or info.st_size>16384 or not row['path'].endswith('.pub'):continue
                parts=resolved.read_text().split();public=' '.join(parts[:2])
                if len(parts)<2 or not parts[0].startswith(('ssh-','ecdsa-','sk-')):continue
                socket=row['socket'] or os.environ.get('SSH_AUTH_SOCK','')
                if socket not in cache:
                    env=dict(os.environ)
                    if socket:env['SSH_AUTH_SOCK']=socket
                    result=self.run(['ssh-add','-L'],env=env);cache[socket]=None if result.returncode not in (0,1) else {' '.join(line.split()[:2]) for line in result.stdout.splitlines() if len(line.split())>=2}
                row['state']='agent_unavailable' if cache[socket] is None else 'ready' if public in cache[socket] else 'not_loaded'
                if public in self.added:row['expires_in']=max(0,int(self.added[public]-time.time()))
            except (OSError,ValueError,UnicodeError):pass
        return rows
    def prepare_saved(self,connection):
        state=cfg.validate(cfg.read_settings()[0]);c=next((c for c in state['connections'] if c['id']==connection),None)
        if not c or c['method']!='ssh' or cfg.ssh_mode(c)!='key':raise ValueError('저장한 지정 키 연결을 선택하세요.')
        ref=next((ref for ref in state['credentials'] if ref['id']==c['credential'] and ref['source']=='bitwarden'),None)
        if not ref:raise ValueError('이 연결의 키는 기존 공급 도구에서 준비하세요.')
        self.items[ref['item']]=dict(id=ref['item'],name=c['name'],kind=ref['kind'])
        record=self.prepare(ref['item']);stored=self.prepared[record['id']];stored['path']=c['publicKey']
        try:
            public=Path(c['publicKey']).expanduser().resolve();info=public.stat()
            if stat.S_ISREG(info.st_mode) and public.is_relative_to(Path.home().resolve()) and info.st_uid==os.getuid() and info.st_size<=16384:stored['saved']=' '.join(public.read_text().split()[:2])==stored['public']
        except (OSError,UnicodeError):pass
        return dict(stored)
    def prepare_registered(self,ident):
        registration=next((row for row in legacy_secrets.registrations()['items'] if row['id']==ident),None)
        if not registration:raise ValueError('기존 bws 등록 목록을 새로 확인하세요.')
        self.items[registration['item']]=dict(id=registration['item'],name=registration['name'],kind=registration['kind'])
        record=self.prepare(registration['item']);stored=self.prepared[record['id']]
        # Reuse a path only after the actual derived public key matches, never by alias/name.
        matches=[]
        for row in self.key_status():
            try:
                path=Path(row['path']).expanduser().resolve();info=path.stat()
                if not path.is_relative_to(Path.home().resolve()) or not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_size>16384:continue
                if ' '.join(path.read_text().split()[:2])==stored['public']:matches.append(row)
            except (OSError,UnicodeError,ValueError):continue
        if matches:stored.update(path=matches[0]['path'],saved=True)
        stored['existing_connections']=[row['name'] for row in matches]
        return dict(stored)
    def status(self):
        if self.session and time.monotonic()>=self.expires:self.forget()
        for key,deadline in list(self.added.items()):
            if time.time()>=deadline:self.added.pop(key,None)
        if self.session:
            probe=self.vault_run(['bw','status'])
            try:unlocked=not probe.returncode and json.loads(probe.stdout).get('status')=='unlocked'
            except (ValueError,TypeError):unlocked=False
            if not unlocked:self.forget()
        return dict(legacy=legacy_secrets.registrations(),keys=self.key_status(),terminals=terminal_handoff.available(),default_terminal=terminal_handoff.settings(),generation=self.generation,connected=bool(self.session),expires_in=max(0,int(self.expires-time.monotonic())) if self.session else 0,
            pending=bool(self.ticket and time.monotonic()<self.ticket_until),installed={x:bool(shutil.which(x)) for x in ('bw','ssh-add','ssh-keygen','ssh-agent')},
            agent_socket=(self.agent_env or {}).get('SSH_AUTH_SOCK'),managed_keys=len(self.added),prepared=[dict(record) for record in self.prepared.values()])
    def connect(self,launch=False):
        if not shutil.which('bw'):raise ValueError('Bitwarden CLI를 먼저 설치하세요.')
        # This one-time capability is not a vault session. It expires and is single-use.
        self.ticket=secrets.token_urlsafe(32);self.ticket_until=time.monotonic()+300
        if self.launch_dir:self.launch_dir.cleanup()
        self.launch_dir=tempfile.TemporaryDirectory(prefix='dotfiles-vault-connect-')
        request=Path(self.launch_dir.name)/'request.json'
        request.write_text(json.dumps(dict(origin=self.origin,ticket=self.ticket,path=os.environ.get('PATH',''),bw_appdata=os.environ.get('BITWARDENCLI_APPDATA_DIR'))));request.chmod(0o600)
        command=shlex.join([sys.executable,str(cfg.REPO/'bin/secret_session.py'),'--request',str(request)])
        mode='manual'
        if launch:mode=terminal_handoff.open_input(command,terminal_handoff.settings(),self.run)
        return dict(command=command,launched=mode!='manual',handoff_mode=mode,expires_in=300)
    def attach(self,ticket,session):
        if not self.ticket or time.monotonic()>=self.ticket_until or not isinstance(ticket,str) or not hmac.compare_digest(ticket,self.ticket):raise ValueError('연결 요청이 만료되었거나 이미 사용되었습니다.')
        self.ticket=None
        if not isinstance(session,str) or not re.fullmatch(r'[A-Za-z0-9+/=_-]{16,4096}',session):raise ValueError('연결 세션 형식 오류')
        result=self.run(['bw','status'],env=dict(os.environ,BW_SESSION=session))
        try:valid=json.loads(result.stdout).get('status')=='unlocked'
        except (ValueError,TypeError):valid=False
        if result.returncode or not valid:raise ValueError('잠금 해제된 Bitwarden 세션을 확인하지 못했습니다.')
        self.forget();self.session=session;self.generation=secrets.token_hex(8);self.expires=time.monotonic()+900
        self.session_timer=threading.Timer(900,self.expire);self.session_timer.daemon=True;self.session_timer.start()
        return dict(connected=True)
    def expire(self):
        with self.lock:
            if time.monotonic()>=self.expires:self.forget()
    def search(self,query,purpose):
        if not isinstance(query,str) or not 2<=len(query.strip())<=100 or purpose not in ('ssh-key','token'):raise ValueError('검색어를 2~100자로 입력하세요.')
        result=self.vault_run(['bw','list','items','--search',query,'--nointeraction'])
        if result.returncode:raise ValueError('항목을 읽지 못했습니다. 저장소 연결을 다시 확인하세요.')
        try:raw=json.loads(result.stdout)
        except ValueError:raise ValueError('항목 목록 형식 오류') from None
        if not isinstance(raw,list):raise ValueError('항목 목록 형식 오류')
        records=[]
        for item in raw:
            if not isinstance(item,dict) or item.get('deletedDate'):continue
            ident=item.get('id');kind={1:'login',2:'note',5:'sshkey'}.get(item.get('type'))
            if not isinstance(ident,str) or not re.fullmatch(r'[A-Za-z0-9-]{1,100}',ident) or not kind:continue
            if purpose=='ssh-key' and kind not in ('note','sshkey') or purpose=='token' and kind not in ('note','login'):continue
            entry=dict(id=ident,name=str(item.get('name',''))[:200],kind=kind)
            self.items[ident]=entry;records.append(entry)
            if len(records)>=50:break
        del raw
        return dict(items=records,limit=50)
    def entry(self,ident,purpose):
        entry=self.items.get(ident)
        if not entry or entry['kind'] not in (('note','sshkey') if purpose=='ssh-key' else ('note','login')):raise ValueError('현재 연결에서 검색한 항목을 먼저 선택하세요.')
        # Require the session even when public metadata is already cached.
        if not self.session or time.monotonic()>=self.expires:self.forget();raise ValueError('저장소 연결이 만료되었습니다.')
        return entry
    def prepare(self,ident):
        entry=self.entry(ident,'ssh-key');value=read_bitwarden(ident,entry['kind'],self.vault_run)
        try:derived=auth.derive_public(value)
        finally:del value
        parts=derived.stdout.split()
        if derived.returncode or len(parts)<2:raise ValueError('공개키를 추출하지 못했습니다. 암호가 필요한 키는 기존 SSH agent에서 먼저 준비하세요.')
        public=' '.join(parts[:2]);fingerprint='SHA256:'+__import__('base64').b64encode(hashlib.sha256(__import__('base64').b64decode(parts[1])).digest()).decode().rstrip('=')
        prepared_id=secrets.token_urlsafe(20)
        record=dict(id=prepared_id,item=entry['id'],name=entry['name'],kind=entry['kind'],public=public,fingerprint=fingerprint,path='~/.ssh/keys/bw-'+entry['id'][:8]+'.pub',saved=False,loaded=False)
        self.prepared[prepared_id]=record
        return dict(record)
    def public_record(self,ident):
        record=self.prepared.get(ident)
        if not record:raise ValueError('공개키를 다시 준비하세요.')
        self.entry(record['item'],'ssh-key')
        return record
    def save_public(self,ident,path):
        record=self.public_record(ident)
        if not isinstance(path,str) or not path.endswith('.pub'):raise ValueError('.pub 공개키 경로를 지정하세요.')
        target=Path(path).expanduser()
        if not target.is_absolute() or not target.resolve().is_relative_to(Path.home().resolve()) or target.is_symlink():raise ValueError('홈 안의 일반 .pub 파일 경로를 지정하세요.')
        target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if target.exists():
            info=target.stat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_size>16384:raise ValueError('기존 파일을 변경하지 않았습니다. 다른 경로를 지정하세요.')
            if ' '.join(target.read_text().split()[:2])!=record['public']:raise ValueError('다른 공개키가 있는 경로입니다. 덮어쓰지 않았습니다.')
        else:
            descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
            with os.fdopen(descriptor,'w') as output:output.write(record['public']+'\n')
        record.update(path=str(target),saved=True);return dict(record)
    def agent(self):
        if self.agent_env:return self.agent_env
        env={k:v for k,v in os.environ.items() if not (k in ('BW_SESSION','BW_CLIENTSECRET','GH_TOKEN','GITHUB_TOKEN','GITLAB_TOKEN','GLAB_TOKEN') or k.endswith('_TOKEN'))}
        probe=self.run(['ssh-add','-l'],env=env)
        if probe.returncode in (0,1):self.agent_env=env;return env
        self.agent_dir=cfg.DATA/'agent'
        if not self.agent_dir.resolve().is_relative_to(Path.home().resolve()) or self.agent_dir.is_symlink():raise ValueError('안전한 전용 agent 경로가 아닙니다.')
        self.agent_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
        info=self.agent_dir.stat()
        if info.st_uid!=os.getuid() or info.st_mode&0o077:raise ValueError('전용 agent 폴더는 본인만 접근할 수 있어야 합니다.')
        socket=str(self.agent_dir/'agent.sock');self.dedicated_socket=True
        if len(os.fsencode(socket))>100:raise ValueError('전용 agent 경로가 너무 깁니다. 기존 SSH agent를 먼저 준비하세요.')
        candidate=dict(env,SSH_AUTH_SOCK=socket)
        if os.path.lexists(socket):
            info=Path(socket).lstat()
            if not stat.S_ISSOCK(info.st_mode) or info.st_uid!=os.getuid():raise ValueError('기존 파일을 agent 소켓으로 덮어쓰지 않습니다.')
            if self.run(['ssh-add','-l'],env=candidate).returncode in (0,1):self.agent_env=candidate;return candidate
            Path(socket).unlink()  # Stale socket in this private, application-owned directory only.
        result=self.run(['ssh-agent','-a',socket,'-s'],env=env)
        pid=re.search(r'SSH_AGENT_PID=(\d+)',result.stdout)
        if result.returncode or not pid:raise ValueError('SSH agent를 시작하지 못했습니다.')
        self.owned_pid=int(pid.group(1));env.update(SSH_AUTH_SOCK=socket,SSH_AGENT_PID=str(self.owned_pid));self.agent_env=env;return env
    def supply(self,ident,lifetime):
        if type(lifetime) is not int or not 60<=lifetime<=86400:raise ValueError('키 유지 시간은 60~86400초입니다.')
        record=self.public_record(ident)
        if not record['saved']:raise ValueError('공개키 파일을 먼저 저장하세요.')
        env=self.agent();runner=lambda args,**kw:self.run(args,env=env,**kw)
        added=auth.add(record['item'],record['kind'],lifetime,record['path'],runner=runner,fetcher=lambda item,kind,private=False:read_bitwarden(item,kind,self.vault_run))
        for key in added:self.added[key]=time.time()+lifetime
        record.update(loaded=True,agent_socket=env.get('SSH_AUTH_SOCK'),dedicated_agent=self.dedicated_socket)
        return dict(record,added=bool(added),lifetime=lifetime if added else None)
    def check_token(self,ident):
        entry=self.entry(ident,'token');value=read_bitwarden(ident,entry['kind'],self.vault_run)
        try:
            if not value.strip() or len(value)>65536 or any(c in value for c in ('\n','\r','\0')):raise ValueError('한 줄 토큰 형식이 아닙니다. 올바른 항목을 선택하세요.')
        finally:del value
        return dict(ready=True,item=entry['id'],name=entry['name'],kind=entry['kind'])
    def cleanup(self):
        errors=0
        if self.agent_env:
            for key in list(self.added):
                result=self.run(['ssh-add','-d','-'],input=key+'\n',env=self.agent_env)
                # Expired keys may already be absent; check identity before retaining failure.
                if result.returncode:
                    probe=self.run(['ssh-add','-L'],env=self.agent_env)
                    if key in probe.stdout:errors+=1;continue
                self.added.pop(key,None)
        if errors:raise ValueError('일부 agent 키를 정리하지 못했습니다. 다시 시도하세요.')
        for record in self.prepared.values():record['loaded']=False
        return dict(removed=True)
    def dispatch(self,request):
        with self.lock:
            if self.closed:raise ValueError('대시보드가 종료 중입니다.')
            action=request.get('action')
            allowed={'status':set(),'set_terminal':{'terminal'},'connect':{'launch'},'search':{'query','purpose'},'prepare_registered':{'registration'},'prepare_saved':{'connection'},'prepare_public':{'item'},'save_public':{'id','path'},'supply_key':{'id','lifetime'},'check_token':{'item'},'cleanup':set(),'disconnect':set()}
            if action not in allowed or set(request)-{'action'}!=allowed[action]:raise ValueError('지원하지 않는 비밀 관리 요청입니다.')
            if action=='status':return self.status()
            if action=='set_terminal':return terminal_handoff.save(request['terminal'])
            if action=='connect':return self.connect(request['launch'] is True)
            if action=='search':return self.search(request['query'],request['purpose'])
            if action=='prepare_registered':return self.prepare_registered(request['registration'])
            if action=='prepare_saved':return self.prepare_saved(request['connection'])
            if action=='prepare_public':return self.prepare(request['item'])
            if action=='save_public':return self.save_public(request['id'],request['path'])
            if action=='supply_key':return self.supply(request['id'],request['lifetime'])
            if action=='check_token':return self.check_token(request['item'])
            if action=='cleanup':return self.cleanup()
            self.forget();return dict(disconnected=True)
    def close(self):
        with self.lock:
            self.closed=True
            try:self.cleanup()
            except (ValueError,OSError):pass
            self.forget();self.ticket=None
            if self.owned_pid and self.agent_env:
                # Never terminate an agent with unrelated identities.
                probe=self.run(['ssh-add','-l'],env=self.agent_env)
                if probe.returncode==1:
                    self.run(['ssh-agent','-k'],env=self.agent_env)
                    if self.agent_dir:shutil.rmtree(self.agent_dir,ignore_errors=True)
            if self.launch_dir:self.launch_dir.cleanup()
