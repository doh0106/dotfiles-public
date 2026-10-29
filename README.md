# dotfiles

공개 저장소를 가져와 로컬 대시보드에서 사용할 기능을 선택한다.
대시보드는 설정 파일과 설치·적용 안내를 만들고, 사람 또는 AI가 안내대로 실행한다.
도구 설치와 인증은 대시보드가 대신 실행하지 않는다.

## 1. 가져오기

Git이 있다면 공개 HTTPS 주소로 clone한다. Git이 없다면 GitHub에서 ZIP을 내려받아 풀어도 된다.
아래 최종 URL은 새 공개 저장소를 배치한 뒤 사용할 주소다.
기존 동명의 비공개 저장소는 먼저 이름을 바꾸거나 다른 공개 URL을 사용한다.

```sh
git clone https://github.com/doh0106/dotfiles.git "$HOME/dotfiles"
cd "$HOME/dotfiles"
```

## 2. 대시보드 실행

Python 3만 있으면 시작할 수 있다. Python이 없으면 OS 패키지 관리자로 먼저 설치한다.
Node.js, zsh, Bitwarden, 선택 기능의 설치는 화면을 열기 위한 사전 조건이 아니다.

```sh
python3 bin/dashboard.py
```

브라우저가 열리지 않으면 출력된 `http://127.0.0.1:포트/` 주소를 직접 연다.
WSL에서는 Windows 브라우저로 해당 localhost 주소를 연다. 이 환경에서 localhost 전달이
꺼져 있다면 WSL의 localhost 연결 설정을 확인한다. `file://`로 HTML만 열면 API가 동작하지 않는다.
포트를 고정하려면 `python3 bin/dashboard.py --port 37691`처럼 실행한다.
종료는 터미널에서 Ctrl-C. 로그인 시작이나 시스템 서비스 등록은 하지 않는다.

## 3. 선택하고 설정 파일 생성

처음 화면은 다음 순서로 시작한다. 각 단계는 필요한 경우에만 선택한다.

| 순서 | 설정 | 다음 단계 전에 할 일 |
|---|---|---|
| 1. 셸·테마 | 설치된 Oh My Zsh와 테마 | 이 단계만 저장·configure 후 새 zsh에서 바로 확인 가능 |
| 2. Git 계정 | 개인·회사 폴더, 커밋 identity, 공개키 | 개인 계정만 쓰면 회사 프로필은 off |
| 3. 인증·키 | Bitwarden 키와 선택적 gh 토큰 | Git 프로필 필요. gh는 Bitwarden도 필요. 로그인은 configure 이후 |
| 4. 선택 도구 | zoxide·Zellij·Yazi·nvm·프로젝트 색상 | 필요한 기능만 켜고 설치 안내 확인 |

테마를 쓰기 위해 GitHub 로그인을 먼저 할 필요는 없다. 단계 이동은 설정을 자동으로 켜거나
저장하지 않는다. 변경사항은 저장 전 검토하고, 화면의 설치·configure 안내를 사람 또는 AI가 실행한다.


처음에는 선택 기능이 모두 꺼져 있다. 도구가 설치돼 있어도 자동 활성화하지 않는다.

- Oh My Zsh: 설치 경로와 테마 (`robbyrussell` 또는 `agnoster`), git 플러그인
- Git 폴더 프로필: 개인·회사 폴더, 커밋 이름·이메일, 선택할 공개키 경로
- 추가 SSH 연결: 호스트 별칭·주소·사용자·공개키 경로
- Bitwarden: 개인·회사 SSH 키 항목 이름·형식, 키 TTL (기본 1시간)
- GitHub CLI: 개인·회사 토큰의 Bitwarden 항목, 명령별 인증
- zoxide: z 명령 활성화
- Zellij: zj 명령과 기본 세션 이름 (빈 값이면 현재 폴더 이름)
- 프로젝트 색상: 프로젝트 glob, Ghostty 색상·iTerm2 탭 색상
- Yazi: y 명령과 기존 기본 탐색기 설정
- nvm: 설치 경로

설정은 저장 전 변경 내용을 미리 볼 수 있다. **설정 파일 생성**은
`~/.config/dotfiles/dashboard/`에 기기별 JSON·Git·SSH·zsh·색상·secret 참조 파일을 만든다.
개인키·토큰·비밀번호 값을 받는 입력란은 없다. 생성 파일은 600 권한이며 공개 저장소에 넣지 않는다.
서버가 실행 중인 WSL/macOS/Linux의 명령 경로로 설치 여부를 판단한다.

설치 여부와 활성화 여부는 별개다. 활성화 후에도 도구가 없으면 설치 안내를 따라야 한다.
화면의 설치 상태 다시 확인 버튼으로 수동 설치 후 상태를 갱신할 수 있다.

## 4. 사람 또는 AI가 안내 실행

저장 후 화면 아래에 활성화한 기능의 안내가 나온다.

- 이미 설치됐다면 설치 단계를 생략한다.
- 알려진 패키지 관리자를 사용할 때는 존재 여부를 검사하는 설치 snippet을 제공한다.
- 배포판마다 설치 방식이 다른 도구는 공식 설치 문서 링크를 제공한다.
- configure 명령으로 홈 설정과 선택 기능을 연결한다.
- 새 zsh를 연 뒤 인증·키 로드 등 후속 단계를 실행한다.
- AI에게 전달할 안내 복사 버튼으로 작업 순서를 전달할 수 있다.

```sh
python3 bin/dashboard.py configure
```

이 명령도 도구 설치·vault unlock·원격 접속은 하지 않는다. Git과 Bash가 필요하며,
실제 셸 기능을 사용하려면 zsh를 설치해야 한다. 기존 zsh·SSH 설정은 백업하고 관리 블록을 추가한다.
새 zsh에서 선택한 기능을 읽는다. 기존 셸의 함수·alias는 새 셸을 열기 전까지 남는다.

## 5. 이후에는 설정만 변경

대시보드에서 변경 후 설정 파일을 다시 생성하고 안내의 configure를 실행한다.
도구가 이미 있으면 재설치 안내를 만들지 않는다. 선택 해제한 zsh integration은 새 셸에서 읽지 않는다.
Yazi·Zellij의 관리 링크는 configure 시 선택 상태에 따라 추가·제거한다.
과거 사용자 파일을 백업했다면 기능 해제 시 그 백업을 복원한다. 도구 자체는 삭제하지 않는다.
이미 실행 중인 프로그램이나 이미 agent에 로드된 키는 종료·제거하지 않는다.

화면 없이도 동일한 저장 설정과 안내를 읽을 수 있다.

```sh
python3 bin/dashboard.py plan
```

AI가 설정을 변경할 때도 같은 `dashboard/settings.json` 형식을 사용하고 configure를 실행하면 된다.
JSON의 키·필드 형식은 대시보드 API와 configure가 검증한다.

## 비공개 회사 설정

공통 코드를 복사하지 않고 별도 `dotfiles-private` 디렉터리를 선택적으로 연결한다.
Bitwarden 기능을 활성화하고 개인 키를 로드한 다음 비공개 설정을 가져온다.

```sh
bwl  # 최초 로그인 또는 로그인 만료 시
bws personal
git -c include.path="$HOME/.config/dotfiles/dashboard/personal.gitconfig" \
  clone git@github.com:doh0106/dotfiles-private.git "$HOME/personal/dotfiles-private"
./bin/attach-private.sh "$HOME/personal/dotfiles-private"
exec zsh
bws personal
```

Git·SSH Include로 추가 비공개 설정을 읽는다. 계정 선택은 대시보드의 gitdir 프로필이 담당한다.
bws는 선택한 프로필의 키만 읽는다. 추가 서버 키는 `bws --extras`로 명시적으로 읽는다.
비공개 shell.zsh는 공통 integration 전에 읽는다. 대시보드에서 활성화한 색상·nvm 등의
로컬 옵션이 비공개 셸의 같은 변수를 덮어쓸 수 있다. 가장 마지막 기기별 설정은
`~/.config/dotfiles/local.zsh`에 둔다.
비공개 overlay의 기존 Git·SSH·셸 설정은 대시보드에서 편집하거나 끄지 않는다.
연결 해제는 `~/.config/dotfiles/private` 심볼릭 링크를 제거한 뒤 새 셸을 여는 방식이다.

## 유지한 기본 동작과 범위

- 공개 HTTPS는 SSH로 강제 변환하지 않는다. 인증 없이 공개 저장소 업데이트가 가능하다.
- `github-personal` SSH 별칭은 비공개 설정을 가져올 수 있도록 기본 제공한다.
- Git의 st/co alias는 기본 제공한다. Git 폴더 프로필을 켠 경우에만 폴더별 identity·SSH 키와
  미분류 identity 차단을 적용한다. 끄면 기존 사용자 identity를 유지한다.
- macOS 앱·open 기반 opener는 macOS 전용이다. Linux·WSL은 Yazi 기본 opener를 사용한다.
- 선택 도구의 설치·OS 런타임·프로젝트 의존성 전체를 자동 관리하지 않는다.
- Obsidian 문서는 안내이며 자동 설치하지 않는다.
- 고급 secret 주입은 [Bitwarden 문서](docs/bitwarden.md)를 참고한다.

## 검증

```sh
python3 tests/smoke.py
python3 tests/dashboard.py
python3 tests/auth.py       # 임시 키·agent와 모의 Bitwarden/gh 사용
./bin/verify.sh
./bin/verify.sh --session personal  # Bitwarden과 선택 프로필 키 확인
```

앞의 두 테스트는 임시 홈에서 실행한다. 실제 Bitwarden·원격 SSH·macOS GUI는 별도 확인이 필요하다.

## Git·gh 인증과 세션 수명

1. Git 프로필에서 개인 폴더와 이름·이메일·공개키를 설정한다. 회사도 쓰면 회사 프로필을 켜고
   겹치지 않는 회사 폴더와 회사 identity·공개키를 입력한다. linked worktree는 원본 Git 폴더를 따른다.
2. Bitwarden에서 키 항목과 TTL을 입력하고, GitHub CLI를 켜면 토큰 항목도 입력한다.
3. 저장 → configure → 새 zsh → bwl(최초 또는 로그인 만료 시) → bws personal 순서로 진행한다.
4. 해당 폴더의 저장소에서 bws·git·gh를 사용한다. 다른 프로필로 이동하면 다음 gh 호출부터
   그 프로필 토큰을 선택한다. -R 옵션만으로는 프로필이 바뀌지 않는다.
5. 작업 후 bwe로 이 셸이 추가한 키·세션을 정리한다. 기존 agent·기존 키는 보존한다.

bws로 새로 추가한 키는 TTL 뒤 자동 제거된다. 터미널 종료만으로 agent 종료를 보장하지 않는다.
GitHub 토큰은 셸 전체에 export하지 않고 gh 자식 프로세스에만 전달한다. 이 인증을 쓰면
Git Credential Manager나 gh auth login/setup-git을 구성할 필요가 없다.
초기 private clone과 저장소 밖의 gh 작업에는 프로필을 명시한다.
상세 명령은 [인증 흐름](docs/authentication.md), [Bitwarden 운영](docs/bitwarden.md)을 참고한다.

기존 owner 기반 저장 설정은 화면에서 새 기본 폴더와 함께 불러온다. 폴더·공개키를 확인하고
다시 저장·configure한다. 기존 개인·회사 폴더를 자동 이동하지 않는다. 과거 원본 dotfiles의
전역 include나 private git/config에 있던 owner 기반 insteadOf·identity 규칙은 직접 제거해야
중복 적용을 피할 수 있다. 이번 dotfiles-private 사본에서는 해당 규칙을 제거했다.

대시보드의 vault·agent 상태는 **서버 프로세스 기준**이며 다른 터미널 상태와 다를 수 있다.
현재 셸에서의 확인은 ssh-add -l, git config --get dotfiles.profile, verify.sh --session을 사용한다.
암호화된 Bitwarden 캐시·일반 설정·공개키는 디스크에 남으며, 이는 로컬 무흔적 구성이 아니다.

## Bitwarden 오류와 기존 테마 복구

`invalid_grant`는 CLI 로그인/갱신 상태 문제일 수 있다. `bwu`는 CLI 상태 읽기 실패를
인식하면 키 로드나 gh 실행으로 진행하지 않고 복구 안내를 낸다.

```sh
unset BW_SESSION
bwl              # raw 세션 출력은 셸 변수로만 받고 화면에 표시하지 않음
bws personal
```

이미 로그인되어 있는데 invalid_grant가 반복되면 `bw logout` 후 `bwl`로 재로그인한다.
인증과 2FA는 사용자가 직접 한다. 캐시 파일을 자동 삭제하거나 버전을 임의로 내리지 않는다.
대시보드는 Bitwarden 로그인과의 동시 접근을 피하려고 이제 bw status를 자동 실행하지 않는다.
현재 vault 상태는 터미널의 bwu/bw status로 확인한다.

기존 Oh My Zsh가 설치되어 있어도 선택 기능이 꺼져 있으면 테마를 읽지 않는다.
화면의 Oh My Zsh를 켜고 설치 경로·테마를 확인한 뒤 저장·configure한다.
기존 robbyrussell 테마와 git 플러그인은 이 기능으로 복원할 수 있다.
설치는 자동 실행하지 않는다.

SSH 공통 Include 파일은 WSL의 /mnt/c 권한 차이로 OpenSSH 검사가 실패하지 않도록
~/.ssh/config.d/dotfiles.conf에 600 권한으로 복사한다. Git pull로 원본이 바뀌면 configure를
다시 실행해서 이 사본도 갱신한다.
