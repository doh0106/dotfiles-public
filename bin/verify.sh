#!/usr/bin/env bash
# Default checks need neither a vault session nor a network connection.
set -uo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
failures=0
check() {
  local label="$1"; shift
  if "$@" >/dev/null 2>&1; then echo "OK: $label"; else echo "FAIL: $label"; failures=$((failures+1)); fi
}
[[ $# -le 2 && "${1:-}" =~ ^(--session)?$ && "${2:-}" =~ ^([a-z][a-z0-9-]{0,63})?$ && ( $# -lt 2 || "${1:-}" == --session ) ]] || { echo 'usage: verify.sh [--session [PROFILE]]' >&2; exit 2; }
for cmd in git python3 zsh ssh ssh-keygen; do check "command $cmd" command -v "$cmd"; done
for public in "$repo_dir"/links/ssh/keys/*.pub; do
  [[ -f "$public" ]] && check 'bundled public key format' ssh-keygen -lf "$public"
done
check 'manifest syntax' python3 -c 'import json,sys; assert isinstance(json.load(open(sys.argv[1]))["secrets"],list)' "$repo_dir/secrets.json"
check 'shell link' test "$(readlink "$HOME/.config/dotfiles/shell.zsh")" = "$repo_dir/links/zsh/dotfiles.zsh"
check 'SSH include' ssh -G localhost
check 'Git include' sh -c 'git config --global --get-all include.path | grep -Fx "$HOME/.config/dotfiles/git/config"'
check 'public HTTPS remains HTTPS' sh -c '
  actual=$(GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 git -c include.path="$1" ls-remote --get-url https://github.com/doh0106/dotfiles.git)
  [ "$actual" = https://github.com/doh0106/dotfiles.git ]
' _ "$repo_dir/links/git/config"
if python3 -c 'import json,sys; from pathlib import Path; p=Path.home()/".config/dotfiles/dashboard/settings.json"; sys.exit(0 if p.exists() and json.loads(p.read_text())["git"]["enabled"] and json.loads(p.read_text())["git"].get("blockUnclassified",True) else 1)'; then
check 'unclassified commit identity blocked' sh -c '
  actual=$(GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 git -C /tmp -c include.path="$1" -c remote.origin.url=https://github.com/example/example.git config --get user.email)
  [ -z "$actual" ]
' _ "$repo_dir/links/git/config"
fi
if [[ "${1:-}" == --session ]]; then
  profile_args=()
  if [[ -n "${2:-}" ]]; then profile_args=(--profile "$2"); fi
  mode="$(python3 "$repo_dir/bin/auth.py" prepare "${profile_args[@]}")" || failures=$((failures+1))
  if [[ "${mode:-}" == *-bitwarden ]]; then
    check 'vault unlocked' sh -c '[ "$(python3 "$1" vault-status)" = unlocked ]' _ "$repo_dir/bin/auth.py"
  fi
  check 'selected connection authentication' python3 "$repo_dir/bin/auth.py" check "${profile_args[@]}"

fi
if [ "$failures" -gt 0 ]; then echo "Failed checks: $failures"; exit 1; fi
echo 'Verification passed.'
