# Select a connection before obtaining a per-command API token.
bwgh() {
  local supply
  supply="$(python3 "$(_dotfiles_auth_script)" needs-gh "$@")" || return 1
  if [[ "$supply" == bitwarden ]]; then bwu || return 1; fi
  python3 "$(_dotfiles_auth_script)" gh "$@"
}
gh() { bwgh "$@"; }
