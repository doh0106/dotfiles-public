# Use the profile at command time, never export a persistent GH_TOKEN.
bwgh() {
  bwu || return 1
  python3 "$(_dotfiles_auth_script)" gh "$@"
}
gh() {
  bwgh "$@"
}
