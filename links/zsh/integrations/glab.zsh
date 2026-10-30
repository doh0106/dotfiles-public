# Select a connection before obtaining a per-command API token.
bwglab() {
  local supply
  supply="$(python3 "$(_dotfiles_auth_script)" needs-glab "$@")" || return 1
  if [[ "$supply" == bitwarden ]]; then bwu || return 1; fi
  python3 "$(_dotfiles_auth_script)" glab "$@"
}
glab() { bwglab "$@"; }
