# 공통 서비스와 개발 환경 관리

환경 대시보드는 개인 설정·Git/SSH 연결을 계속 관리한다. Jira·Confluence·Google의
공통 설정과 관측은 선택 설치한 environment-core에 위임한다.
비밀값을 대시보드 settings.json에 추가하지 않으며 기존 schema 3을 유지한다.

대시보드의 **서비스 인증**에서 Jira·Confluence·Google 설정과 인증 창을 열고,
**개발 환경 상태**에서 선택한 프로젝트의 Dev Container 구성·컨테이너 상태를 확인한다.
설정 저장·설치·현재 인증·실행 상태는 별개다. core 미설치는 해당 기능의 미관측 상태이며
기존 dotfiles의 Git·SSH·설정 적용을 막지 않는다.

## 공통 모듈 설치 위치

environment-core에서 `python3 cli.py register`로 코드 위치를 명시적으로 등록하면
대시보드와 앱 실행기가 `~/.config/environment-core/installation.json`을 읽는다.
개발 중에는 ENVIRONMENT_CORE_ROOT, DEV_ENVIRONMENT_ROOT, ENVIRONMENT_AGENT_KIT_ROOT로
명시 위치를 덮어쓸 수 있다. 프로세스 실행은 정확한 checkout의 고정 CLI와 격리된 Python을 사용한다.
잘못된 프로토콜·실패한 관측은 unavailable 또는 unknown으로 표시한다.

서비스 설정 창 열기는 사용자의 버튼 선택으로만 진행한다. 대시보드가 연 서버는
대시보드 종료 시 함께 종료하며, 기존 다른 터미널의 서버를 종료하지 않는다.
터미널의 Bitwarden·SSH·API 토큰 환경을 새 서비스 서버로 전달하지 않는다.

## 기존 기기 이전

1. 현재 셸·Git include·SSH·개인 설정 위치를 기록하고 백업한다.
2. 공개 checkout과 core를 준비하되 기존 bootstrap이나 configure를 바로 실행하지 않는다.
3. core는 기존 Agent Kit 상태 루트를 그대로 읽는다. 토큰 복사·symlink로 경로를 맞추지 않는다.
4. 공통 연결과 기존 제품의 계정을 확인한 뒤, 소비 프로그램은 연결 ID를 사용하도록 전환한다.
5. 옛 dotfiles include와 새 프로필의 중복을 검토한 후 별도로 configure한다.

이 구현은 옛 활성 셸/Git 설정을 자동 전환하지 않는다. 새 컴퓨터와 기존 기기의 전환은
서로 다른 절차다. 실제 서비스 계정의 접근은 사용자가 요청한 연결 확인에서 검증한다.
