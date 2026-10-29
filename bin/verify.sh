#!/usr/bin/env bash
# Default checks need neither a vault session nor a network connection.
set -uo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
failures=0
check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "OK: $label"; else echo "FAIL: $label"; failures=$((failures+1)); fi
}
[[ $# -le 1 && "${1:-}" =~ ^(--session)?$ ]] || { echo 'usage: verify.sh [--session]' >&2; exit 2; }
for cmd in git python3 zsh ssh ssh-keygen; do check "command $cmd" command -v "$cmd"; done
check 'personal public key' ssh-keygen -lf "$repo_dir/links/ssh/keys/github-personal.pub"
check 'manifest syntax' python3 -c 'import json,sys; assert isinstance(json.load(open(sys.argv[1]))["secrets"],list)' "$repo_dir/secrets.json"
check 'shell link' test "$(readlink "$HOME/.config/dotfiles/shell.zsh")" = "$repo_dir/links/zsh/dotfiles.zsh"
check 'SSH include' ssh -G github-personal
check 'Git include' sh -c 'git config --global --get-all include.path | grep -Fx "$HOME/.config/dotfiles/git/config"'
check 'public HTTPS remains HTTPS' sh -c '
  actual=$(GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 git -c include.path="$1" ls-remote --get-url https://github.com/doh0106/dotfiles.git)
  [ "$actual" = https://github.com/doh0106/dotfiles.git ]
' _ "$repo_dir/links/git/config"
check 'personal commit identity' sh -c '
  actual=$(GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 git -C /tmp -c include.path="$1" -c remote.origin.url=https://github.com/doh0106/example.git config --get user.email)
  [ "$actual" = doh0106@naver.com ]
' _ "$repo_dir/links/git/config"
check 'unclassified commit identity blocked' sh -c '
  actual=$(GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 git -C /tmp -c include.path="$1" -c remote.origin.url=https://github.com/example/example.git config --get user.email)
  [ -z "$actual" ]
' _ "$repo_dir/links/git/config"
if [[ "${1:-}" == --session ]]; then
  for cmd in bw jq; do check "command $cmd" command -v "$cmd"; done
  check 'vault unlocked' sh -c '[ "$(bw status | jq -r .status)" = unlocked ]'
  fingerprint=$(ssh-keygen -lf "$repo_dir/links/ssh/keys/github-personal.pub" | awk '{print $2}')
  check 'personal key in agent' sh -c 'ssh-add -l | grep -F "$1"' _ "$fingerprint"
fi
if [ "$failures" -gt 0 ]; then echo "Failed checks: $failures"; exit 1; fi
echo 'Verification passed.'
