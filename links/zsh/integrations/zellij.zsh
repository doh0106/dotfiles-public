# 현재 프로젝트 폴더를 이름으로 한 Zellij 세션을 만들거나 다시 연결한다.
zj() {
  command -v zellij >/dev/null 2>&1 || {
    print -u2 'zellij이 설치되어 있지 않습니다. dev-environment에서 설치하세요.'
    return 127
  }

  local session_name="${1:-${PWD:t}}"
  session_name="${session_name//[^[:alnum:]_.-]/-}"
  [[ -n "$session_name" ]] || session_name='workspace'

  command zellij attach --create "$session_name"
}
