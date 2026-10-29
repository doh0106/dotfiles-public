# dotfiles의 프로젝트 색상 편집 UI를 어느 경로에서나 연다.
terminal-colors() {
  local integration_file="${functions_source[terminal-colors]:A}"
  command "${integration_file:h:h:h:h}/bin/terminal-colors" "$@"
}
