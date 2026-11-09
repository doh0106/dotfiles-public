"""UI-owned SSH supply domain. Only public metadata is persisted; BW remains a value adapter."""
import contextlib,fcntl,json,os,stat,subprocess,time
from pathlib import Path
import configuration as cfg
import legacy_secrets
import auth

class SSHDomain:
    def __init__(self,run=None):
        self.run=run or self.execute;self.owned_pid=None;self.owned_socket=None
    @staticmethod
    def execute(args,**kw):
        return subprocess.run(args,capture_output=True,text=True,timeout=30,**kw)
    @property
    def path(self):return cfg.DATA/'ssh-supply.json'
    def read(self):
        try:
            info=self.path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077 or info.st_size>131072:raise ValueError('공유 SSH 상태 파일을 확인하세요.')
            state=json.loads(self.path.read_text())
            if not isinstance(state,dict) or state.get('schema')!=1:raise ValueError('공유 SSH 상태 형식 오류')
            return state
        except FileNotFoundError:return dict(schema=1,socket='',preference='',added={},last_supply=None,sync_before_fetch=True,generations={},manifest='')
    @contextlib.contextmanager
    def transaction(self):
        if cfg.DATA.is_symlink():raise ValueError('관리 폴더 링크를 확인하세요.')
        cfg.DATA.mkdir(parents=True,exist_ok=True,mode=0o700)
        path=cfg.DATA/'.ssh-supply.lock'
        descriptor=os.open(path,os.O_RDWR|os.O_CREAT|getattr(os,'O_NOFOLLOW',0),0o600)
        with os.fdopen(descriptor,'a+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX);yield
    def write(self,state):cfg.atomic(self.path,(json.dumps(state,ensure_ascii=False)+'\n').encode())
    def registrations(self,manifest=None):
        rows={}
        for row in legacy_secrets.registrations(manifest or self.read().get('manifest'))['items']:rows[(row['item'],row['kind'])]=dict(row)
        state=cfg.read_settings()[0]
        for ref in state['credentials']:
            used=any(c['method']=='ssh' and c['credential']==ref['id'] for c in state['connections'])
            if ref['source']!='bitwarden' or ref['kind'] not in ('note','sshkey') or not ref['item'] or not (ref.get('purpose')=='ssh-key' or not ref.get('purpose') and used):continue
            key=(ref['item'],ref['kind'])
            if key not in rows:rows[key]=dict(id=ref['id'],item=ref['item'],name=ref['item'],kind=ref['kind'],purpose='ssh-key',sources=[])
            rows[key]['sources']=list(dict.fromkeys(rows[key]['sources']+[str(cfg.SETTINGS)]))
        return list(rows.values())
    def environment(self,socket):
        env={k:v for k,v in os.environ.items() if not (k.startswith('BW_') or k=='DOTFILES_VAULT_PASSWORD' or k.endswith('_TOKEN'))}
        if socket:env['SSH_AUTH_SOCK']=socket
        return env
    def reachable(self,socket):
        if not socket:return False
        try:
            info=Path(socket).stat()
            return stat.S_ISSOCK(info.st_mode) and info.st_uid==os.getuid() and self.run(['ssh-add','-l'],env=self.environment(socket)).returncode in (0,1)
        except OSError:return False
    def validate_socket(self,socket):
        if not isinstance(socket,str) or not socket.startswith('/') or len(socket)>100 or any(ord(c)<32 for c in socket):raise ValueError('SSH agent 소켓은 절대 경로로 지정하세요.')
    def choose_agent(self,state,requested=None):
        preferred=requested if requested is not None else state.get('preference','')
        dedicated=str(cfg.DATA/'agent/agent.sock')
        if preferred:
            self.validate_socket(preferred)
            if self.reachable(preferred):state['socket']=preferred;return self.environment(preferred)
            if preferred!=dedicated:raise ValueError('지정한 agent에 연결할 수 없습니다. 기존 agent를 덮어쓰지 않았습니다.')
        else:
            for socket in [state.get('socket',''),os.environ.get('SSH_AUTH_SOCK',''),dedicated]:
                if self.reachable(socket):state['socket']=socket;return self.environment(socket)
        directory=cfg.DATA/'agent'
        if directory.is_symlink() or not directory.resolve().is_relative_to(Path.home().resolve()):raise ValueError('안전한 agent 경로가 아닙니다.')
        directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        info=directory.stat()
        if info.st_uid!=os.getuid() or info.st_mode&0o077:raise ValueError('agent 폴더 권한을 확인하세요.')
        self.validate_socket(dedicated)
        if os.path.lexists(dedicated):
            info=Path(dedicated).lstat()
            if not stat.S_ISSOCK(info.st_mode) or info.st_uid!=os.getuid():raise ValueError('기존 파일은 덮어쓰지 않습니다.')
            Path(dedicated).unlink()
        result=self.run(['ssh-agent','-a',dedicated,'-s'],env=self.environment(''))
        import re
        pid=re.search(r'SSH_AGENT_PID=(\d+)',result.stdout)
        if result.returncode or not pid:raise ValueError('SSH agent 시작 실패')
        self.owned_pid=int(pid.group(1));self.owned_socket=dedicated;state['socket']=dedicated;return self.environment(dedicated)
    def set_agent(self,socket):
        if socket:self.validate_socket(socket)
        with self.transaction():
            state=self.read()
            if socket and socket!=str(cfg.DATA/'agent/agent.sock') and not self.reachable(socket):raise ValueError('연결 가능한 agent 소켓을 지정하세요.')
            state['preference']=socket
            if socket:state['socket']=socket
            self.write(state)
        return self.status()
    def agent(self):
        with self.transaction():
            state=self.read();env=self.choose_agent(state);self.write(state);return env
    def set_manifest(self,path):
        if not isinstance(path,str):raise ValueError('등록 목록 경로 형식 오류')
        if path:
            target=Path(path).expanduser().resolve();info=target.stat()
            if not target.is_relative_to(Path.home().resolve()) or not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_size>262144:raise ValueError('홈 안의 등록 목록 파일을 선택하세요.')
            result=legacy_secrets.registrations(str(target))
            if result['warnings'] and not result['items']:raise ValueError('SSH 등록 목록을 읽지 못했습니다.')
            path=str(target)
        with self.transaction():
            state=self.read();state['manifest']=path;self.write(state)
        return self.status()
    def set_sync(self,enabled):
        if type(enabled) is not bool:raise ValueError('동기화 옵션 형식 오류')
        with self.transaction():
            state=self.read();state['sync_before_fetch']=enabled;self.write(state)
        return self.status()
    def generation(self,socket):
        info=Path(socket).stat();return [info.st_dev,info.st_ino]
    def status(self):
        state=self.read();socket=state.get('socket') or os.environ.get('SSH_AUTH_SOCK','');reachable=self.reachable(socket)
        current=auth.keys(lambda args,**kw:self.run(args,env=self.environment(socket),**kw)) if reachable else set()
        return dict(agent_socket=socket,preference=state.get('preference',''),agent_ready=reachable,key_count=len(current),managed_keys=sum(public in current and deadline>time.time() for public,deadline in state.get('added',{}).get(socket,{}).items()),last_supply=state.get('last_supply'),sync_before_fetch=state.get('sync_before_fetch',True),manifest=state.get('manifest',''),inherited_socket=os.environ.get('SSH_AUTH_SOCK',''),dedicated_socket=str(cfg.DATA/'agent/agent.sock'))
    def supply(self,rows,lifetime,fetcher,socket=None,syncer=None,sync=None):
        if type(lifetime) is not int or not 60<=lifetime<=86400:raise ValueError('키 유지 시간은 60~86400초입니다.')
        if not rows:raise ValueError('공급할 등록 키가 없습니다.')
        with self.transaction():
            state=self.read()
            if sync is not None and type(sync) is not bool:raise ValueError('동기화 옵션 형식 오류')
            if (state.get('sync_before_fetch',True) if sync is None else sync) and syncer is not None and syncer().returncode:raise ValueError('Bitwarden 동기화에 실패했습니다. 키는 변경하지 않았습니다.')
            env=self.choose_agent(state,socket);results=[];new=[]
            if socket is not None:state['preference']=socket
            generation=self.generation(env['SSH_AUTH_SOCK'])
            if state.get('generations',{}).get(env['SSH_AUTH_SOCK'])!=generation:state['added'].pop(env['SSH_AUTH_SOCK'],None)
            state.setdefault('generations',{})[env['SSH_AUTH_SOCK']]=generation
            runner=lambda args,**kw:self.run(args,env=env,**kw)
            for row in rows:
                try:
                    added=auth.add(row['item'],row['kind'],lifetime,row.get('publicKey'),runner=runner,fetcher=fetcher)
                    for key in added:state['added'].setdefault(env['SSH_AUTH_SOCK'],{})[key]=time.time()+lifetime;new.append(key)
                    results.append(dict(item=row['item'],kind=row['kind'],state='added' if added else 'reused'))
                except (ValueError,RuntimeError,OSError):results.append(dict(item=row['item'],kind=row['kind'],state='failed',message='항목·Bitwarden 연결·공개키를 확인하세요.'))
                self.write(state) # Preserve earlier successes if a later key fails or the process exits.
            state['last_supply']=dict(results=results,agent_socket=env['SSH_AUTH_SOCK'],dedicated_agent=env['SSH_AUTH_SOCK']==str(cfg.DATA/'agent/agent.sock'));self.write(state)
            return dict(state['last_supply'],added_keys=new)
    def cleanup(self):
        with self.transaction():
            state=self.read()
            for socket,tracked in list(state['added'].items()):
                if not tracked:continue
                if not self.reachable(socket):
                    for public,deadline in list(tracked.items()):
                        if deadline<=time.time():tracked.pop(public,None)
                    continue
                if state.get('generations',{}).get(socket)!=self.generation(socket):state['added'].pop(socket,None);continue
                env=self.environment(socket);present=auth.keys(lambda args,**kw:self.run(args,env=env,**kw))
                for public in list(tracked):
                    if tracked[public]<=time.time():tracked.pop(public,None);continue
                    if public in present and self.run(['ssh-add','-d','-'],input=public+'\n',env=env).returncode:continue
                    tracked.pop(public,None)
                if not tracked:state['added'].pop(socket,None)
            self.write(state)
            if any(state['added'].values()):raise ValueError('일부 agent 키를 해제하지 못했습니다. 해제 기록을 보존했습니다.')
        return dict(removed=True)
    def close_empty_owned(self):
        if self.owned_pid:
            env=self.environment(self.owned_socket)
            if self.run(['ssh-add','-l'],env=env).returncode==1:self.run(['ssh-agent','-k'],env=dict(env,SSH_AGENT_PID=str(self.owned_pid)))
