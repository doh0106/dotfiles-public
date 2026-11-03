#!/usr/bin/env bash
# Run only an explicitly named tool; dashboard save/configure never invokes this file.
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
tool="${1:-}"; nvm_dir="${2:-$HOME/.nvm}"; node_version="${3:-lts/*}"
[[ $# -ge 1 && $# -le 3 ]] || { echo 'usage: install-tool.sh TOOL [NVM_DIR [NODE_VERSION]]' >&2; exit 2; }
case "$node_version" in 'lts/*'|22|24|system) ;; *) echo 'Unsupported Node version' >&2; exit 2;; esac
fetch() { python3 - "$1" "$2" <<'PY'
import sys,urllib.request
with urllib.request.urlopen(sys.argv[1],timeout=60) as r,open(sys.argv[2],'wb') as f:
    import shutil
    shutil.copyfileobj(r,f)
PY
}
temporary=''
cleanup() { [[ -z "$temporary" ]] || rm -rf -- "$temporary"; }
trap cleanup EXIT
scratch() { temporary="$(mktemp -d)"; }
package() {
  local formula="$1";shift
  if [[ "$(uname -s)" == Darwin ]]; then
    command -v brew >/dev/null || { echo 'Install Homebrew first: https://brew.sh' >&2; exit 1; }
    brew install "$formula"
  elif command -v apt-get >/dev/null; then
    local -a elevate=();[[ "$(id -u)" == 0 ]] || elevate=(sudo)
    "${elevate[@]}" apt-get update
    "${elevate[@]}" apt-get install -y "$@"
  else echo 'Use your OS package manager or the official installation link.' >&2;exit 1;fi
}
ensure_nvm() {
  if [[ ! -s "$nvm_dir/nvm.sh" ]]; then
    scratch;fetch 'https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.8/install.sh' "$temporary/install.sh"
    mkdir -p "$nvm_dir"
    NVM_DIR="$nvm_dir" PROFILE=/dev/null bash "$temporary/install.sh"
  fi
}
load_node() {
  export NVM_DIR="$nvm_dir"
  if [[ -s "$NVM_DIR/nvm.sh" ]]; then
    # nvm is not compatible with nounset in all versions.
    set +u;source "$NVM_DIR/nvm.sh" --no-use;nvm use --silent "$node_version";set -u
  fi
}
case "$tool" in
 zoxide|fzf|ripgrep|unzip|gitlfs)
  case "$tool" in ripgrep) cmd=rg;pkg=ripgrep;; gitlfs) cmd=git-lfs;pkg=git-lfs;; *) cmd="$tool";pkg="$tool";; esac
  command -v "$cmd" >/dev/null || package "$pkg" "$pkg" ;;
 fd) command -v fd >/dev/null || command -v fdfind >/dev/null || package fd fd-find ;;
 bat) command -v bat >/dev/null || command -v batcat >/dev/null || package bat bat ;;
 buildtools)
  if ! command -v make >/dev/null || ! command -v cc >/dev/null || ! command -v c++ >/dev/null; then
    if [[ "$(uname -s)" == Darwin ]];then xcode-select --install;else package unused build-essential;fi
  fi ;;
 ohmyzsh)
  # The second argument is the selected framework directory for this tool.
  if [[ ! -s "$nvm_dir/oh-my-zsh.sh" ]];then
    command -v git >/dev/null;command -v zsh >/dev/null
    scratch;fetch https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh "$temporary/install.sh"
    ZSH="$nvm_dir" RUNZSH=no CHSH=no KEEP_ZSHRC=yes sh "$temporary/install.sh" --unattended
  fi ;;
 nvm) ensure_nvm ;;
 node)
  ensure_nvm;export NVM_DIR="$nvm_dir";set +u;source "$NVM_DIR/nvm.sh" --no-use
  if [[ "$(nvm version "$node_version")" != v* ]];then nvm install "$node_version";fi
  set -u ;;
 uv|claude)
  command -v "$tool" >/dev/null && exit 0
  scratch
  if [[ "$tool" == uv ]];then
    fetch https://astral.sh/uv/install.sh "$temporary/install.sh"
    UV_NO_MODIFY_PATH=1 sh "$temporary/install.sh"
  else fetch https://claude.ai/install.sh "$temporary/install.sh";bash "$temporary/install.sh";fi ;;
 gemini)
  [[ "$node_version" == system ]] || load_node
  command -v gemini >/dev/null && exit 0
  command -v npm >/dev/null || { echo 'Select Node.js · nvm and install its Node version first.' >&2;exit 1; }
  node -e 'if(Number(process.versions.node.split(".")[0])<20)process.exit(1)'
  npm install -g @google/gemini-cli ;;
 aws)
  command -v aws >/dev/null && exit 0
  if [[ "$(uname -s)" == Darwin ]];then package awscli awscli;exit;fi
  case "$(uname -m)" in x86_64|aarch64) arch="$(uname -m)";; *) echo 'Unsupported AWS CLI architecture' >&2;exit 1;;esac
  scratch;fetch "https://awscli.amazonaws.com/awscli-exe-linux-$arch.zip" "$temporary/aws.zip"
  command -v unzip >/dev/null || { echo 'Select and install unzip first.' >&2;exit 1; }
  unzip -q "$temporary/aws.zip" -d "$temporary"
  mkdir -p "$HOME/.local/bin"
  "$temporary/aws/install" --install-dir "$HOME/.local/aws-cli" --bin-dir "$HOME/.local/bin" ;;
 ngrok)
  command -v ngrok >/dev/null && exit 0
  if [[ "$(uname -s)" == Darwin ]];then package ngrok ngrok;exit;fi
  case "$(uname -m)" in x86_64) arch=amd64;; aarch64|arm64) arch=arm64;; *) echo 'Unsupported ngrok architecture' >&2;exit 1;;esac
  scratch;fetch "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-$arch.tgz" "$temporary/ngrok.tgz"
  tar -xzf "$temporary/ngrok.tgz" -C "$temporary" ngrok
  mkdir -p "$HOME/.local/bin";install -m 755 "$temporary/ngrok" "$HOME/.local/bin/ngrok" ;;
 *) echo "Unknown tool: $tool" >&2;exit 2 ;;
esac
