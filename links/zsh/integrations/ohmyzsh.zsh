# Opt-in framework: read an existing installation, never download at shell startup.
export ZSH="${ZSH:-$HOME/.oh-my-zsh}"
ZSH_THEME="${ZSH_THEME:-robbyrussell}"
plugins=(git)
if [[ -r "$ZSH/oh-my-zsh.sh" ]]; then
  source "$ZSH/oh-my-zsh.sh"
else
  print -u2 'Oh My Zsh가 선택됐지만 설치 경로를 찾을 수 없습니다. 대시보드 경로를 확인하세요.'
fi
