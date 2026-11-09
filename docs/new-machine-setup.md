# 빈 컴퓨터에서 시작하기

진입점은 dotfiles-public 대시보드다. 셸·도구·Git/SSH → 공통 서비스 인증 → 선택적인
컨테이너 개발·원격 PC 연결 순서로 진행한다. 설정 코드와 실제 계정 로그인은 별개다.

## 1. Git과 Python 준비

Git과 Python 3.10 이상을 설치하고 `git --version`, `python3 --version`으로 확인한다.
Windows에서는 WSL과 그 안의 Git·Python을 준비한다. 대시보드는 실행한 OS의 설정을 다룬다.

## 2. 공개 대시보드 받기

현재 통합 변경은 PR 검토 중인 `codex/environment-control` 브랜치에 있다.
이 브랜치를 사용하려면 다음처럼 받는다. main에 반영된 뒤에는 `--branch`를 생략한다.

```sh
mkdir -p "$HOME/personal"
git clone --branch codex/environment-control https://github.com/doh0106/dotfiles-public.git "$HOME/personal/dotfiles"
cd "$HOME/personal/dotfiles"
python3 bin/dashboard.py
```

Node·Docker·Bitwarden·Agent Kit 없이도 대시보드부터 열 수 있다.

## 3. 대시보드에서 내 환경 적용

**내 환경**이 기본 진입점이다. 기존 컴퓨터에서 내보낸 설정 JSON을 불러오거나 도구·설정을 고른 뒤
**선택한 설정 저장·적용**을 누른다. 없는 도구 설치 → 설정 적용의 실제 진행 결과가 표시된다.
관리자 승인이 필요하면 표시된 안내를 수행하고 다시 이어간다. 새 터미널에서 셸을 확인한다.

**Bitwarden 연결하기**에서 잠금을 해제하고 **등록된 SSH 키 모두 공급**을 누른다.
CLI 첫 로그인에는 Bitwarden 계정의 개인 API 키가 필요하다. 키 생성·파일 등록·항목 편집은 Bitwarden에서 한다.
agent 수명·공급·해제는 **원격 접속 → SSH agent**, 실제 접속 대상은 Git·원격 접속에서 관리한다.
설정 JSON에는 항목 참조만 들어 있고 인증 비밀 값은 복원되지 않는다.

전체 화면 사용법과 업데이트는 [대시보드 사용 순서](dashboard-control-center.md)를 참고한다.
아래 저장소 설치 명령은 수동 경로다. **내 환경 → 필요한 기능 추가**의 설치·연결 버튼으로도 진행할 수 있다.

## 4. 공통 서비스 인증 관리 연결

비공개 저장소를 읽을 Git 인증을 준비한 뒤 core를 받는다.
프로필 없는 연결을 선택했다면 적용 안내에 나온 `git -c include.path=… clone` 접두사를
아래 clone 명령에도 사용한다. 이 연결의 인증은 모든 폴더에 자동 적용되지 않는다.

```sh
git clone https://github.com/doh0106/environment-core.git "$HOME/personal/environment-core"
python3 "$HOME/personal/environment-core/cli.py" register
```

대시보드를 다시 열고 **외부 서비스**에서 Jira·Confluence·Google 설정 창을 연다.
필요한 서비스만 직접 로그인·토큰 등록·접근 검증한다. 기존 인증을 가져올 경우 안전한
이전 절차를 사용하며 채팅·공개 Git에 인증 값을 넣지 않는다.

## 5. 개발 컨테이너가 필요하면

Docker와 Dev Container CLI를 준비한다. 다음 저장소도 현재 통합 작업 브랜치를 사용한다.

```sh
git clone --branch codex/environment-control https://github.com/doh0106/dev-environment.git "$HOME/personal/dev-environment"
cd "$HOME/personal/dev-environment"
./scripts/install-host-workflow.sh
python3 "$HOME/personal/environment-core/cli.py" \
  --dev-environment-root "$HOME/personal/dev-environment" register --replace
```

프로젝트의 `.devcontainer/`를 기준으로 `dev-up .`, `dev-shell .`, `dev-stop .`을 사용한다.
대시보드의 **프로젝트 실행 환경**는 관측만 하며 컨테이너를 생성하지 않는다.

## 6. 집 WSL에 원격 접속하려면

기존 비공개 dotfiles를 읽을 인증을 준비하고 필요한 설정을 받는다.

```sh
git clone https://github.com/doh0106/dotfiles.git "$HOME/personal/dotfiles-private"
```

**원격 접속 → Tailscale·집 WSL**에서 위 저장소의 `HEAD` 또는 마지막 fetch의 `origin/main`을 선택해
접속 설정을 불러온다. 대상 저장 → Tailscale 설치 → 같은 신원 로그인 → SSH 별칭 적용 →
집 WSL 접속 확인 순서로 따른다. [상세 절차](tailscale-client-setup.md)를 참고한다.
이 용도로 private dotfiles의 옛 bootstrap 전체를 실행할 필요는 없다.

## 7. AI 도구와 Agent Kit

사용할 AI 도구를 설치하고 해당 계정에 로그인한 뒤 필요한 Agent Kit 스킬 묶음을 설치한다.
Agent Kit을 먼저 설치하지 않아도 호스트 설정과 공통 서비스 인증을 준비할 수 있다.
통합 Agent Kit 변경은 작업 브랜치/PR이며 기존 marketplace main의 설치본은 자동 갱신되지 않는다.
기존 Drive 전용 어댑터가 필요한 경우 접근 가능한 Agent Kit checkout을 별도로 준비해 core에
`--agent-kit-root`로 등록한다. Jira·Confluence·공통 Google 연결은 그 checkout 없이 동작한다.

마지막으로 macOS에서는 `apps/macos/Install Dotfiles.command`를 실행해 앱 아이콘을 만들 수 있다.
이후에는 대시보드에서 설정 선택·진행 기록·서비스 인증·개발 환경 상태·원격 접속 안내를 확인한다.
