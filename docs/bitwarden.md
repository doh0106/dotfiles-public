# Bitwarden 운영

기본 흐름은 대시보드의 작업 프로필·연결 → Bitwarden → SSH agent / HTTPS Git helper / gh·glab 자식 프로세스다.

## 준비할 항목

| 용도 | 지원 형식 | 내용 |
|---|---|---|
| 연결별 SSH 키 | Secure Note (`note`) | OpenSSH 개인키 본문 |
| 연결별 SSH 키 | Native SSH Key (`sshkey`) | `sshKey.privateKey` |
| HTTPS Git / API 토큰 | Secure Note (`note`) | 토큰 한 줄 |
| HTTPS Git / API 토큰 | Login (`login`) | 비밀번호 필드에 토큰 |

키의 public key 파일도 대시보드에 지정한 위치에 준비한다. 공개키는 agent에서 사용할 개인키를
선택하는 데 사용한다. 키를 agent에 넣기 전에 메모리에서 공개키를 추출해 대조한다.
추가 passphrase가 필요한 개인키는 기존 agent 공급자에서 먼저 준비한다. 실제 private key나 API 토큰을 dashboard/settings.json에 넣지 않는다.

새 대시보드에서는 **Git · SSH 연결 → 인증 참조**에 공급자·항목 이름·형식을 지정한다.
SSH 공개키 경로는 프로필이 아닌 연결에 속한다. HTTPS Git과 API 토큰 참조도 각각 선택한다.
Bitwarden을 사용하기 위해 Git 신원 설정을 강제로 켤 필요는 없다.

## 세션 명령

```sh
bwl             # 기기 최초 로그인/로그인 만료, 세션 출력은 캡처
bwu             # 잠금 해제, BW_SESSION은 현재 셸에서 export; 자식에 상속 가능
bws --connection YOUR-CONNECTION-ID # 선택 연결의 인증 준비
bws personal    # 프로필에 연결이 하나일 때의 단축형
bws             # 저장소 안: 현재 Git 폴더 프로필 + origin 호스트/방식
bwgh --connection YOUR-GITHUB-ID repo list # 해당 gh 자식에 토큰 주입
bwglab --connection YOUR-GITLAB-ID mr list  # 해당 glab 자식에 토큰 주입
gh pr list      # 저장소 안: 현재 프로필 토큰
bwe             # 관리 대상 키 제거, 빈 자체 agent 종료, CLI 잠금·셸 변수 정리
```

bws는 키 로드 전 vault를 sync한다. gh는 현재 로컬 vault에서 토큰을 읽는다.
다른 기기에서 토큰을 바꿨다면 `bw sync`한다. 이미 unlock됐다면 bwu는 세션을 재사용한다.
기본 키 TTL은 3600초이며 대시보드에서 60~86400초로 지정한다.
agent에 미리 있던 키는 재사용하므로 해당 키의 TTL은 보장하거나 덮어쓰지 않는다.

## 추가 서버 키

회사 외 서버 키 목록은 비공개 저장소의 `secrets.json`에 둘 수 있다.
자동으로 전부 불러오지 않고 명시적으로 선택한다.

```sh
bws --extras
```

이 모드는 `action=ssh-add`, `bw_type=note|sshkey`만 받는다. 추가 키에도 TTL을 적용하고
현재 셸에서 추적해 bwe가 제거한다. 중간 조회가 실패해도 앞서 추가된 키는 정리 대상으로 기록한다.

## 고급 수동 복원

기존 `bin/load-secrets.sh`는 별도 고급 로더로 유지한다. 이 로더는 manifest의
`ssh-add`, `write-file`, `eval-env`를 처리한다. 실행 시 전체 형식을 확인하고,
파일은 600 기본 권한의 임시 파일을 거쳐 교체한다.

```sh
bwu
source ./bin/load-secrets.sh /absolute/path/to/custom-secrets.json
```

이 경로는 bws의 기본 경로가 아니다. `write-file`은 의도적으로 비밀값을 디스크에 쓰며,
`eval-env`는 현재 셸에 값을 남긴다. 고급 로더로 넣은 키는 bwe의 관리 목록에 자동 등록되지 않는다.
SSH 키에는 `DOTFILES_KEY_LIFETIME` 또는 기본 3600초를 적용한다.
일반 Git·서비스 API에는 bws/bwgh/bwglab를 사용한다.

## 세션 상태와 한계

Bitwarden CLI는 암호화된 vault 캐시를 로컬에 저장한다. 마스터 비밀번호나 BW_SESSION은
dotfiles가 파일에 쓰지 않는다. SSH agent는 별도 프로세스이므로 bw lock이 agent 키를 지우지 않는다.
대시보드는 agent의 서버 기준 상태만 읽으며 vault 상태는 터미널 확인으로 표시한다.
로그인 중 CLI 캐시 갱신과 겹치지 않도록 화면에서 bw status를 자동 실행하지 않는다.
다른 터미널의 잠금 해제 여부나 키 만료 잔여시간을 추측하지 않는다. 토큰을 조회하거나 표시하지 않는다.

침해된 동일 사용자·관리자 프로세스는 메모리와 agent를 악용할 수 있다. 메모리 사용은
키 파일·백업·Git에 평문 키를 남기는 위험을 줄이는 방식이다.
