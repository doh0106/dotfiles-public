# 개인·회사 Git 프로필과 인증

Git의 커밋 계정과 GitHub API 인증은 별개다. 두 인증 수단은 Bitwarden에 보관하고,
어떤 프로필을 사용할지는 Git 저장소의 폴더로 선택한다.

## 프로필 선택

대시보드에서 개인 폴더(기본 `~/personal/`)와 선택적 회사 폴더(기본 `~/work/`)를 지정한다.
두 폴더는 겹치거나 중첩되면 안 된다. 각 프로필에 커밋 이름·이메일과 공개키 경로를 입력한다.
회사 이름·이메일·키 항목은 공개 저장소에 기본값으로 기록하지 않는다.

생성되는 로컬 Git 설정의 구조는 다음과 같다.

```gitconfig
[includeIf "gitdir:~/personal/"]
    path = personal.gitconfig
[includeIf "gitdir:~/work/"]
    path = work.gitconfig
```

실제 파일에는 정규화한 절대 폴더를 기록한다. 프로필 파일은 `user.name`, `user.email`,
`core.sshCommand`, `dotfiles.profile`을 지정한다. SSH 명령은 해당 공개키와
`IdentitiesOnly=yes`를 사용해 agent의 대응 개인키를 선택한다.
Git identity를 켜면 미분류 폴더에서 커밋을 차단한다. 끄면 기존 identity를 유지한다.

```sh
cd ~/personal/my-project
git config --show-origin --get user.email
git config --show-origin --get core.sshCommand
git config --get dotfiles.profile
```

Git은 현재 터미널 경로 자체가 아니라 저장소의 Git 디렉터리로 조건을 평가한다.
linked worktree는 원본 저장소의 Git 메타데이터 경로를 따라 프로필을 선택한다.
API wrapper도 `git-common-dir`로 같은 원본 폴더를 확인한다. 다른 계정을 원하는 worktree는
별도 프로필의 새 clone을 쓰는 것이 기본 정책이다. 저장소의 로컬 Git override가 프로필과
충돌하면 wrapper가 실행을 중단한다.

## 키 로드와 최초 clone

```sh
bws personal  # 저장소 밖: 명시적 프로필
cd ~/personal/my-project
bws           # 저장소 안: Git 프로필 자동 선택
```

SSH 개인키를 파일로 만들지 않는다. 새로 로드하는 키에는 대시보드의 TTL(기본 3600초)을 적용한다.
선택한 공개키와 불러온 개인키가 맞는지 agent의 공개키 목록으로 확인한다.
agent에 이미 있던 같은 키는 그대로 재사용하며 만료시간도 변경하지 않는다.

인증이 필요한 remote는 `git@github.com:OWNER/REPO.git`을 사용한다.
공개 HTTPS 주소는 자동으로 SSH로 바꾸지 않는다. `user.email`만 바꿔서는 HTTPS 인증이 바뀌지 않는다.

최초 clone은 아직 대상 저장소의 gitdir 조건을 사용할 수 없으므로 프로필을 한 번 명시한다.

```sh
bws personal
git -c include.path="$HOME/.config/dotfiles/dashboard/personal.gitconfig" \
  clone git@github.com:OWNER/REPO.git "$HOME/personal/REPO"
```

회사 저장소는 `bws work`, `work.gitconfig`, 회사 폴더를 사용한다.

## GitHub CLI

GitHub API는 SSH 키로 인증할 수 없다. 대시보드에서 GitHub CLI를 켜고 개인·회사 토큰의
Bitwarden 항목 이름과 형식을 지정한다. Secure Note 본문 또는 Login 비밀번호 필드에
토큰 한 줄만 저장한다. 토큰 권한·만료·조직 승인은 GitHub에서 수행한다.

```sh
cd ~/personal/my-project
gh pr list
cd ~/work/company-project
gh issue list
bwgh --profile personal repo list  # 저장소 밖 또는 명시적 계정
```

새 zsh의 `gh` 함수는 현재 프로필을 확인하고 Bitwarden에서 토큰을 읽어 **gh 자식 프로세스에만**
`GH_TOKEN`으로 전달한다. 셸에 토큰을 export하거나 파일·키체인에 저장하지 않는다.
환경에 남아 있던 다른 토큰보다 선택한 토큰을 우선하며 조회 실패 시 실행하지 않는다.
Bitwarden 잠금 해제 세션(BW_SESSION)은 gh 자식 프로세스에 전달하지 않는다.
`gh -R ...`은 프로필을 바꾸지 않는다. 다른 계정을 쓰려면 `bwgh --profile ...`을 명시한다.
현재 wrapper의 대상 호스트는 github.com이다. GitHub Enterprise 인증은 아직 지원하지 않는다.

`gh auth login/setup-git/refresh/switch/token`은 wrapper에서 막는다. gh 로그인 저장소나
Git credential helper 설정을 별도로 만들지 않기 위해서다. `command gh`는 wrapper를 우회하므로
의도적으로 필요한 경우에만 쓴다. CLI·인증 helper는 자동 설치하지 않는다.
토큰을 다른 기기에서 변경했다면 `bw sync` 후 다시 실행한다.

## 정리

```sh
bwe
```

현재 셸에서 이 구성으로 새로 추가한 키만 제거한다. 공유 agent의 기존 키는 보존한다.
직접 시작한 agent는 비어 있을 때만 종료하며, 다른 프로그램이 키를 넣었다면 보존한다.
Bitwarden CLI 잠금을 시도하고 `BW_SESSION`, `GH_TOKEN`, `GITHUB_TOKEN`을 현재 셸에서 지운다.
다른 셸·이미 실행 중인 자식 프로세스의 환경변수나 GitHub 토큰 자체를 폐기하는 작업은 아니다.

터미널 닫기·Bitwarden 잠금만으로 SSH agent 키가 제거되는 것은 아니다. 사용 후 `bwe`를 실행한다.
갑작스러운 셸 종료 시에는 TTL이 새로 추가한 키의 수명을 제한한다. 미리 있던 키에는 적용되지 않는다.
Bitwarden CLI의 암호화된 캐시는 로컬에 남는다. RAM 사용이 침해된 기기에서의 안전을 보장하지는 않는다.

원칙은 '개인키·API 토큰을 일반 파일에 남기지 않기'이며, 설정·공개키·암호화 vault 캐시는 남는다.

기준: [Git includeIf](https://git-scm.com/docs/git-config#_includes),
[ssh-add lifetime](https://man.openbsd.org/ssh-add),
[gh 환경변수](https://cli.github.com/manual/gh_help_environment).
