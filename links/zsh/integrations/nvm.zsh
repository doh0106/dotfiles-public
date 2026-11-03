export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [ -r "$NVM_DIR/nvm.sh" ]; then
  source "$NVM_DIR/nvm.sh"
  if [[ -n "${DOTFILES_NODE_VERSION:-}" ]]; then
    nvm use --silent "$DOTFILES_NODE_VERSION" >/dev/null || print -u2 "dotfiles: 선택한 Node.js가 없습니다. 대시보드 적용 안내에서 설치하세요."
  fi
fi
if [ -r "$NVM_DIR/bash_completion" ]; then
  source "$NVM_DIR/bash_completion"
fi
