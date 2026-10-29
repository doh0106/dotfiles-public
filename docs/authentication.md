# Git과 SSH 인증

공개 저장소는 HTTPS로 인증 없이 가져온다. Git identity와 SSH 인증은 별개다.
`user.email`은 커밋 작성자 정보이고, 로그인 계정을 선택하지 않는다.

## 개인 계정

`links/git/config`는 개인 remote owner에만 개인 identity를 조건부 include한다.
HTTPS 주소를 SSH로 바꾸는 전역 규칙은 두지 않는다. 인증이 필요한 clone/push에서는
`git@github-personal:doh0106/REPOSITORY.git`처럼 SSH alias를 명시한다.

SSH는 `~/.ssh/keys/github-personal.pub`에 대응하는 private key를 agent에서 선택한다.
이 public key로 private key를 복원할 수 없으며 실제 private key는 Bitwarden이 보관한다.

```sh
bws
ssh-add -l
ssh -T github-personal
```

GitHub가 성공 메시지를 출력하면서 exit code 1을 반환하는 것은 정상이다.
실제 인증 성공 여부는 메시지를 확인한다.

## 비공개 설정

Git은 `~/.config/dotfiles/private/git/config`, SSH는
`~/.config/dotfiles/private/ssh/config`를 포함한다. 파일이 없어도 개인 설정은 동작한다.
SSH는 먼저 얻은 값을 사용하므로 비공개 Host 규칙을 공통 기본값보다 먼저 읽는다.
비공개 SSH 파일 마지막에는 `Host *`를 두어 이후 Include 범위를 초기화한다.

비공개 설정에는 필요한 소유자의 URL 변환과 조건부 identity만 둔다.
공개·비공개 remote가 한 저장소에 섞여 있다면 의도한 identity를 로컬로 지정한다.

```sh
git config --local user.name 'Your Name'
git config --local user.email 'your-email@example.com'
git config --show-origin --get user.email
git remote get-url origin
ssh -G github-personal
```

미분류 저장소에서는 identity가 비어 있어 커밋이 실패한다. 잘못된 계정으로 커밋하는
것을 막기 위한 동작이다.

기준 문서: [Git includes](https://git-scm.com/docs/git-config#_includes),
[OpenSSH Include와 IdentityFile](https://man.openbsd.org/ssh_config).
