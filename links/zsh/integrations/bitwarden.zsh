# Keep all runtime state local except BW_SESSION and SSH agent environment.
bwu() {
  command -v bw >/dev/null 2>&1 && command -v jq >/dev/null 2>&1 || {
    print -u2 'Install bw and jq first.'; return 1
  }
  local vault_status session
  vault_status="$(bw status | jq -er '.status')" || return 1
  case "$vault_status" in
    unlocked) return 0 ;;
    unauthenticated) print -u2 'Run bw login first.'; return 1 ;;
    locked)
      session="$(bw unlock --raw)" || return 1
      [[ -n "$session" ]] || return 1
      export BW_SESSION="$session" ;;
    *) print -u2 'Unexpected Bitwarden status.'; return 1 ;;
  esac
}

bws() {
  local dotfiles_dir manifest agent_status
  dotfiles_dir="${DOTFILES_DIR:-${${functions_source[bws]}:A:h:h:h:h}}"
  bwu || return 1
  ssh-add -l >/dev/null 2>&1
  agent_status=$?
  # ssh-add returns 1 for an empty reachable agent and 2 for an unreachable agent.
  if (( agent_status == 2 )); then
    eval "$(ssh-agent -s)" >/dev/null || return 1
    print 'Started ssh-agent for this shell. Stop it with ssh-agent -k when done.'
  elif (( agent_status > 2 )); then
    return "$agent_status"
  fi
  if [[ -n "${DOTFILES_SECRETS_MANIFEST:-}" ]]; then
    source "$dotfiles_dir/bin/load-secrets.sh" "$DOTFILES_SECRETS_MANIFEST"
    return $?
  fi
  source "$dotfiles_dir/bin/load-secrets.sh" "$dotfiles_dir/secrets.json" || return 1
  manifest="$HOME/.config/dotfiles/private/secrets.json"
  if [[ -r "$manifest" ]]; then
    source "$dotfiles_dir/bin/load-secrets.sh" "$manifest" || return 1
  fi
  return 0
}
