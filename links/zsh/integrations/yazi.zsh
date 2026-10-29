# Yazi를 종료한 위치로 현재 zsh의 작업 디렉터리를 옮긴다.
y() {
  command -v yazi >/dev/null 2>&1 || {
    print -u2 'yazi가 설치되어 있지 않습니다. macOS에서는 brew install yazi로 설치하세요.'
    return 127
  }

  local tmp cwd yazi_status
  tmp="$(mktemp -t 'yazi-cwd.XXXXXX')" || return 1

  command yazi "$@" --cwd-file="$tmp"
  yazi_status=$?
  IFS= read -r -d '' cwd < "$tmp" || true
  command rm -f -- "$tmp"

  [[ "$cwd" != "$PWD" && -d "$cwd" ]] && builtin cd -- "$cwd"
  return "$yazi_status"
}
