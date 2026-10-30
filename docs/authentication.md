# 작업 신원·Git 접속·API 인증

작업 폴더의 프로필은 설정 범위와 커밋 작성자를 고른다.
연결은 서비스 호스트와 Git 통신 방식을 고르고, 인증 참조는 필요한 키나 토큰의 공급자를 고른다.
한 프로필에 여러 연결을 둘 수 있다. GitHub SSH와 GitLab HTTPS도 동시에 사용할 수 있다.

## 생성되는 설정

```gitconfig
[includeIf "gitdir:/HOME/personal/"]
    path = /HOME/.config/dotfiles/dashboard/profile-personal.gitconfig
```

프로필 파일에는 선택한 `user.name`, `user.email`, `dotfiles.profile`이 들어간다.
SSH 연결이 있으면 `core.sshCommand = ssh -F <해당 프로필 SSH 설정>`을 넣고,
그 설정이 **호스트별** 공개키·사용자·포트를 지정한다. 모든 서비스가 같은 키를 쓰도록 고정하지 않는다.
HTTPS 연결이 있으면 `credential "https://HOST"`에 선택한 helper를 지정한다.
Bitwarden 공급자는 Python helper를 사용하고, 외부 helper 공급자는 사용자가 고른 helper에 맡긴다.
HTTPS 공개 읽기는 인증 참조 없이 사용할 수 있다.

Gitdir는 현재 작업 폴더 문자열이 아니라 Git 메타데이터 경로를 검사한다.
linked worktree도 원본 저장소의 Git common directory를 따른다.
CLI wrapper는 그 경로와 실제 `dotfiles.profile` 값이 맞는지 확인한다.

```sh
git config --show-origin --get user.email
git config --show-origin --get core.sshCommand
git config --show-origin --get-all credential.helper
git config --get dotfiles.profile
git remote -v
```

글로벌 관리 include는 configure 시 마지막에 둔다. 이후의 글로벌 설정, 저장소 로컬 설정,
실행별 `-c`가 설정을 바꿀 수 있으므로 출처를 확인한다. 외부 helper를 추가하면
Bitwarden 토큰을 그 helper가 저장할 수도 있다. Bitwarden helper 자체는 store/erase를 무시한다.

## 선택과 최초 clone

```sh
bws --connection YOUR-CONNECTION-ID
# 프로필에 연결이 하나일 때는 bws personal 도 가능
# 저장소 안에서는 gitdir + origin의 호스트·방식으로 선택
bws
```

연결이 둘 이상이고 대상이 모호하면 명시적인 ID를 요구한다. 관련 없는 연결로 자동 우회하지 않는다.
저장소 밖에서 처음 clone할 때는 대상 폴더가 아직 Git 저장소가 아니므로 적용 안내의 프로필 include를 쓴다.

```sh
git -c include.path="$HOME/.config/dotfiles/dashboard/profile-personal.gitconfig" \
  clone https://YOUR-HOST/OWNER/REPO.git "$HOME/personal/REPO"
```

SSH 연결은 공개키 파일이 먼저 필요하다. Bitwarden에서 개인키를 메모리로 읽어
`ssh-add -t TTL -`에 전달하고, 실제 추가된 키가 공개키와 맞는지 검사한다.
기존 agent 공급자는 키를 가져오지 않고 해당 공개키가 agent에 있는지만 확인한다.
HTTPS 연결은 SSH agent를 사용하지 않는다. Bitwarden을 골랐다면 bws가 vault만 준비하고,
Git이 인증을 요청할 때 helper가 토큰을 조회한다. URL의 호스트와 HTTPS 프로토콜을 확인한다.

SSH↔HTTPS를 바꾸어도 기존 remote는 그대로다. `git remote set-url origin URL`로 별도 변경한다.
Git SSH 호스트가 API 서비스 호스트와 다르면 API 탭에 후자를 따로 입력한다.

## 서비스 API

| 제품 | 도구 | 인증 주입 |
|---|---|---|
| GitHub.com / ghe.com | gh | GH_TOKEN, GH_HOST |
| GitHub Enterprise Server | gh | GH_ENTERPRISE_TOKEN, GH_HOST |
| GitLab / Self-Managed | glab | GITLAB_TOKEN, GITLAB_HOST, GITLAB_API_HOST |
| 다른 Git 호스트 | API 어댑터 없음 | Git SSH/HTTPS는 가능 |

```sh
bwgh --connection YOUR-GITHUB-CONNECTION pr list
bwglab --connection YOUR-GITLAB-CONNECTION mr list
# 해당 서비스의 저장소에서는 gh / glab 함수도 같은 경로 사용
```

Bitwarden 또는 지정 환경변수에서 토큰을 읽고 선택한 CLI 자식 프로세스에 전달한다.
상위 셸에 토큰을 새로 export하지 않으며 `BW_SESSION`이나 다른 공급자의 ambient token을 전달하지 않는다.
조회 실패 시 실행하지 않는다. 환경변수 공급자의 원래 변수는 부모 셸에 그대로 있으므로 직접 unset한다.
자식 프로세스에는 중복된 원래 환경변수도 제거하고 정해진 도구 변수로만 전달한다.

다른 호스트를 가리키는 옵션·URL·repo 인수를 거부한다. 연결 호스트와 다른 호스트의 저장소 안에서도
실행하지 않는다. 저장소 밖으로 이동해 연결을 명시한다. `-R`은 프로필 전환 옵션이 아니다.
auth status 이외의 인증 저장·토큰 출력 명령, `--show-token`은 wrapper에서 막는다.
`command gh` / `command glab`는 우회 경로이므로 별도 인증 정책이 적용된다.
이 wrapper가 임의 명령의 악의적인 동작을 격리하는 sandbox는 아니다.

현재 API 지원은 HTTPS·도메인 루트 구성을 기준으로 한다. GitLab 서브폴더 설치나 별도 API path,
다른 제품의 API 어댑터는 추가 구현이 필요하다.

## 정리와 진단

```sh
bwe
ssh-add -l
```

이 셸이 새로 추가한 키만 제거하고, 직접 만든 agent가 비면 종료한다. 기존 키는 보존한다.
새 키 TTL은 기본 1시간이며 기존 키의 TTL을 바꾸지 않는다. 다른 프로그램이 키를 추가한 agent는 유지한다.
정리에 실패한 agent는 기록을 보존해 재시도한다. 터미널 종료가 agent 종료를 보장하지는 않는다.
이 셸이 사용한 Bitwarden vault를 잠그고 알려진 세션 변수를 해제한다.
서버의 토큰 만료·폐기, 외부 helper 저장소, 사용자 정의 토큰 변수, 다른 터미널은 별도 관리다.

대시보드의 ‘설정됨’은 인증 성공을 뜻하지 않는다. 다음 순서로 진단한다.

1. 도구가 설치됐고 PATH에서 보이는가?
2. configure 후 새 셸을 열었는가?
3. 실제 gitdir 프로필과 remote 호스트·방식이 맞는가?
4. `.pub` 파일과 agent 키가 맞는가, 또는 HTTPS helper가 선택됐는가?
5. vault/환경변수 공급자가 준비됐는가?
6. 서버에 키가 등록됐고, 토큰 권한·만료·조직 승인이 충족되는가?

공식 근거: [Git 조건부 include](https://git-scm.com/docs/git-config#_conditional_includes),
[Git credential helper](https://git-scm.com/docs/gitcredentials),
[gh 환경변수](https://cli.github.com/manual/gh_help_environment),
[glab 환경변수](https://docs.gitlab.com/cli/configuration/#environment-variables).
