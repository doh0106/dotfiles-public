# 새 컴퓨터의 Tailscale 원격 접속 설정

대시보드의 **원격 접속 · Tailscale**에서 기존 집 WSL에 접속할 클라이언트를 준비한다.
처음 설정 화면의 선택 기능에서도 이 화면으로 이동할 수 있다.

## 기존 설정과 연결

- 일반 Git·SSH 연결은 기존 키·credential 계약을 유지한다.
- Tailscale SSH는 별도 클라이언트 설정으로 관리한다. 개인키를 복사하지 않는다.
- 비공개 dotfiles에서 집 WSL의 대상·로그인 신원·공개 호스트 지문을 불러올 수 있다.
  로컬 `origin/main` 또는 `HEAD`의 정확한 커밋을 읽으며 fetch나 네트워크 작업은 하지 않는다.
  불러온 뒤 검토·저장해야 한다. 원하는 경우 같은 항목을 직접 입력할 수도 있다.
- `~/.config/dotfiles/tailscale/settings.json`에 대상·출처·사용자 확인 기록을 저장한다.
  설정 디렉터리는 700, 설정과 생성 SSH 파일은 600이다. 토큰·개인키를 저장하지 않는다.
- 생성 파일은 `~/.config/dotfiles/tailscale/ssh.config`다. `links/ssh/config`에 이 파일의
  Include를 추가했으므로 기존 `python3 bin/dashboard.py configure`도 이 별칭을 적용한다.
- SSH만 적용하려면 `python3 bin/tailscale_setup.py apply-ssh`를 실행한다. 기존 사용자
  SSH 설정과 기존 Git 별칭을 보존·백업하고 Tailscale 파일만 읽는 관리 Include를 추가한다.
  기존 private dotfiles 심볼릭 링크의 내용과 원본 저장소도 보존한다. 로그인·네트워크 작업은 없다.
- 저장 시 Include가 이미 연결되어 있으면 생성 파일의 변경 내용이 바로 반영된다.
  기존 동일 별칭과 충돌하면 사용자 설정을 비교·정리한다. 기존 키·Git 설정을 자동 삭제하지 않는다.
- Windows 네이티브 SSH는 화면의 Host 블록을 `%USERPROFILE%\.ssh\config`에 병합한다.
  WSL의 `~/.ssh/config`와 별개다. Mac/Linux에서도 다른 OS의 서버가 설정을 대신 적용하지 않는다.

## 화면에서 따르는 순서

먼저 클라이언트 OS와 접속 대상을 준비·저장한다. 비공개 import를 사용하면 저장된 커밋을 표시한다.
그 뒤 다음을 순서대로 진행한다.

1. **설치**: 선택한 OS의 공식 설치 파일·패키지 안내를 따라 설치하고 앱을 연다.
2. **로그인**: 집 WSL을 등록한 것과 같은 신원으로 로그인한다. 로그인·MFA·OS 권한은 직접 완료한다.
3. **SSH 별칭 적용**: 화면의 생성 블록과 적용 명령을 실제 클라이언트에 적용한다.
4. **접속 확인**: `ssh <별칭>`으로 접속하고 첫 연결의 공개 지문을 신뢰하는 기록과 대조한다.
   원격 셸에서 `id -un`, `hostname`으로 대상 사용자·호스트를 확인한 뒤 `exit`한다.

각 단계의 **이 단계를 직접 완료했어요**는 사용자 확인 기록이다. 현재 로그인이나 SSH 성공을
대시보드가 자동 검증했다고 표시하지 않는다. 앞 단계를 확인해야 다음 기록을 남길 수 있다.
대상·신원·OS·지문이 바뀌면 기록을 초기화하며, 한 단계 확인을 취소하면 이후 확인도 취소한다.
단순 새로고침은 기록을 유지한다.

**이 서버의 설치·로그인 상태 확인**만 명시적으로 로컬 `tailscale status --json`을 호출한다.
서버 OS와 클라이언트 OS가 다르면 미확인으로 표시한다. CLI가 없다고 GUI 앱도 없다고 판정하지 않는다.
응답은 실행 여부·현재 신원·예상 신원 일치·조회 시각만 표시하고 원시 상태·AuthURL·다른 노드는 반환하지 않는다.
이 조회는 SSH 접속 확인이 아니다. 로그인·설치·SSH·서버 정책 변경을 버튼에서 자동 실행하지 않는다.

집 PC의 전원과 Windows 사용자 로그인, WSL 실행이 선행되어야 한다. 문서에 보관한 기존
OpenSSH 2222번과 Tailscale SSH 22번은 별도 경로다. 집 호스트 재구축·정책 변경은 이 화면의 범위가 아니다.
공개 지문이 맞지 않으면 기존 신뢰 기록을 삭제하지 말고 신뢰하는 호스트에서 다시 확인한다.

## 검증과 근거

공식 [설치 안내](https://tailscale.com/docs/install),
[macOS 설치 종류](https://tailscale.com/docs/concepts/macos-variants),
[CLI](https://tailscale.com/docs/reference/tailscale-cli),
[Tailscale SSH](https://tailscale.com/docs/features/tailscale-ssh)를 2026-11-07에 확인했다.
비공개 기존 설정 `aae3113`에서 대상과 공개 지문 3개를 읽는 경로를 확인했다.
실제 계정 로그인·집 WSL 네트워크 접속·재부팅 자동 시작은 이번 구현 검증에 포함하지 않았다.

```sh
python3 tests/tailscale_setup.py
python3 tests/dashboard.py
```

합성 데이터 검사: 단계 순서·stale 요청·대상 변경 초기화·설정/SSH 보존·고정 읽기 전용
관측·원시 상태 비노출·비공개 import. 브라우저에서는 입력→저장→4단계 기록→새로고침 유지와
Windows 안내·OS 변경 초기화를 확인했다. 실제 설치나 SSH 성공을 의미하지 않는다.
