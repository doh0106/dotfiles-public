#!/usr/bin/env bash
set -euo pipefail
[[ $# == 1 ]] || { echo 'usage: attach-private.sh /path/to/dotfiles-private' >&2; exit 2; }
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
exec python3 "$repo_dir/bin/configure.py" attach "$1"
