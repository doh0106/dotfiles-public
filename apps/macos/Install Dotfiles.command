#!/bin/bash
set -euo pipefail
repo="$(cd "$(dirname "$0")/../.." && pwd -P)"
source_app="$repo/apps/macos/Dotfiles.app"
target="$HOME/Applications/Dotfiles.app"
mkdir -p "$HOME/Applications"
if [[ -e "$target" ]];then mv "$target" "$target.backup.$(date +%Y%m%d%H%M%S)";fi
cp -R "$source_app" "$target"
printf '%s\n' "$repo" > "$target/Contents/Resources/repository-path"
chmod +x "$target/Contents/MacOS/Dotfiles"
/usr/bin/open -R "$target"
printf '설치 완료: %s\n이제 Finder에서 Dotfiles를 더블클릭하세요.\n' "$target"
