# 선택 기능: Windows에서 WSL SSH로 연결 전달

이 기능은 Git 서비스에 접속하는 클라이언트 인증과 별개다. 대시보드 configure와 앱 실행은
SSH 서버·포트 전달·방화벽을 설정하지 않는다.

## 준비

WSL에서 SSH 서버를 직접 구성하고 공개키를 `~/.ssh/authorized_keys`에 등록한다.
서버 포트와 공개키 인증 정책을 확인한 뒤, Windows에서 해당 포트로 접근할 수 있는지 확인한다.
서버 설정이나 개인 LAN 주소·키 항목 이름은 공개 저장소에 기록하지 않는다.

## 연결 전달

관리자 PowerShell에서 실행한다. 경로의 배포판, LAN 주소, 포트는 실제 값으로 바꾼다.

```powershell
& "\\wsl.localhost\Ubuntu-24.04\home\USER\personal\dotfiles\bin\enable-wsl-ssh.ps1" -ListenAddress <LAN-IP> -Distribution Ubuntu-24.04 -Port 2222
```

스크립트는 WSL eth0 주소와 SSH 포트의 접근 가능 여부를 확인한 뒤 Windows portproxy와
방화벽 규칙을 만든다. WSL 주소가 바뀌면 다시 실행한다. 공유기는 별도로 설정한다.
이 안내는 해당 기능을 보존하기 위한 것으로, 현재 정리 과정에서는 실행하지 않았다.

## 제거

관리자 PowerShell에서 실제 설정한 주소와 포트를 넣는다.

```powershell
& "$env:WINDIR\System32\netsh.exe" interface portproxy delete v4tov4 listenaddress=<LAN-IP> listenport=2222
Remove-NetFirewallRule -Name Dotfiles-WSL-SSH-2222
```

예전 WSL 전용 bootstrap은 현재 `python3 bin/dashboard.py configure`로 대체한다.
예전 공용 agent 자동 로드는 적용하지 않는다. 현재 인증 로더의 명시적 키 로드·수명·정리 절차를 따른다.
