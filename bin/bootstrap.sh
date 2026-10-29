#!/usr/bin/env bash
# Install shared settings without replacing existing SSH or zsh configuration.
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
config_dir="$HOME/.config/dotfiles"
mode="${1:-host}"
[[ "$mode" == host || "$mode" == container ]] && [[ $# -le 1 ]] || {
  echo 'usage: bootstrap.sh [host|container]' >&2; exit 2;
}
for cmd in git python3; do
  command -v "$cmd" >/dev/null || { echo "Required: $cmd" >&2; exit 1; }
done
mkdir -p "$config_dir" "$HOME/.ssh/keys" "$HOME/.ssh/config.d"
chmod 700 "$HOME/.ssh"
# One helper owns backups, managed blocks and private attachment for both platforms.
python3 "$repo_dir/bin/configure.py" install "$repo_dir" "$mode"
echo 'Settings installed. No secrets loaded.'
echo 'Select features in the dashboard, then open a new zsh. Authentication is optional and manual.'
