# dotfiles-public

공개 설정 코드를 가져와 로컬 대시보드에서 필요한 기능을 고른다.
대시보드는 설정 파일과 실행 안내를 만들고, 사람 또는 AI가 안내를 실행한다.
설치·로그인·키 로드는 사용자가 선택한 때에만 진행한다.

## 시작하기

빈 컴퓨터에서 전체 환경을 준비할 때는 [새 컴퓨터 설정 순서](docs/new-machine-setup.md)를 따른다.
호스트 설정, 서비스 인증, 컨테이너 개발, Tailscale 원격 접속을 단계별로 연결한다.


Git과 Python 3를 준비한 뒤 저장소를 clone한다. Git이 없다면 ZIP으로 받아 풀어도 된다.
공개 저장소는 `doh0106/dotfiles-public`이다. 기존 비공개 `dotfiles` 저장소와 이력을 분리한다.

```sh
mkdir -p "$HOME/personal"
git clone https://github.com/doh0106/dotfiles-public.git "$HOME/personal/dotfiles"
cd "$HOME/personal/dotfiles"
python3 bin/dashboard.py
```

출력된 `http://127.0.0.1:포트/`로 접속한다. WSL에서는 Windows 브라우저로 같은 주소를 연다.
Node.js·Bitwarden·zsh가 없어도 대시보드부터 열 수 있다. 화면은 이 서버를 실행한 OS의 설정을 다룬다.
`file://` HTML만 열면 설정 API를 사용할 수 없다. 고정 포트는 `--port 37691`, 종료는 Ctrl-C다.
서버는 127.0.0.1에만 바인딩하며 같은 출처의 저장 요청만 허용한다.

## 앱 아이콘으로 열기

매번 Python 명령을 입력하는 대신 앱 실행기를 사용할 수 있다. Python 3.9 이상은 기기에
한 번 설치되어 있어야 한다. 실행기가 서버를 시작하고, Chrome·Edge가 있으면 별도 앱 창으로,
없으면 기본 브라우저로 대시보드를 연다. Python을 포함한 독립 실행 바이너리는 아니다.

| 환경 | 처음 한 번 | 이후 실행 | 관리 대상 |
|---|---|---|---|
| macOS | `apps/macos/Install Dotfiles.command` 더블클릭 | `~/Applications/Dotfiles.app` 더블클릭 또는 Dock에 추가 | 해당 Mac의 홈 설정 |
| Windows | WSL·Python 준비 후 `apps/windows/Install Dotfiles.cmd` 더블클릭 | 시작 메뉴·바탕 화면의 **Dotfiles** | 선택한 WSL 배포판의 홈 설정 |

Mac 실행기는 Apple Silicon·Intel의 일반적인 Python 설치 경로를 찾는다. 배포용 서명·공증은
하지 않았으며 Mac 실기기 실행은 별도 확인이 필요하다. Windows는 네이티브 PowerShell/Git 설정을
관리하는 앱이 아니라 WSL용 실행기다. WSL 서버는 127.0.0.1에서만 실행된다.

Windows에서 기본 WSL이 아닌 배포판이나 별도 저장소 경로를 사용할 때는 최초 설치 시 지정한다.
아래 명령의 배포판·사용자·폴더는 실제 값으로 바꾼다. 이후에는 생성된 아이콘만 누르면 된다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\apps\windows\Dotfiles.ps1 -Install -Distro Ubuntu-24.04 -Repository /home/USER/personal/dotfiles
```

실행기는 저장소 위치를 기억하므로 폴더를 옮겼다면 설치 실행기를 다시 실행한다.
앱 실행 자체는 프로그램 설치·configure·Bitwarden 로그인을 수행하지 않는다.
계속 켜져 있는 터미널의 인증 세션을 앱에 전달하지 않으며, 인증은 기존 적용 안내를 따른다.

화면 아래 **앱 서버 종료**는 로컬 서버를 종료한다. 저장하지 않은 초안이 있으면 확인한다.
아이콘을 여러 번 눌러도 같은 저장소의 앱 서버를 재사용한다. 창을 모두 닫거나 창에서 5분간
연결 신호를 받지 못하면 서버가 자동 종료된다. 잠자기 등으로 종료되었으면 아이콘으로 다시 연다.
다른 창에도 같은 서버가 열려 있다면 서버 종료가 함께 영향을 준다.

일반 `python3 bin/dashboard.py` 실행은 기존 동작을 유지하고 앱 종료 버튼을 표시하지 않는다.
앱의 상태·최근 실행 로그는 `~/.local/state/dotfiles-app/` 아래에 저장한다.
문제가 생겼을 때 화면 없이 실행·종료를 확인할 수 있다.

```sh
python3 bin/desktop.py launch --no-open
python3 bin/desktop.py stop
```

## 저장소 위치와 업데이트

사용할 checkout은 `~/personal/dotfiles` 하나로 유지한다. 셸·Git 설정은 이 checkout의 파일에
연결하고, 대시보드에서 저장한 개인 선택은 `~/.config/dotfiles/dashboard/`에 별도로 보관한다.
코드 변경은 이 checkout에서 커밋한 뒤 원격과 동기화한다. 다른 로컬 사본을 origin으로 연결하지 않는다.

```sh
cd "$HOME/personal/dotfiles"
git remote -v
git status
# 미커밋 변경을 정리한 뒤 원격 변경을 가져온다.
git pull --ff-only origin main
```

WSL을 외부에서 접속하는 선택 기능은 [WSL SSH 안내](docs/wsl-ssh.md)를 참고한다.

## 설정을 나누는 기준

| 영역 | 정하는 것 | 다른 영역과의 관계 |
|---|---|---|
| 셸과 테마 | 설치된 Oh My Zsh, 테마, 프레임워크 경로 | 서비스 로그인 없이 사용 가능 |
| 도구 선택 | 이동·검색·빌드·런타임·AI·서비스 도구를 개별 선택 | 설치 여부와 활성화는 별개 |
| 작업 프로필 | 폴더 범위, 커밋 이름·이메일 | `gitdir`로 선택. 접속 계정을 의미하지 않음 |
| 저장소 · 서버 연결 | Git 호스트·SSH 서버, 접속 방식, 인증 참조, gh/glab 사용 | 프로필 없이 직접 선택 가능. 필요하면 폴더별 자동 적용 |
| Git · SSH 인증 참조 | 공급자, 항목 이름·형식, 공개키 경로 등 | 개인키·토큰 값은 화면에 입력하지 않음 |
| API 도구 | GitHub의 gh, GitLab의 glab, 별도 API 토큰 | Git SSH/HTTPS와 독립적으로 켜거나 끔 |
| SSH 키 · 인증 세션 | 새 SSH 키 TTL, 사용 후 정리 | 토큰의 서버 만료·폐기와는 별개 |

예를 들어 `personal` 폴더 프로필에 GitHub SSH와 GitLab HTTPS를 함께 연결할 수 있다.
회사 프로필이나 비공개 overlay는 필요할 때만 추가한다. 처음부터 회사 설정을 요구하지 않는다.
일반 Git 호스트는 SSH/HTTPS로 사용할 수 있지만 별도 API 도구 어댑터는 제공하지 않는다.
GitHub Enterprise와 GitLab Self-Managed도 호스트를 지정한다. SSH 접속 호스트와 API 서비스 호스트가
다르면 API 탭에서 서비스 호스트를 따로 지정한다. API는 HTTPS와 도메인 루트 구성을 지원한다.

## 대시보드 메뉴

환경 개요는 각 영역의 상태와 지금 할 일을 모아 보여준다. **새 컴퓨터 설정 시작 / 이어서 설정**은
환경 개요 안의 안내 흐름이며, 설정 자체는 아래 담당 화면에서 관리한다.

| 메뉴 | 세부 설정과 역할 |
|---|---|
| 환경 개요 | 준비 상태, 지금 할 일, 새 컴퓨터 설정 순서, 설정 적용 안내 |
| 앱·도구 | 프로그램 선택·설치 안내, 터미널·셸·테마, AI 도구·Agent Kit 스킬 안내 |
| Git 설정 | Git 호스트 연결, 폴더별 작성자, 공통 인증 참조·키 세션 |
| 원격 접속 | SSH 접속 대상, Tailscale·집 WSL 준비, 공통 인증 참조·키 세션 |
| 프로젝트 실행 환경 | 선택한 프로젝트의 Dev Container 구성·상태 조회, 실행·접속·중지 명령 안내 |
| 외부 서비스 | Jira·Confluence·Google의 계정 연결·인증·사용 설정 창 |

Git과 SSH 서버는 각 메뉴에서 별도 목록으로 표시한다. 연결 종류는 해당 메뉴에서 정해지며,
기존 연결·프로필·인증 참조와 설정 파일 형식은 유지한다. 두 영역의 인증 참조와 키 세션은
같은 공통 설정을 보여준다. 실제 비밀값을 메뉴별로 복제하지 않는다.

외부 서비스와 프로젝트 실행 환경의 관측은 선택 설치한 environment-core를 사용한다.
AI 스킬 설치 상태는 자동 관측하지 않으며 Agent Kit의 도구별 설치 안내로 연결한다.
프로젝트 실행·접속·중지는 안내한 dev-* 명령으로 진행하며 대시보드가 자동 실행하지 않는다.

## 화면에서 작업하기

처음 기기를 설정할 때는 **환경 개요 → 새 컴퓨터 설정**의 순서를 따른다. 각 설정 화면에서
선택을 확인하고 다음 단계로 이동한다. 저장과 실제 적용은 따로 표시한다.
[처음 설정 안내](docs/first-run-setup.md)에 진행 기록과 선택 기능을 설명했다.


1. **앱·도구 → 터미널·셸·테마**에서 원하는 프레임워크·테마를 고른다. 글꼴·글자 크기 조절은 화면 미리보기 전용이다.
2. **Git 설정 → 폴더별 작성자**에서 서로 겹치지 않는 프로젝트 폴더와 Git 이름·이메일을 정한다.
3. **Git 설정 → Git 호스트 연결**에서 Git 접속과 인증 참조를 정한다. 서버 SSH는 **원격 접속 → SSH 접속 대상**에서 별도로 추가한다.
   처음에는 빈 목록이며 연결을 추가한 뒤 선택하면 상세로 이동한다. 작업 프로필은 선택 사항이다.
   Git 저장소는 SSH/HTTPS를 고르고, SSH 서버는 키 인증용 사용자·별칭을 설정한다.
   GitHub·GitLab 제품 선택은 해당 API 추가 기능을 켤 때만 필요하다. 필수 항목과 저장된 값의 출처를 각 입력 옆에 표시한다.
4. 필요하다면 **API** 탭에서 gh/glab와 토큰 참조를 켠다. Git만 사용할 때는 꺼둔다.
5. **변경 검토 → 저장 · 설정 파일 생성**으로 로컬 파일을 생성한다.
6. **적용 안내**에서 미설치 도구 안내와 configure·새 셸·인증 명령을 실행한다.
   안내를 복사해 AI에게 전달할 수도 있다.

적용 안내는 현재 선택에 따라 확인 → 인증 재료 → 저장 → 미설치 도구 → configure → 새 zsh →
Bitwarden 상태별 로그인/잠금 해제 → 연결별 인증 준비 → 접속 확인 → 작업 후 정리 순서로 만든다.
Bitwarden을 사용하지 않으면 로그인 단계가 없고, HTTPS에는 SSH 키 로드 명령이 나오지 않는다.
로그인 복구와 최초 clone 예시는 필요할 때만 펼쳐본다. 화면과 AI에게 복사하는 안내는 같은 순서를 사용한다.

처음 받은 환경에서는 기능이 꺼져 있다. 설치된 프로그램도 자동 활성화하지 않는다.
저장 전 초안은 브라우저 메모리에만 있고, 저장한 설정은 아래 위치에 남는다.
여러 창이 같은 설정을 바꾸면 오래된 창의 저장을 거부한다.

```text
~/.config/dotfiles/dashboard/
  settings.json                 # schema 3: 기능·프로필·연결·인증 참조·세션 정책
  enabled.zsh                   # 선택한 셸 integration
  git.config                    # gitdir별 include
  profile-<ID>.gitconfig         # identity와 호스트별 SSH/HTTPS 정책
  ssh-<ID>.config               # 해당 프로필의 Git SSH 호스트·공개키 선택
  ssh.config                    # 일반 SSH 서버 별칭
  profiles.json                 # 명령 실행 시 사용할 연결/인증 참조
  ghostty.conf / iterm.conf     # 선택한 프로젝트 색상
```

설정 파일은 600 권한, 설정 디렉터리는 700 권한으로 만든다. 개인키·토큰 값을 기록하지 않는다.
기존 평면 설정은 읽을 때 새 구조로 옮겨 보여주고, 첫 저장 때 원본 JSON을 백업한다.
원래 켜져 있던 개인 설정을 보존하며, 꺼져 있던 회사 프로필을 추가 활성화하지 않는다.

## 설정 연결과 이후 변경

```sh
python3 bin/dashboard.py configure
exec zsh
```

configure는 도구 설치·네트워크 인증을 실행하지 않는다. 기존 셸·SSH 파일은 백업하고 관리 블록을
추가한다. 글로벌 Git 설정의 기존 identity/helper 뒤에 관리 include를 배치해 폴더 정책을 적용한다.
저장소 로컬 설정·명령별 `-c`는 여전히 우선하므로 실제 값은 `git config --show-origin`으로 확인한다.
WSL의 `/mnt/c` 권한 때문에 OpenSSH가 설정을 거부하지 않도록 공통 SSH Include는 홈에 600 권한으로 복사한다.

변경할 때는 대시보드 저장 → 적용 안내의 configure → 새 셸 순서로 진행한다.
이미 설치된 도구의 재설치 단계는 만들지 않는다. Yazi·Zellij 선택을 끄면 관리 링크를 제거하고,
보관했던 사용자 파일이 있으면 복원한다. 이미 실행 중인 프로그램·로드된 키는 바꾸지 않는다.
기존 저장소의 remote URL도 자동 변경하지 않는다. SSH↔HTTPS 변경 후에는 다음처럼 직접 바꾼다.

```sh
git remote set-url origin https://YOUR-HOST/OWNER/REPO.git
python3 bin/dashboard.py plan  # 화면 없이 저장된 설정의 적용 안내 출력
```

## 도구 선택 설치와 zi

앱·도구의 프로그램 설치 화면에서 필요한 항목만 켠 뒤 저장하고 적용 안내를 따른다.
저장·configure는 설치 프로그램을 실행하지 않는다. 안내의 명령을 사람이 또는 AI가 실행한다.
이미 설치된 도구는 재설치하지 않으며, 기능을 꺼도 프로그램을 삭제하지 않는다.

| 용도 | 개별 선택 항목 | 의존성과 동작 |
|---|---|---|
| 이동·목록 선택 | zoxide, fzf | zoxide를 선택하면 zi에 필요한 fzf도 설치 안내에 포함 |
| 검색·파일 보기 | ripgrep, fd, bat | Ubuntu에서는 fd와 bat의 명령 이름이 fdfind·batcat일 수 있음 |
| 개발 기본 | C/C++ 빌드 도구, unzip, Git LFS | LFS 전역 필터를 설정하지 않음. 필요한 저장소에서만 git lfs install --local |
| 언어 환경 | nvm·Node.js, uv | nvm 경로와 Node 버전 선택. nvm만 있고 해당 Node가 없으면 별도 설치. pip 별칭은 바꾸지 않음 |
| AI 도구 | Claude Code, Gemini CLI | Claude는 native 설치. Gemini는 Node 20+·npm 필요. 로그인은 별도 |
| 서비스 도구 | AWS CLI, ngrok | CLI만 설치. 계정 인증·토큰 등록·터널 시작은 별도 |

Oh My Zsh는 셸과 테마 화면에서 선택한다. 없으면 선택한 경로에 설치하는 안내가 나온다.
GitHub·GitLab CLI는 Git 호스트 연결의 추가 기능 선택을 따른다. Git만 쓰면 설치할 필요가 없다.
외부 패키지 저장소가 필요한 CLI는 공식 설치 문서 링크를 제공한다.

nvm을 선택하면 설치 안내가 nvm → 선택한 Node 버전 → Gemini 순서로 나온다.
새 셸은 선택한 Node 버전을 사용한다. Gemini만 선택하고 시스템 Node 20+·npm이 없다면
먼저 nvm을 선택하라는 안내가 나온다. 다른 도구가 Node를 자동으로 선택하거나 설치하지 않는다.
npm 전역 패키지는 Node 버전별로 달라서, 버전을 바꿨으면 Gemini 설치 상태를 다시 확인한다.

설치 명령은 `bash bin/install-tool.sh TOOL [NVM_DIR [NODE_VERSION]]` 형태이며 한 도구만 다룬다.
패키지 관리자가 필요한 설치는 sudo를 요청할 수 있다. Linux의 uv·Claude·AWS·ngrok은
사용자 경로를 사용한다. 기존 설치의 업그레이드와 서비스 로그인은 별도 작업이다.

zi를 사용하려면 zoxide를 켜고 fzf 설치 안내를 따른 뒤 configure하고 새 zsh를 연다.
초기화 코드를 .zshrc에 다시 추가할 필요는 없다.

```sh
python3 bin/dashboard.py configure
exec zsh
# 자주 쓰는 폴더를 cd로 몇 번 방문한 뒤
zi                 # 방문 기록을 골라 이동
zi dotfiles        # 이름으로 좁힌 뒤 선택
z dotfiles         # 가장 잘 맞는 기록으로 바로 이동
```

방문 기록은 각 기기에 저장되며 새 기기에 자동 동기화하지 않는다.
기존 설정을 읽으면 새 도구는 꺼진 상태로 추가하고, 기존 선택·인증 참조는 보존한다.
첫 저장 시 이전 설정 파일을 백업한다.

## 인증 공급 방식

| 용도 | 지원 공급자 | 실제 사용 |
|---|---|---|
| Git SSH / 서버 SSH | Bitwarden, 기존 SSH agent | `.pub`로 선택한 키를 agent에서 사용 |
| Git HTTPS | Bitwarden, 외부 Git credential helper, 인증 없음 | 호스트별 helper. 공개 읽기는 인증 없이 가능 |
| gh / glab API | Bitwarden, 지정 환경변수 | 해당 호스트의 명령 자식 프로세스에 토큰 주입 |

Bitwarden에는 SSH Key 또는 Secure Note의 개인키, Secure Note 또는 Login password의 토큰을 둔다.
`.pub` 파일은 연결에 지정한 경로에 미리 준비해야 한다. 공개키를 Bitwarden에서 자동 추출하지 않는다.
Git 설정과 키 로더가 같은 연결의 공개키 경로를 사용한다.

```sh
bwl                                      # Bitwarden 최초 로그인/만료 시
bws --connection personal-github          # 예시 ID: 선택한 연결의 인증 준비
# 이후 해당 폴더에서 git fetch / git push
bwgh --connection personal-github pr list # API를 켰을 때만
bwglab --connection personal-gitlab mr list
bwe                                      # 이 셸이 추가한 키·세션 정리
```

연결 ID는 연결을 추가할 때 자동 생성하며 상세 화면에서 확인한다. 한 프로필에 연결이 하나뿐이면 `bws personal`도 된다.
프로필을 연결했다면 저장소 안에서 gitdir 프로필과 origin의 호스트·방식으로 선택한다.
프로필이 없으면 `--connection ID`로 직접 선택한다. 생성된 `connection-ID.gitconfig`는
전체 폴더에 자동 연결하지 않으며 적용 안내의 `git -c include.path=…` 명령으로 사용한다. 모호하면 `--connection ID`를 요구한다.
최초 clone에는 대상 gitdir가 아직 없으므로 적용 안내의 `git -c include.path=… clone …`을 사용한다.
SSH가 아닌 HTTPS 연결의 bws는 agent를 시작하지 않는다.

API를 켜면 새 zsh의 gh/glab 함수도 같은 선택을 사용한다. 다른 터미널에 토큰을 공유하지 않으며,
토큰 조회가 실패하면 ambient token으로 우회하지 않는다. 호스트 변경 옵션과 다른 저장소 호스트는
검사하며, 다른 호스트에서 실행할 작업은 저장소 밖에서 해당 연결을 명시한다.
`command gh`, `command glab`는 wrapper를 우회한다. wrapper는 auth login·토큰 출력 등 저장/노출 명령을 막는다.

새 SSH 키에는 기본 3600초 TTL을 적용한다. 기존 키의 수명은 바꾸지 않으며 bwe도 기존 키는 보존한다.
bwe는 이 셸이 사용한 vault를 잠그고 알려진 세션 변수를 해제한다. 선택한 외부 helper의 저장소,
다른 터미널, 서버 토큰의 폐기, 사용자가 정의한 토큰 환경변수의 해제는 별도 관리한다.
Bitwarden 경로의 HTTPS helper는 store/erase 요청을 무시한다. 다른 credential helper를 별도로 추가하면
그 도구의 보관 정책이 적용될 수 있으므로 설정 출처를 확인한다.

[인증 선택과 진단](docs/authentication.md), [Bitwarden 운영·복구](docs/bitwarden.md)에서 자세히 다룬다.
암호화 vault 캐시·일반 설정·공개키는 디스크에 남는다. 로컬 무흔적 구성은 아니다.
대시보드의 agent 표시는 서버 프로세스 기준이고, vault는 로그인과 충돌하지 않도록 자동 조회하지 않는다.

## 기기 간 설정과 비공개 overlay

설정은 기기 로컬에 저장한다. 다른 기기에는 `settings.json`을 안전하게 복사한 뒤 폴더·공개키 경로를
그 기기에 맞춰 검토하고 configure한다. 계정 이메일·호스트·항목 이름 같은 정보가 포함되므로
기기 설정을 공개 저장소에 자동 커밋하지 않는다. 실제 키·토큰과 설치된 프로그램은 별도로 준비한다.

회사 설정 등은 공통 코드를 복사하지 않고 별도 비공개 저장소를 선택적으로 연결한다.
비공개 설정을 먼저 clone한 뒤 `./bin/attach-private.sh /PATH/TO/dotfiles-private`로 연결한다.
Git·SSH Include와 shell.zsh를 읽으며, 연결 해제는 `~/.config/dotfiles/private` 링크를 제거하고 새 셸을 연다.
대시보드는 이 overlay의 내용을 수정하거나 자동 연결하지 않는다. 추가 서버 키만 필요하다면
`bws --extras`로 비공개 secrets.json의 ssh-add 항목을 명시적으로 로드한다.
기기별 최종 셸 설정은 `~/.config/dotfiles/local.zsh`에 둔다.

## 검증

```sh
python3 tests/smoke.py
python3 tests/dashboard.py
python3 tests/runbook.py
python3 tests/tools.py
python3 tests/desktop.py
python3 tests/auth.py
./bin/verify.sh
# 인증 준비를 한 셸에서만 선택적으로 실행
./bin/verify.sh --session personal
```

자동 테스트는 임시 홈, 합성 SSH 키, 실제 SSH agent, 모의 Bitwarden·gh·glab를 사용한다.
실제 vault 로그인·원격 서버 권한·macOS GUI는 자동 테스트가 확인하지 않는다.
Git의 [조건부 include](https://git-scm.com/docs/git-config#_conditional_includes)와
[credential helper](https://git-scm.com/docs/gitcredentials),
[gh 환경변수](https://cli.github.com/manual/gh_help_environment),
[glab 환경변수](https://docs.gitlab.com/cli/configuration/#environment-variables)가 연동의 근거다.

## 서비스 인증과 개발 환경 상태

선택 설치한 environment-core와 연결하면 대시보드의 **외부 서비스**에서 Jira·Confluence·Google 계정의 설정·로그인·갱신을,
**프로젝트 실행 환경**에서 선택한 프로젝트의 Dev Container 구성·실행 상태를 확인한다.
기존 Git·SSH·Bitwarden 설정은 유지한다. [연결·이전 안내](docs/environment-control.md)를 따른다.

## UI 설계 미리보기

카탈로그에서 사용한 패턴을 확인하고, 주 메뉴·보조 설명 표시의 구현된
대안을 비교하고 목록→상세 구조의 적용 패턴을 확인할 수 있다. [UI 설계 살펴보기](docs/ui-design-inspector.md)의 미리보기 명령으로
연다. 예시 설정을 사용하며 실제 설정 저장·인증 실행은 차단된다.

Tailscale을 사용하는 원격 개발 PC는 **원격 접속 → Tailscale·집 WSL**의
[새 클라이언트 설정](docs/tailscale-client-setup.md)을 따른다. 기존 SSH configure에도
전용 별칭 Include가 연결되며 실제 계정 로그인과 원격 접속은 직접 확인한다.
