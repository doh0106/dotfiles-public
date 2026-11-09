"""Secret-management orchestration: source selection -> in-memory key -> agent port."""
import json,os,stat
from pathlib import Path
import configuration as cfg
import legacy_secrets
from secret_store import read_bitwarden

class SecretKeySupply:
    def __init__(self,agent,vault_run):self.agent=agent;self.vault_run=vault_run
    @property
    def path(self):return cfg.DATA/'secret-key-supply.json'
    def read(self):
        try:
            info=self.path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077 or info.st_size>65536:raise ValueError('키 공급 설정을 확인하세요.')
            value=json.loads(self.path.read_text())
            if not isinstance(value,dict):raise ValueError('키 공급 설정 형식 오류')
            return value
        except FileNotFoundError:
            # Previous versions stored source preferences together with agent metadata.
            old=self.agent.read();return dict(manifest=old.get('manifest',''),sync_before_fetch=old.get('sync_before_fetch',True),last_supply=old.get('last_supply'))
    def write(self,state):cfg.DATA.mkdir(parents=True,exist_ok=True,mode=0o700);cfg.atomic(self.path,(json.dumps(state,ensure_ascii=False)+'\n').encode())
    def set_manifest(self,path):
        if not isinstance(path,str):raise ValueError('등록 목록 경로 형식 오류')
        if path:
            target=Path(path).expanduser().resolve();info=target.stat()
            if not target.is_relative_to(Path.home().resolve()) or not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_size>262144:raise ValueError('홈 안의 등록 목록 파일을 선택하세요.')
            result=legacy_secrets.registrations(str(target))
            if result['warnings'] and not result['items']:raise ValueError('SSH 등록 목록을 읽지 못했습니다.')
            path=str(target)
        state=self.read();state['manifest']=path;self.write(state);return state
    def set_sync(self,enabled):
        if type(enabled) is not bool:raise ValueError('동기화 옵션 형식 오류')
        state=self.read();state['sync_before_fetch']=enabled;self.write(state);return state
    def registrations(self):
        rows={}
        for row in legacy_secrets.registrations(self.read().get('manifest'))['items']:rows[(row['item'],row['kind'])]=dict(row)
        state=cfg.read_settings()[0]
        for ref in state['credentials']:
            used=any(c['method']=='ssh' and c['credential']==ref['id'] for c in state['connections'])
            if ref['source']!='bitwarden' or ref['kind'] not in ('note','sshkey') or not ref['item'] or not (ref.get('purpose')=='ssh-key' or not ref.get('purpose') and used):continue
            key=(ref['item'],ref['kind'])
            if key not in rows:rows[key]=dict(id=ref['id'],item=ref['item'],name=ref['item'],kind=ref['kind'],purpose='ssh-key',sources=[])
            rows[key]['sources']=list(dict.fromkeys(rows[key]['sources']+[str(cfg.SETTINGS)]))
        return list(rows.values())
    def supply(self,rows,lifetime):
        if type(lifetime) is not int or not 60<=lifetime<=86400:raise ValueError('키 유지 시간은 60~86400초입니다.')
        if not rows:raise ValueError('공급할 키를 선택하세요.')
        policy=self.read()
        if policy.get('sync_before_fetch',True) and self.vault_run(['bw','sync','--nointeraction']).returncode:raise ValueError('Bitwarden 동기화 실패. agent 키는 바꾸지 않았습니다.')
        results=[];added=[];last=None
        for row in rows:
            material=None
            try:
                material=read_bitwarden(row['item'],row['kind'],self.vault_run)
                last=self.agent.register_materials([dict(name=row['item'],material=material,publicKey=row.get('publicKey'))],lifetime)
                added+=last['added_keys'];results.append(dict(item=row['item'],kind=row['kind'],state=last['results'][0]['state']))
            except (ValueError,RuntimeError,OSError):results.append(dict(item=row['item'],kind=row['kind'],state='failed',message='키 항목·저장소 연결을 확인하세요.'))
            finally:material=None
        status=self.agent.status();report=dict(results=results,agent_socket=status['agent_socket'],dedicated_agent=status['agent_socket']==status['dedicated_socket'])
        policy['last_supply']=report;self.write(policy);return dict(report,added_keys=added)
