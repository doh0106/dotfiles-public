"""Explicit setup acknowledgements, separate from configuration and live authentication."""
import datetime
import hashlib
import json
import fcntl
import configuration as cfg

STEPS=('appearance','tools','profiles','connections','apply','shell','auth')

def basis(state,step):
    if step=='appearance':return state['features']['ohmyzsh']
    if step=='tools':return {k:v for k,v in state['features'].items() if k!='ohmyzsh'}
    if step=='profiles':return {k:state[k] for k in ('git','profiles')}
    if step=='connections':return {k:state[k] for k in ('git','profiles','connections','credentials','session')}
    return state

def fingerprint(state,step):
    return hashlib.sha256(json.dumps(basis(state,step),sort_keys=True,separators=(',',':')).encode()).hexdigest()

def read():
    try:raw=json.loads((cfg.DATA/'setup-progress.json').read_text())
    except FileNotFoundError:return {}
    if not isinstance(raw,dict) or raw.get('schema')!=1 or not isinstance(raw.get('steps'),dict):raise ValueError('설정 진행 기록을 읽을 수 없습니다.')
    return raw['steps']

def status(state,preview=False):
    records={} if preview else read()
    return {step:dict(done=records.get(step,{}).get('fingerprint')==fingerprint(state,step),completed_at=records.get(step,{}).get('completed_at')) for step in STEPS}

def record(step,completed,state,revision):
    if step not in STEPS or not isinstance(completed,bool):raise ValueError('설정 단계 형식 오류')
    state=cfg.validate(state)
    cfg.DATA.mkdir(parents=True,exist_ok=True);cfg.DATA.chmod(0o700)
    with (cfg.DATA/'.setup-progress.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        # Application acknowledgements always belong to the current saved configuration.
        if cfg.revision()!=revision:raise ValueError('설정이 다른 곳에서 바뀌었습니다. 새로고침 후 확인하세요.')
        if completed and step in ('apply','shell','auth'):
            saved,_,_=cfg.read_settings()
            if revision=='new' or state!=saved:raise ValueError('현재 초안을 먼저 저장한 뒤 적용 완료를 확인하세요.')
        records=read()
        if completed:records[step]=dict(fingerprint=fingerprint(state,step),completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
        else:records.pop(step,None)
        cfg.atomic(cfg.DATA/'setup-progress.json',(json.dumps(dict(schema=1,steps=records),indent=2)+'\n').encode())
    return status(state)
