#!/usr/bin/env bash
# Explicit dependency installation; bootstrap itself never installs packages.
set -euo pipefail
case "$(uname -s)" in
  Darwin)
    command -v brew >/dev/null || { echo 'Install Homebrew first: https://brew.sh' >&2; exit 1; }
    formulas=()
    for pair in git:git jq:jq bw:bitwarden-cli python3:python zsh:zsh; do
      command -v "${pair%%:*}" >/dev/null || formulas+=("${pair#*:}")
    done
    if [ "${#formulas[@]}" -gt 0 ]; then brew install "${formulas[@]}"; fi ;;
  Linux)
    command -v apt-get >/dev/null || { echo 'Install git python3 zsh jq openssh-client and Bitwarden CLI with your package manager.' >&2; exit 1; }
    if [ "$(id -u)" -eq 0 ]; then elevate=(); else elevate=(sudo); fi
    "${elevate[@]}" apt-get update
    "${elevate[@]}" apt-get install -y git python3 zsh jq openssh-client
    command -v bw >/dev/null || { echo 'Install Bitwarden CLI, then rerun: https://bitwarden.com/help/cli/' >&2; exit 1; } ;;
  *) echo 'Supported: macOS and Linux (including WSL).' >&2; exit 1 ;;
esac
for cmd in git python3 zsh jq bw ssh ssh-add ssh-keygen; do
  command -v "$cmd" >/dev/null || { echo "Missing: $cmd" >&2; exit 1; }
done
