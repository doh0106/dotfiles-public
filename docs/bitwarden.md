# Bitwarden 운영

이 문서는 `secrets.json`에 Bitwarden 항목을 등록하고 `bin/load-secrets.sh`로 불러오는
방법만 설명한다. 실제 private key, token, password 값은 Bitwarden에 저장하며 Git에
커밋하지 않는다.

기본적으로 secret을 파일에 저장하지 않는다. 단, `write-file`로 명시한 항목만 지정된
경로에 복원한다.

## 각 파일이 하는 일

- `secrets.json`: Bitwarden 항목 이름과 주입 방법을 기록한다. secret 값은 없다.
- `bin/load-secrets.sh`: 매니페스트를 읽고 각 항목을 agent, 환경변수 또는 파일로 전달한다.
- `links/zsh/integrations/bitwarden.zsh`: unlock만 하는 `bwu`, unlock 뒤 secret까지 로드하는 `bws` 함수를 정의한다.

평소에는 `bws`만 실행하면 된다. `bwu`는 unlock만 필요할 때 쓴다.

## 세션 열기

```bash
bw login  # 기기당 최초 1회
bws       # 새 Bitwarden 세션: unlock + secret 로드
```

`bws`는 내부에서 `bwu`를 실행한다. `bwu`는 `bw unlock --raw` 결과를 현재 셸의 `BW_SESSION` 환경변수에 저장한다. 마스터
비밀번호와 `BW_SESSION` 값은 파일이나 `.zshrc`에 저장하지 않는다. 셸을 종료하면 해당
셸이 가지고 있던 세션 값도 사라진다.

`bwu`를 사용할 수 없는 셸에서는 직접 실행할 수 있다.

```bash
export BW_SESSION=$(bw unlock --raw)
```

## 기존 SSH key를 Bitwarden에 올리기

private key를 저장하는 방식은 두 가지다. 어느 방식을 써도 최종적으로는 private key를
`ssh-agent`에 넣어 GitHub SSH 인증에 사용한다. 단, Bitwarden에서 key를 읽는 명령과
`secrets.json`의 `bw_type`은 방식에 맞춰야 한다.

아래 명령을 복사하기 전에 경로와 항목 이름을 한 번만 선언한다. 다른 위치나 이름을
쓴다면 이 블록만 바꾸면 된다.

```bash
DOTFILES_DIR="${DOTFILES_DIR:-$HOME/dotfiles}"
PERSONAL_KEY="${PERSONAL_KEY:-$HOME/.ssh/id_ed25519}"
PERSONAL_PUBLIC_KEY="${PERSONAL_PUBLIC_KEY:-${PERSONAL_KEY}.pub}"
PERSONAL_BW_ITEM="${PERSONAL_BW_ITEM:-personal-github-ssh-key}"
```

| 방식 | Bitwarden 항목 | `bw_type` | 로더가 private key를 읽는 곳 |
|---|---|---|---|
| A. 네이티브 SSH Key | SSH key | `sshkey` | `.sshKey.privateKey` |
| B. Secure Note | Secure Note | `note` | notes 본문 |

두 방식 모두 로드 결과는 같다.

```text
Bitwarden private key → ssh-add - → ssh-agent → github-personal
```

### A. Bitwarden SSH Key 항목으로 가져오기

Bitwarden Desktop에서 **New → SSH key → Import key from clipboard**를 선택한다.
개인 key는 `personal-github-ssh-key`로 저장한다.

```bash
pbcopy < "$PERSONAL_KEY"
# Bitwarden Desktop에서 Import key from clipboard 후 저장
printf '' | pbcopy
```

현재 Bitwarden은 OpenSSH 또는 PKCS#8 형식의 기존 key를 가져올 수 있다. 자세한 화면과
지원 형식은 [Bitwarden SSH Agent 공식 문서](https://bitwarden.com/help/ssh-agent/#import-key-to-bitwarden)를
참고한다.

`secrets.json`에는 다음처럼 등록한다.

```json
{
  "bw_name": "personal-github-ssh-key",
  "bw_type": "sshkey",
  "field": "private",
  "action": "ssh-add"
}
```

### B. Secure Note로 CLI에서 만들기

이미 Secure Note 방식으로 관리하거나 clipboard·UI를 거치고 싶지 않을 때 쓴다.
다음 명령은 private key 내용을 명령 인자나 터미널 출력에 넣지 않고, Bitwarden에
`personal-github-ssh-key` Secure Note를 만든다. 같은 이름의 항목이 이미 있으면 먼저
중복 여부를 확인한다.

```bash
export BW_SESSION=$(bw unlock --raw)

if bw list items --search "$PERSONAL_BW_ITEM" \
  | jq --arg name "$PERSONAL_BW_ITEM" -e 'any(.[]; .name == $name)' >/dev/null; then
  echo "$PERSONAL_BW_ITEM 항목이 이미 있습니다."
else
  bw get template item \
    | jq \
        --rawfile key "$PERSONAL_KEY" \
        --arg name "$PERSONAL_BW_ITEM" \
        '.type = 2
         | .name = $name
         | .notes = $key
         | .secureNote.type = 0' \
    | bw encode \
    | bw create item >/dev/null
fi
```

Bitwarden 폴더에 넣고 싶다면 `jq` 필터에 다음 줄을 추가한다.

```jq
| .folderId = "<Bitwarden-folder-id>"
```

Secure Note를 쓸 때는 `secrets.json`을 다음처럼 등록한다.

```json
{
  "bw_name": "personal-github-ssh-key",
  "bw_type": "note",
  "action": "ssh-add"
}
```

## 업로드 후 확인

### A. 네이티브 SSH Key 확인

저장된 public key의 fingerprint를 원본과 비교한다.

```bash
ssh-keygen -lf "$PERSONAL_PUBLIC_KEY"
bw get item "$PERSONAL_BW_ITEM" \
  | jq -r '.sshKey.publicKey' \
  | ssh-keygen -lf -
```

두 줄의 `SHA256:` 값이 같아야 한다.

### B. Secure Note 확인

Secure Note에는 별도 public key 필드가 없으므로, notes에서 읽은 private key를
`ssh-agent`에 넣고 원본 public key의 fingerprint와 비교한다.

```bash
expected_fingerprint=$(ssh-keygen -lf "$PERSONAL_PUBLIC_KEY" | awk '{print $2}')

bw get notes "$PERSONAL_BW_ITEM" | ssh-add -
ssh-add -l | grep -F "$expected_fingerprint"
```

마지막 명령이 해당 `SHA256:` fingerprint를 출력하면 Bitwarden Secure Note의 private
key가 원본 public key와 짝이 맞는다.

### 두 방식 공통 확인

`secrets.json`에 실제 항목 형식과 같은 `bw_type`을 등록한 뒤 전체 로더와 GitHub
인증도 확인한다.

```bash
bws
ssh-add -l
ssh -T github-personal
```

확인 전에는 로컬 private key를 삭제하지 않는다. 삭제가 필요하다면 Bitwarden 로드와
GitHub 인증까지 검증한 뒤 별도 작업으로 진행한다.

## secrets.json 항목 작성

SSH key는 위 두 방식 중 하나로 저장한다. `bw_type`은 실제 Bitwarden 항목 형식과
반드시 일치해야 한다.

```json
{
  "bw_name": "example-ssh-key",
  "bw_type": "sshkey",
  "field": "private",
  "action": "ssh-add"
}
```

환경변수 묶음은 Bitwarden Secure Note에 한 줄당 하나의 `KEY=VALUE`로 저장한다.

```text
EXAMPLE_API_TOKEN=...
ANOTHER_TOKEN=...
```

```json
{
  "bw_name": "example-development-env",
  "bw_type": "note",
  "action": "eval-env"
}
```

SOPS age key처럼 파일이 꼭 필요한 secret은 Secure Note에 저장하고 `write-file`을
사용한다.

```json
{
  "bw_name": "example-sops-age-key",
  "bw_type": "note",
  "action": "write-file",
  "dest": "~/.config/sops/age/keys.txt",
  "mode": "600"
}
```

## 주입 방식

| `action` | 결과 |
|---|---|
| `ssh-add` | private key를 파일로 만들지 않고 현재 `ssh-agent`에 전달한다. |
| `eval-env` | `KEY=VALUE` 줄을 현재 셸의 환경변수로 export한다. |
| `write-file` | 지정한 경로에 파일을 만들고 `mode` 권한을 적용한다. |

`eval-env`는 현재 셸을 변경해야 하므로 로더를 반드시 `source`로 실행해야 한다.

## 로드와 검증

```bash
bws
ssh-add -l
"$DOTFILES_DIR/bin/verify.sh" --session
```

`bws`는 먼저 Bitwarden을 unlock한 뒤 로더를 실행한다. 로더 자체는 Bitwarden을 자동으로
unlock하지 않으므로, 다른 셸에서 직접 로더를 부를 때는 먼저 `bwu` 또는 `bw unlock`이
필요하다. 다음 경우에는 non-zero로 종료한다.

- `secrets.json` 형식이 올바르지 않음
- Bitwarden sync 또는 항목 조회 실패
- SSH agent 등록 실패
- 환경변수 이름이 올바르지 않음
- `eval-env` 항목이 있는데 `source` 없이 실행함

## 유출 대응

private key나 token이 파일 공유, Git, 로그에 노출됐다면 파일만 지워서는 안 된다.

1. 해당 credential을 revoke하거나 rotate한다.
2. 접근 로그와 사용 범위를 확인한다.
3. Git에 들어갔다면 history 정리를 검토한다.
4. 새 credential을 Bitwarden에 저장하고 다시 로드해 검증한다.

## 비공개 목록

bws는 기본 개인 목록 다음에 `~/.config/dotfiles/private/secrets.json`도 읽는다.
`DOTFILES_SECRETS_MANIFEST`를 지정하면 기본·비공개 목록 대신 지정한 목록 하나만 읽는다.
로더를 직접 사용할 때는 `source "$DOTFILES_DIR/bin/load-secrets.sh" /path/to/secrets.json`으로 실행한다.
실패한 조회는 성공으로 처리하지 않으며, write-file은 제한된 권한의 임시 파일을 거쳐 교체한다.
