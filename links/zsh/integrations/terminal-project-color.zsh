# 현재 경로에 맞춰 Ghostty 본문색 또는 iTerm2 탭 chrome 색을 설정한다.
# 터미널별 규칙은 links/terminal/ 아래의 데이터 파일에서만 읽는다.

[[ -o interactive && ( "${TERM_PROGRAM:-}" == "ghostty" || "${TERM_PROGRAM:-}" == "iTerm.app" ) ]] || return 0

_dotfiles_iterm_set_tab_color() {
  local color="$1" red green blue

  if [[ "$color" == default ]]; then
    printf '\e]6;1;bg;*;default\a'
    return 0
  fi

  red=$(( 16#${color[2,3]} ))
  green=$(( 16#${color[4,5]} ))
  blue=$(( 16#${color[6,7]} ))
  printf '\e]6;1;bg;red;brightness;%d\a' "$red"
  printf '\e]6;1;bg;green;brightness;%d\a' "$green"
  printf '\e]6;1;bg;blue;brightness;%d\a' "$blue"
}

_dotfiles_terminal_project_color() {
  local integration_file terminal_dir config_file line remainder pattern background foreground color

  integration_file="${functions_source[_dotfiles_terminal_project_color]:A}"
  terminal_dir="${integration_file:h:h:h}/terminal"

  if [[ "${TERM_PROGRAM:-}" == "ghostty" ]]; then
    config_file="${DOTFILES_GHOSTTY_COLORS:-$HOME/.config/dotfiles/terminal/ghostty.conf}"

    if [[ -r "$config_file" ]]; then
      while IFS= read -r line || [[ -n "$line" ]]; do
        [[ -z "$line" || "$line" == \#* ]] && continue

        foreground="${line##*|}"
        remainder="${line%|*}"
        background="${remainder##*|}"
        pattern="${remainder%|*}"
        if [[ "$remainder" == "$line" || "$pattern" == "$remainder" \
          || -z "$pattern" || -z "$background" || -z "$foreground" \
          || ! "$background" =~ '^#[0-9A-Fa-f]{6}$' \
          || ! "$foreground" =~ '^#[0-9A-Fa-f]{6}$' ]]; then
          print -u2 "dotfiles: Ghostty 프로젝트 색 규칙 무시 (형식 오류): $line"
          continue
        fi

        [[ "$pattern" == /* ]] || pattern="$HOME/$pattern"
        if [[ "$PWD" == ${~pattern} ]]; then
          printf '\e]10;%s\e\\\e]11;%s\e\\' "$foreground" "$background"
          return 0
        fi
      done < "$config_file"
    fi

    printf '\e]110\e\\\e]111\e\\'
    return 0
  fi

  config_file="${DOTFILES_ITERM_COLORS:-$HOME/.config/dotfiles/terminal/iterm.conf}"
  if [[ -r "$config_file" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
      [[ -z "$line" || "$line" == \#* ]] && continue

      color="${line##*|}"
      pattern="${line%|*}"
      if [[ "$pattern" == "$line" || -z "$pattern" || -z "$color" \
        || ! "$color" =~ '^#[0-9A-Fa-f]{6}$' ]]; then
        print -u2 "dotfiles: iTerm2 탭 색 규칙 무시 (형식 오류): $line"
        continue
      fi

      [[ "$pattern" == /* ]] || pattern="$HOME/$pattern"
      if [[ "$PWD" == ${~pattern} ]]; then
        _dotfiles_iterm_set_tab_color "$color"
        return 0
      fi
    done < "$config_file"
  fi

  _dotfiles_iterm_set_tab_color default
}

autoload -Uz add-zsh-hook
# 이전 통합을 source한 기존 셸도 새 훅만 남기도록 정리한다.
add-zsh-hook -d chpwd _dotfiles_ghostty_dircolor 2>/dev/null || true
add-zsh-hook -d precmd _dotfiles_ghostty_dircolor 2>/dev/null || true
add-zsh-hook -d chpwd _dotfiles_terminal_project_color 2>/dev/null || true
add-zsh-hook chpwd _dotfiles_terminal_project_color
add-zsh-hook -d precmd _dotfiles_terminal_project_color 2>/dev/null || true
add-zsh-hook precmd _dotfiles_terminal_project_color
_dotfiles_terminal_project_color
