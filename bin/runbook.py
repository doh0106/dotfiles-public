"""Ordered, conditional instructions shared by the dashboard and AI handoff."""
from pathlib import Path
import shlex
import configuration as cfg
import features


def block(title,text='',commands=None,when='',links=None,optional=False,example=False):
    return dict(title=title,text=text,commands=commands or [],when=when,links=links or [],optional=optional,example=example)


def build(state,dependencies,repo,data):
    active=[c for c in state['connections'] if c['enabled']]
    credentials={c['id']:c for c in state['credentials']}
    profiles={p['id']:p for p in state['profiles'] if p['enabled']}
    refs={ref for c in active for ref in (([c['credential']] if c['method']!='ssh' or cfg.ssh_mode(c)=='key' and not c.get('agentSocket') else [])+([c['api']['credential']] if c['api']['enabled'] else [])) if ref}
    vault_refs=[credentials[ref] for ref in sorted(refs) if credentials[ref]['source']=='bitwarden']
    stages=[]
    def stage(ident,title,description,blocks,view=None):
        stages.append(dict(id=ident,title=title,description=description,blocks=blocks,view=view))
    checks=[]
    if state['features']['ohmyzsh']['enabled']:
        values=state['features']['ohmyzsh']['values'];checks.append(block('셸과 테마','Oh My Zsh 사용 · '+values['theme']+' · '+values['dir']))
    if state['git']['enabled']:
        for p in profiles.values():checks.append(block('작업 프로필 · '+p['name'],p['id']+' · '+p['path']+' · '+p['author']+' <'+p['email']+'>'))
    for c in active:
        api='API: '+c['api']['tool'] if c['api']['enabled'] else 'API 도구 사용 안 함'
        checks.append(block('연결 · '+c['name'],c['id']+' · 적용 범위 '+(c['profile'] or '프로필 없음 · 연결 ID로 직접 선택')+' · '+c['host']+' · '+c['method'].upper()+' · '+api))
    tool_names=[f['name'] for f in features.DEFINITIONS if state['features'][f['id']]['enabled'] and f['id']!='ohmyzsh']
    if tool_names:checks.append(block('도구 선택',', '.join(tool_names)))
    stage('review','선택한 환경 확인','켜진 기능과 연결만 이 안내에 포함됩니다. 폴더별 신원, 서비스 접속, API 인증은 각각 확인합니다.',checks or [block('선택 기능 없음','필요한 기능을 고른 뒤 안내를 갱신하세요.')],'overview')
    materials=[]
    for c in active:
        if c['method']!='ssh' or cfg.ssh_mode(c)=='system':continue
        path=str(Path(c['publicKey']).expanduser());exists=Path(path).is_file()
        links=[]
        if c['kind']=='git' and c['provider']=='github' and cfg.host_parts(c['host'])[0]=='github.com':links=[dict(label='개인 GitHub 계정의 SSH 키 관리',url='https://github.com/settings/keys')]
        materials.append(block(c['name']+' · 공개키',('파일 있음: ' if exists else '파일 준비 필요: ')+c['publicKey']+'. 대응하는 개인키와 짝이어야 하며, Git 서비스 또는 서버에 공개키가 등록되어 있어야 합니다. 공개키를 Bitwarden에서 자동 추출하지 않습니다.',links=links))
    for reference in vault_refs:
        uses=[c for c in active if c['credential']==reference['id'] or (c['api']['enabled'] and c['api']['credential']==reference['id'])]
        ssh=any(c['method']=='ssh' and c['credential']==reference['id'] for c in uses)
        location={'note':'Secure Note 본문','sshkey':'SSH Key의 private key','login':'Login의 password'}[reference['kind']]
        content='SSH 개인키 전체' if ssh else '토큰 한 줄'
        materials.append(block('Bitwarden · '+reference['id'],'항목 이름/ID: '+reference['item']+' · '+location+'에 '+content+'를 보관합니다. '+('추가 passphrase가 필요한 키는 기존 agent에서 먼저 준비하세요. ' if ssh else '')+'항목 형식이 다르면 연결의 인증 참조를 수정하세요. 비밀값은 대시보드에 입력하지 않습니다.'))
    connection_kinds={c['kind'] for c in active}
    connection_view='servers' if connection_kinds=={'server'} else 'connections' if connection_kinds=={'git'} else 'overview'
    if materials:stage('materials','인증 재료 확인','공개키 파일, 비밀정보 항목의 이름·형식을 확인합니다. 실제 비밀값이나 vault 상태는 이 화면에서 조회하지 않습니다.',materials,connection_view)
    stage('save','검토 후 설정 파일 생성','변경 검토·적용 화면에서 내용을 검토한 뒤 「저장 · 설정 파일 생성」을 누르세요. 저장한 설정을 기준으로 다음 명령을 실행합니다.',[block('저장과 실행은 별개','초안 미리보기는 파일을 바꾸지 않습니다. 이미 같은 값을 저장했다면 그대로 다음 단계로 진행하세요.')])
    missing=[d for d in dependencies if not d['installed']]
    installed=[d for d in dependencies if d['installed']]
    installation=[]
    for dependency in missing:
        commands=list(dependency.get('commands',[]));texts=[dependency['note']] if dependency.get('note') else [];links=[]
        for instruction in dependency['steps']:
            if instruction.startswith('설치 안내: https://'):links.append(dict(label=dependency['name']+' 공식 설치 안내',url=instruction[len('설치 안내: '):]))
            elif instruction.startswith('command -v '):commands.append(instruction)
            else:texts.append(instruction)
        installation.append(block(dependency['name']+' 설치 필요',' '.join(texts),commands,links=links))
    if installed:installation.append(block('설치된 도구 · 재설치 생략',', '.join(d['name'] for d in installed)))
    stage('install','필요한 프로그램 준비',str(len(installed))+'개 설치됨 · '+str(len(missing))+'개 설치 필요. 아래에는 없는 프로그램의 설치 명령·문서만 표시합니다.',installation)
    if state['features']['gitlfs']['enabled']:
        installation.append(block('Git LFS · 저장소별 설정','설치 후 LFS를 사용할 저장소 안에서만 실행하세요. 전역 필터는 자동 설정하지 않습니다.',['git lfs install --local'],when='해당 저장소에서 Git LFS를 사용할 때만',optional=True))
    if any(state['features'][key]['enabled'] for key in ('aws','claude','gemini','ngrok')):
        installation.append(block('서비스 도구의 로그인은 별도','이 안내는 프로그램만 설치합니다. 각 서비스 로그인·토큰 등록·터널 시작은 자동 실행하지 않습니다.'))
    stage('configure','설정 연결 · configure','홈의 관리 설정과 도구 선택를 연결합니다. 이미 설치된 도구는 재설치하지 않으며, 설정을 바꾼 뒤에도 같은 명령을 사용할 수 있습니다.',[block('WSL / macOS / Linux 터미널에서 실행',commands=[shlex.join(['python3',str(repo/'bin/dashboard.py'),'configure'])])])
    stage('shell','새 zsh에서 시작','현재 셸을 새 zsh로 바꿔 선택한 integration을 읽습니다. 기존 셸에서 bws로 키를 로드한 상태라면 먼저 작업을 마치고 세션을 정리하세요.',[block('다음 인증 명령은 새 셸에서 실행',commands=['exec zsh'])])
    if vault_refs:
        stage('vault','Bitwarden 로그인 · 잠금 해제','같은 터미널에서 상태를 확인한 뒤 해당하는 경우 하나만 진행하세요. 이메일·마스터 비밀번호·2FA는 사용자가 직접 입력합니다.',[
            block('현재 CLI 상태 확인',commands=['bw status']),
            block('최초 로그인 또는 로그인 만료','bwl은 raw 세션 값을 화면에 출력하지 않고 현재 셸의 BW_SESSION으로 받습니다. 데스크톱 앱의 로그인과 CLI 로그인은 별개입니다.',['bwl'],when='status가 unauthenticated'),
            block('로그인은 되어 있고 vault만 잠김',commands=['bwu'],when='status가 locked'),
            block('이미 잠금 해제됨','추가 로그인 없이 다음 단계로 진행합니다.',when='status가 unlocked'),
            block('로그인 상태 복구','정상 로그인 중에는 실행하지 마세요. invalid_grant가 반복되거나 CLI 상태를 읽지 못할 때만 로그아웃 후 다시 로그인합니다.',['unset BW_SESSION','bw logout','bwl'],when='invalid_grant / 상태 조회 오류가 반복될 때만',optional=True),
        ])
    preparation=[]
    for c in active:
        credential=credentials.get(c['credential'])
        if c['method']=='ssh' and cfg.ssh_mode(c)=='system':
            preparation.append(block(c['name']+' · 기존 SSH 설정 사용','기존 ~/.ssh/config·agent·SSH 인증 절차에 맡깁니다. 키 로드·vault 로그인·공개키 파일 준비를 요구하지 않습니다. 실제 서버 인증은 별도 확인하세요.'))
        elif c['method']=='ssh' and c.get('agentSocket'):
            preparation.append(block(c['name']+' · 대시보드 전용 agent','SSH 키 준비 화면에서 키를 공급하세요. 이 명령은 해당 agent의 상태만 확인하며 현재 터미널에 다른 agent를 만들거나 키를 다시 로드하지 않습니다.',[shlex.join(['env','SSH_AUTH_SOCK='+c['agentSocket'],'ssh-add','-l'])]))
        elif c['method']=='ssh':
            text=('Bitwarden에서 개인키를 읽어 agent에 로드합니다. 새 키 TTL: '+str(state['session']['keyLifetime'])+'초. 이미 있는 키의 TTL은 바꾸지 않습니다.' if credential and credential['source']=='bitwarden' else '기존 SSH agent에 대응하는 키를 준비하세요. 이 공급자에서는 키를 가져오거나 TTL을 변경하지 않고 공개키 일치 여부를 확인합니다.')
            preparation.append(block(c['name']+' · SSH 키 준비',text,[shlex.join(['ssh-keygen','-lf',str(Path(c['publicKey']).expanduser())]),shlex.join(['bws','--connection',c['id']]),'ssh-add -l']))
        elif credential and credential['source']=='bitwarden':
            preparation.append(block(c['name']+' · HTTPS 인증 준비','vault를 준비합니다. SSH agent는 시작하지 않으며, Git이 인증을 요청할 때 helper가 토큰을 읽습니다.',[shlex.join(['bws','--connection',c['id']])]))
        elif credential and credential['source']=='git-helper':
            preparation.append(block(c['name']+' · 외부 helper','Git credential '+credential['helper']+'의 로그인·보관 정책을 따릅니다. SSH 키 TTL과 bwe의 정리 대상에 포함되지 않습니다.'))
    env_refs={c['api']['credential'] for c in active if c['api']['enabled'] and credentials[c['api']['credential']]['source']=='environment'}
    for ref in sorted(env_refs):preparation.append(block('API 토큰 환경변수 · '+ref,'현재 셸에 '+credentials[ref]['variable']+' 값을 별도로 준비하세요. 설정에는 변수 이름만 저장합니다. 토큰을 터미널 명령 인수나 대시보드에 붙여넣지 마세요.'))
    if preparation:stage('credentials','선택한 연결의 인증 준비','연결 ID를 명시하므로 다른 연결의 키·토큰을 선택하지 않습니다. 명령들은 로그인한 같은 터미널에서 실행합니다.',preparation)
    verification=[]
    for c in active:
        if c['method']=='ssh' and c['kind']=='git':
            hostname,port=cfg.host_parts(c['host']);command=['ssh','-T'] if cfg.ssh_mode(c)=='system' else ['ssh','-F',str(data/('ssh-'+c['profile']+'.config' if c['profile'] else 'ssh-connection-'+c['id']+'.config')),'-T']
            if port:command+=['-p',str(port)]
            command+=[hostname if cfg.ssh_mode(c)=='system' else c['sshUser']+'@'+hostname];links=[]
            text='처음 연결할 때 서버 host key의 fingerprint를 확인하세요. 서비스가 반환한 인증 계정이 본인 계정인지 확인합니다.'
            if c['provider']=='github' and hostname=='github.com':
                text+=' GitHub의 “Hi USERNAME! … successfully authenticated”는 성공 응답이며 종료 코드 1도 정상입니다.'
                links=[dict(label='GitHub 공식 서버 fingerprint',url='https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints'),dict(label='GitHub SSH 연결 확인 안내',url='https://docs.github.com/en/authentication/connecting-to-github-with-ssh/testing-your-ssh-connection')]
            verification.append(block(c['name']+' · SSH 접속 확인',text,[shlex.join(command)],links=links))
        elif c['kind']=='server':
            hostname,port=cfg.host_parts(c['host'])
            target=hostname if cfg.ssh_mode(c)=='system' else c.get('sshAlias') or c['id']
            command=['ssh','-G']+(['-p',str(port)] if port and cfg.ssh_mode(c)=='system' else [])+[target]
            verification.append(block(c['name']+' · SSH 설정 확인','OpenSSH가 적용할 설정을 확인합니다. 원본에 Match exec 등이 있으면 OpenSSH가 실행할 수 있으므로 내용을 먼저 확인하세요. 서버에 접속하는 명령은 아닙니다.',[shlex.join(command)]))
        if c['api']['enabled']:verification.append(block(c['name']+' · '+c['api']['tool']+' API 인증 확인','선택한 API 서비스 호스트의 토큰을 해당 CLI 자식 프로세스에만 전달합니다.',[shlex.join(['bw'+c['api']['tool'],'--connection',c['id'],'auth','status'])]))
        if c['kind']=='git' and c['profile']:verification.append(block(c['name']+' · 저장소 설정과 읽기 권한 확인',(('프로필 폴더 '+profiles[c['profile']]['path']+' 아래의 ' ) if c['profile'] else '연결별 설정을 적용한 ' )+'실제 프로젝트 저장소로 이동한 뒤 실행하세요. origin의 호스트와 '+c['method'].upper()+' 방식이 이 연결과 맞아야 합니다. Git identity 관리를 켰다면 작성자 이메일도 확인하세요.',['git config --get dotfiles.profile','git config --show-origin --get user.email','git remote -v','git ls-remote origin'],when='해당 서비스의 기존 저장소에서 작업할 때만',optional=True))
    for c in active:
        if c['kind']=='git' and not c['profile']:
            policy=str(data/('connection-'+c['id']+'.gitconfig'))
            verification.append(block(c['name']+' · 프로필 없이 기존 저장소에서 사용','이 명령은 이 연결을 명시한 경우에만 적용합니다. 임의 폴더에 인증을 자동 주입하지 않습니다.',[shlex.join(['git','-c','include.path='+policy,'ls-remote','origin'])],optional=True))
    if verification:stage('verify','접속과 적용값 확인','인증 준비와 서버 접근 성공은 별개입니다. 실제 접속 확인은 여기의 명령을 터미널에서 직접 실행합니다.',verification)
    clone=[]
    for c in active:
        if c['kind']!='git':continue
        hostname,port=cfg.host_parts(c['host'])
        user='' if cfg.ssh_mode(c)=='system' else c['sshUser']+'@'
        url=('ssh://'+user+c['host']+'/OWNER/REPO.git' if port else user+hostname+':OWNER/REPO.git') if c['method']=='ssh' else 'https://'+c['host']+'/OWNER/REPO.git'
        command=shlex.join(['git','-c','include.path='+str(data/('profile-'+c['profile']+'.gitconfig' if c['profile'] else 'connection-'+c['id']+'.gitconfig')),'clone',url,str(Path(profiles[c['profile']]['path']).expanduser()/'REPO') if c['profile'] else '/PATH/TO/REPO'])
        clone.append(block(c['name']+' · 최초 clone 예시','선택한 연결의 설정 파일을 명시합니다. 프로필이 없으면 폴더 자동 적용이 없으므로 기존 저장소에서도 git -c include.path=… 명령을 사용하거나 해당 저장소의 로컬 include로 연결하세요. OWNER/REPO와 대상 폴더는 실제 값으로 바꾸세요.',[command],when='새 저장소가 필요할 때만',optional=True,example=True))
    if clone:stage('clone','필요할 때만 새 저장소 가져오기','현재 환경 설정만 확인한다면 이 단계는 건너뛰세요.',clone)
    if any(c['method']=='ssh' and cfg.ssh_mode(c)=='key' and c.get('agentSocket') for c in active):
        stage('managed-agent','대시보드에서 공급한 키 정리','작업을 마친 뒤 SSH 키 준비 화면의 정리 버튼을 사용합니다. 다른 agent의 키는 변경하지 않습니다.',[block('전용 agent 수명','대시보드를 다시 시작한 뒤 SSH 키 준비에서 키를 다시 공급하세요. 전용 소켓 경로는 유지됩니다.')],'secrets')
    if refs:
        commands=['bwe']+[shlex.join(['unset',credentials[ref]['variable']]) for ref in sorted(env_refs)]
        stage('cleanup','작업을 마치면 같은 터미널에서 정리','인증 준비 직후가 아니라 Git·API 작업을 모두 마친 뒤 실행하세요.',[block('이 셸의 관리 키·세션 정리','새로 추가한 키만 제거하고, 이 셸이 사용한 vault를 잠급니다. 기존 키·다른 터미널·외부 helper 저장소·서버의 토큰 만료/폐기는 별도 관리입니다.',commands)])
    return stages
