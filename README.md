# dotfiles

macOS·Linux·WSL용 공통 사용자 설정. 인증 없이 가져와 기본 설정을 적용하고,
Bitwarden에서 개인 SSH 키를 불러온 뒤 비공개 설정과 작업 저장소를 연결한다.
Windows 네이티브 PowerShell 설정은 포함하지 않는다.

## 새 기기에서 시작

Git이 없다면 OS 패키지 관리자로 설치한다. 또는 GitHub에서 ZIP을 내려받아 압축을 푼다.
Python 3도 bootstrap 실행 전에 필요하다.

```sh
git clone https://github.com/doh0106/dotfiles.git "$HOME/dotfiles"
cd "$HOME/dotfiles"
./bin/install-prerequisites.sh
./bin/bootstrap.sh
zsh
```

이 URL은 공개 저장소 배치 후 사용하는 최종 주소다. 현재 GitHub에 같은 이름의
비공개 저장소가 남아 있다면, 먼저 이름을 변경하거나 새 공개 주소를 사용해야 한다.

사전 도구 설치기는 macOS에서 Homebrew, Debian/Ubuntu·WSL에서 apt를 사용한다.
Linux의 Bitwarden CLI는 [공식 배포 안내](https://bitwarden.com/help/cli/)에 따라
별도로 설치해야 한다. 다른 Linux 배포판도 필요한 명령을 직접 설치하면 된다.
필요한 명령은 `git python3 zsh jq bw ssh ssh-add ssh-keygen`이다.

bootstrap은 패키지를 설치하거나 비밀값을 가져오지 않는다. 기존 `.zshrc`와 SSH config에
관리 블록을 추가하고 기존 내용을 유지한다. 변경 전 `.bak.<timestamp>`를 만든다.
과거 dotfiles가 전체 파일을 심볼릭 링크로 연결한 경우에는 그 링크를 백업하고
새 관리 파일을 만든다. 백업에 있던 기기별 설정은 `~/.config/dotfiles/local.zsh`로 옮긴다.
기존 Git include 중 다른 checkout을 가리키는 항목은 전환 전에 직접 확인·제거한다.

## 개인 키 로드

```sh
bw login  # 최초 1회, 인증은 직접 진행
bws       # 필요할 때 unlock, 개인 키 로드
ssh -T github-personal
```

`secrets.json`의 `personal-github-ssh-key`는 Bitwarden Secure Note의 본문에 있는
기존 개인 private key를 읽는다. Native SSH Key 항목을 쓴다면 `bw_type`을 `sshkey`로
바꾼다. 실제 private key를 저장소에 복사하지 않는다.

사용 가능한 agent가 없으면 `bws`가 현재 셸용 agent를 시작한다. 이미 실행 중인 agent는
재사용한다. 생성한 agent는 사용 후 `ssh-agent -k`로 종료할 수 있다.
Bitwarden 잠금과 agent에서 키를 제거하는 것은 별도다 (`bw lock`, `ssh-add -d <public-key>`).

공개 저장소의 HTTPS URL은 SSH로 자동 변환하지 않는다. 따라서 키를 로드하지 않아도
이 공개 저장소를 clone/pull할 수 있다. 비공개 저장소는 SSH alias를 명시해 가져온다.

공개 저장소에 push할 때만 SSH를 쓰려면 해당 checkout에서 다음처럼 설정한다.

```sh
git remote set-url --push origin git@github-personal:doh0106/dotfiles.git
```

## 비공개 설정 연결

공개 저장소에는 회사 계정, 서버 주소, 회사 public key, 업무 프로젝트 경로를 두지 않는다.
이 데이터만 비공개 `dotfiles-private`에 둔다. 공통 스크립트를 복사하지 않는다.

```sh
git clone git@github-personal:doh0106/dotfiles-private.git "$HOME/dotfiles-private"
"$HOME/dotfiles/bin/attach-private.sh" "$HOME/dotfiles-private"
exec zsh
bws
```

위 비공개 저장소 주소는 해당 저장소를 GitHub에 만든 뒤 사용할 주소다.
로컬 사본으로 시작한다면 clone 없이 `attach-private.sh`에 그 경로를 전달한다.
연결기는 디렉터리를 `~/.config/dotfiles/private`에 심볼릭 링크로 연결할 뿐이며
스크립트를 실행하거나 인증하지 않는다. 새 zsh를 열면 해당 셸 설정이 로드된다.

| 경로 (비공개 저장소 기준) | 사용처 |
|---|---|
| `git/config`, `git/identities/` | Git include, 회사 URL·commit identity |
| `ssh/config`, `ssh/keys/` | SSH Include, 비공개 호스트·public key 선택 |
| `shell.zsh` | 공통 설정 다음, 기기별 local.zsh 이전에 로드 |
| `secrets.json` | bws가 개인 목록 다음에 로드 |
| `terminal/` | 비공개 프로젝트 색상 규칙 |

연결 해제는 `~/.config/dotfiles/private` 심볼릭 링크만 제거하고 새 셸을 연다.
이미 agent에 로드된 키는 남으므로 필요한 키는 별도로 제거한다.

## 기기별 설정과 업데이트

Git에 넣지 않을 기기별 셸 설정은 `~/.config/dotfiles/local.zsh`에 둔다.
공통 기능은 공개 저장소에서만 수정하고, 회사 정보는 비공개 저장소에서만 수정한다.
각 저장소를 `git pull`하면 연결된 파일에 반영된다. 새 파일이나 링크가 추가된 경우에는
bootstrap을 다시 실행한다. 경로를 옮겨도 bootstrap 또는 attach를 다시 실행하면 된다.

미분류 Git 저장소의 커밋은 빈 identity로 실패하도록 유지한다. 외부 저장소에서 커밋할 때는
해당 저장소의 `git config --local user.name`과 `user.email`을 명시한다.
개인 Git identity에는 실명·개인 이메일이 들어 있다. 공개 시 이 정보도 공개된다.

## 선택 기능

- Oh My Zsh는 이미 설치된 경우에만 읽는다. 자동 다운로드하지 않는다.
- zoxide, Yazi의 `y`, Zellij의 `zj`와 터미널 색상 기능은 유지한다.
- `pip`는 원래 의미를 유지한다. uv를 사용할 때는 `uv pip`를 직접 실행한다.
- `terminal-colors` UI는 로컬 색상 파일을 편집한다. 회사 설정이 연결된 셸에서는
  비공개 색상 파일을 편집하므로 업무 경로가 공개 저장소에 기록되지 않는다.
- Yazi.app과 `open` 기반 opener는 macOS 전용이다. Linux·WSL에서는 Yazi의 기본
  opener와 `y`를 쓰며, macOS 앱 링크를 설치하지 않는다.
- Dev Container는 `./bin/install-container-shell.sh`로 셸·Git·SSH만 연결한다.
  agent socket은 컨테이너 실행 환경이 전달해야 한다. 공개키는 같은 설정을 사용한다.

## 검증

```sh
./bin/verify.sh            # 오프라인 기본 검증, Bitwarden·agent 로그인 불필요
./bin/verify.sh --session  # Bitwarden unlock과 개인 agent key까지 확인
```

기본 검증 성공이 원격 인증 성공을 뜻하지는 않는다. 네트워크 인증은 별도로
`ssh -T github-personal`로 확인한다. macOS 앱 실행은 macOS에서 확인해야 한다.

상세: [인증](docs/authentication.md), [Bitwarden](docs/bitwarden.md),
[Yazi](docs/yazi.md), [Obsidian](docs/obsidian.md).
