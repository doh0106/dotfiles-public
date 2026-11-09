"""Explicit local setup/update jobs. Fixed operations; never execute client command text."""
import copy
import datetime
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import threading
import configuration as cfg
import tool_catalog

class Attention(ValueError):pass

class Control:
    def __init__(self,planner,git_credentials=None):
        self.git_credentials=git_credentials;self.planner=planner;self.lock=threading.RLock();self.thread=None;self.job=None;self.update=None;self.closed=False
    def run(self,args,timeout=900,cwd=None):
        env={k:v for k,v in os.environ.items() if k in ('HOME','PATH','LANG','LC_ALL','TMPDIR','TMP','TEMP','SSH_AUTH_SOCK','GH_CONFIG_DIR','BITWARDENCLI_APPDATA_DIR')}
        env.update(GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='never',NONINTERACTIVE='1')
        if args[0]=='git':
            env.update({key:os.environ[key] for key in ('GH_TOKEN','GITHUB_TOKEN') if os.environ.get(key)})
            if self.git_credentials and 'clone' in args and any(arg.startswith('https://github.com/doh0106/') for arg in args):
                try:env.update(self.git_credentials())
                except (ValueError,RuntimeError):raise Attention('Bitwarden 연결과 GitHub 설치용 환경변수 참조를 확인하세요.') from None
        result=subprocess.run(args,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=timeout)
        if result.returncode:raise Attention('실행하지 못했습니다. 설치 권한·네트워크·저장소 접근을 확인한 뒤 다시 시도하세요.')
    def git(self,*args):
        result=subprocess.run(['git','-C',str(cfg.REPO),*args],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30,env=dict(os.environ,GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='never'))
        if result.returncode:raise Attention('원격 브랜치·인증·네트워크를 확인하세요. 기존 파일은 초기화하지 않습니다.')
        return result.stdout if '-z' in args else result.stdout.strip()
    def status(self):
        with self.lock:
            job=copy.deepcopy(self.job)
            if job is None:
                try:
                    path=cfg.DATA/'environment-run.json'
                    if not path.is_symlink() and path.stat().st_size<=65536:job=json.loads(path.read_text())
                    if job and not isinstance(job,dict):job=None
                    if job:job['restart_required']=False
                    if job and job.get('status')=='running':job['status']='interrupted';job['message']='중단된 작업입니다. 다시 실행하면 설치된 도구는 확인 후 건너뜁니다.'
                except (OSError,ValueError):pass
            return dict(job=job,update=copy.deepcopy(self.update),busy=bool(self.thread and self.thread.is_alive()))
    def persist(self):
        cfg.DATA.mkdir(parents=True,exist_ok=True,mode=0o700)
        cfg.atomic(cfg.DATA/'environment-run.json',(json.dumps(self.job,ensure_ascii=False)+'\n').encode())
    def plans(self,state):
        rows=self.planner(state)['dependencies'];seen={row['id'] for row in rows}
        for command in ('bw','jq'):
            if command not in seen:rows.append(dict(id=command,name=command,installed=bool(shutil.which(command)),steps=[]))
        steps=[]
        for row in rows:
            if row['installed']:continue
            commands=[];ident=row['id'];hint=''
            if row.get('commands'):commands=[shlex.split(command) for command in row['commands']]
            elif sys.platform=='darwin' and shutil.which('brew'):
                formula={'bw':'bitwarden-cli','ssh':'openssh','ssh-add':'openssh','ssh-keygen':'openssh','python3':'python'}.get(ident,ident)
                if ident in {'git','bash','zsh','bw','jq','gh','glab','ssh','ssh-add','ssh-keygen','zellij','yazi'}:commands=[['brew','install',formula]]
            elif shutil.which('apt-get'):
                package={'ssh':'openssh-client','ssh-add':'openssh-client','ssh-keygen':'openssh-client'}.get(ident,ident)
                if ident in {'git','bash','zsh','jq','gh','ssh','ssh-add','ssh-keygen'}:
                    prefix=[] if os.geteuid()==0 else ['sudo','-n']
                    commands=[prefix+['apt-get','update'],prefix+['apt-get','install','-y',package]]
            if not commands:
                hint='OS 설치 또는 관리자 승인이 필요합니다. 프로그램 설치의 안내를 진행하고 다시 적용하세요.'
                if ident=='bw':hint='Bitwarden CLI 설치가 필요합니다. https://bitwarden.com/help/cli/ 안내로 설치한 뒤 다시 적용하세요.'
                elif sys.platform=='darwin' and not shutil.which('brew'):hint='Homebrew 설치가 필요합니다. https://brew.sh 안내로 설치한 뒤 다시 적용하세요.'
            steps.append(dict(id='install-'+ident,title=row['name']+' 설치',commands=commands,hint=hint))
        steps.append(dict(id='configure',title='저장한 설정 적용 · 기존 설정 보존',commands=[[sys.executable,str(cfg.REPO/'bin/dashboard.py'),'configure']],hint=''))
        return steps
    def start(self,action,revision=None):
        with self.lock:
            if self.closed or self.thread and self.thread.is_alive():raise Attention('진행 중인 작업이 있습니다.')
            if action not in ('apply','check_update','update','services','runtime'):raise Attention('지원하지 않는 환경 작업입니다.')
            if action=='apply':
                if revision=='new' or revision!=cfg.revision():raise Attention('현재 설정을 먼저 저장하고 다시 적용하세요.')
                state=cfg.validate(cfg.read_settings()[0]);steps=self.plans(state)
            elif action in ('services','runtime'):steps=[dict(id=action,title='외부 서비스 관리 설치' if action=='services' else '프로젝트 실행 도구 설치',commands=[],hint='')]
            else:steps=[dict(id=action,title='환경 코드 업데이트 확인' if action=='check_update' else '환경 코드 업데이트 가져오기',commands=[],hint='')]
            self.job=dict(action=action,status='running',revision=revision,started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),steps=[dict(id=s['id'],title=s['title'],state='pending') for s in steps],message='')
            self.persist();self.thread=threading.Thread(target=self.execute,args=(steps,revision),daemon=True);self.thread.start();return self.status()
    def execute(self,steps,revision):
        try:
            for index,step in enumerate(steps):
                with self.lock:self.job['steps'][index]['state']='running';self.persist()
                action=self.job['action']
                if action in ('check_update','update'):self.update_code(action=='update')
                elif action in ('services','runtime'):self.install_module(action)
                else:
                    if cfg.revision()!=revision:raise Attention('설정이 다른 창에서 바뀌었습니다. 실행을 중단했습니다. 변경을 확인하고 다시 적용하세요.')
                    if not step['commands']:raise Attention(step['hint'])
                    for command in step['commands']:self.run(command)
                with self.lock:self.job['steps'][index]['state']='done';self.persist()
            with self.lock:
                self.job['status']='done';self.job['message']='설정 적용을 마쳤습니다. 새 터미널에서 셸을 확인하고, 아래에서 필요한 인증을 이어가세요.' if self.job['action']=='apply' else '작업을 마쳤습니다.';self.persist()
        except (ValueError,OSError,subprocess.TimeoutExpired):
            with self.lock:
                self.job['status']='needs_action';self.job['message']=str(sys.exc_info()[1]) if isinstance(sys.exc_info()[1],Attention) else '작업을 완료하지 못했습니다. 설치 권한·네트워크를 확인하고 다시 시도하세요.'
                for step in self.job['steps']:
                    if step['state']=='running':step['state']='needs_action'
                self.persist()
    def update_code(self,apply):
        upstream=self.git('rev-parse','--abbrev-ref','--symbolic-full-name','@{u}')
        if not upstream.startswith('origin/') or not re.fullmatch(r'[A-Za-z0-9/_.-]+',upstream):raise Attention('origin 추적 브랜치를 먼저 설정하세요.')
        branch=upstream[len('origin/'):]
        if apply and self.git('status','--porcelain'):raise Attention('로컬 변경이 있어 업데이트하지 않았습니다. 변경을 보존·정리한 뒤 다시 시도하세요.')
        self.run(['git','-C',str(cfg.REPO),'fetch','--quiet','origin','refs/heads/'+branch+':refs/remotes/origin/'+branch],timeout=120)
        ahead,behind=map(int,self.git('rev-list','--left-right','--count','HEAD...'+upstream).split())
        with self.lock:self.update=dict(branch=branch,ahead=ahead,behind=behind,restart_required=False)
        if apply:
            if self.git('status','--porcelain'):raise Attention('로컬 변경이 있어 업데이트하지 않았습니다.')
            if ahead and behind:raise Attention('로컬·원격 변경이 갈라져 있습니다. 자동 병합하지 않았습니다.')
            if behind:
                additions=self.git('diff','--no-renames','--name-only','--diff-filter=A','-z','HEAD',upstream).split('\0')
                if any(name and ((cfg.REPO/name).exists() or (cfg.REPO/name).is_symlink()) for name in additions):raise Attention('원격의 새 파일이 로컬 보관 파일과 겹칩니다. 기존 파일을 보존하고 업데이트를 중단했습니다.')
                self.run(['git','-C',str(cfg.REPO),'merge','--ff-only',upstream],timeout=120)
                with self.lock:self.update.update(behind=0,restart_required=True)
            with self.lock:self.job['restart_required']=self.update['restart_required']
    def install_module(self,kind):
        import environment_bridge
        locations=environment_bridge.registered_locations();root=Path(locations.get('core_root') or Path.home()/'personal/environment-core')
        runtime=Path(locations.get('runtime_root') or Path.home()/'personal/dev-environment')
        def ensure(path,url,marker,branch=None):
            if path.exists():
                if not (path/marker).is_file():raise Attention('기존 설치 폴더를 덮어쓰지 않았습니다. 저장소 위치를 확인하세요.')
                result=subprocess.run(['git','-C',str(path),'remote','get-url','origin'],capture_output=True,text=True,timeout=5)
                expected=url.removeprefix('https://github.com/').removesuffix('.git')
                allowed=['https://github.com/'+expected,'git@github.com:'+expected,'git@github-personal:'+expected]
                if result.returncode or result.stdout.strip().removesuffix('.git') not in allowed:raise Attention('기존 폴더의 원격 저장소가 다릅니다. 덮어쓰거나 실행하지 않았습니다.')
                return
            path.parent.mkdir(parents=True,exist_ok=True)
            self.run(['git','clone',*(['--branch',branch] if branch else []),url,str(path)],timeout=180)
        ensure(root,'https://github.com/doh0106/environment-core.git','cli.py')
        if kind=='runtime':
            ensure(runtime,'https://github.com/doh0106/dev-environment.git','scripts/install-host-workflow.sh','codex/environment-control')
            self.run(['bash',str(runtime/'scripts/install-host-workflow.sh')])
        command=[sys.executable,str(root/'cli.py')]
        if kind=='runtime' or locations.get('runtime_root'):command+=['--dev-environment-root',str(runtime)]
        command+=['register']
        if locations.get('agent_kit_root'):command+=['--agent-kit-root',locations['agent_kit_root']]
        if locations:command+=['--replace']
        self.run(command)
        environment_bridge.reload_registration()
