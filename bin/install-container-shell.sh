#!/usr/bin/env bash
# Reuse the same portable shell/Git/SSH configuration; no network installation.
set -euo pipefail
[[ $# == 0 ]] || { echo 'usage: install-container-shell.sh' >&2; exit 2; }
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
exec bash "$repo_dir/bin/bootstrap.sh" container
