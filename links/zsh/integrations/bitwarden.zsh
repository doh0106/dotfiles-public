# Public key tracking stays in this shell; no private key/token files are created.
typeset -gA _dotfiles_managed_keys _dotfiles_owned_agents

_dotfiles_auth_script() {
  local integration="${functions_source[_dotfiles_auth_script]:A}"
  print -r -- "${integration:h:h:h:h}/bin/auth.py"
}

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
  [[ $# -le 1 && ( $# == 0 || "${1:-}" == personal || "${1:-}" == work || "${1:-}" == --extras ) ]] || {
    print -u2 'usage: bws [personal|work|--extras]'; return 2
  }
  local agent_result added result public socket script
  script="$(_dotfiles_auth_script)" || return 1
  # Unlock is interactive and always stays in the calling shell.
  bwu || return 1
  ssh-add -l >/dev/null 2>&1
  agent_result=$?
  if (( agent_result == 2 )); then
    eval "$(ssh-agent -s)" >/dev/null || return 1
    _dotfiles_owned_agents[$SSH_AUTH_SOCK]="$SSH_AGENT_PID"
  elif (( agent_result > 2 )); then
    return "$agent_result"
  fi
  socket="$SSH_AUTH_SOCK"
  if [[ "${1:-}" == --extras ]]; then
    added="$(python3 "$script" extras)"
  elif [[ -n "${1:-}" ]]; then
    added="$(python3 "$script" load --profile "$1")"
  else
    added="$(python3 "$script" load)"
  fi
  result=$?
  # Track partial success too (e.g. the second extra key failed).
  for public in "${(@f)added}"; do
    [[ -n "$public" ]] || continue
    _dotfiles_managed_keys[$socket]+="$public"$'\n'
  done
  (( result == 0 )) && print 'SSH key ready. New keys have the configured expiry; run bwe after use.'
  return "$result"
}

bwe() {
  local socket public failed=0 owned_pid identities probe_result remaining
  # Do not kill shared agents or delete their unrelated/pre-existing identities.
  for socket in "${(@k)_dotfiles_managed_keys}"; do
    identities="$(SSH_AUTH_SOCK="$socket" ssh-add -L 2>/dev/null)"
    probe_result=$?
    if (( probe_result > 1 )); then
      print -u2 'Cannot reach a tracked agent; retaining its cleanup record. Key TTL still applies.'
      failed=1
      continue
    fi
    remaining=''
    for public in "${(@f)_dotfiles_managed_keys[$socket]}"; do
      [[ -n "$public" ]] || continue
      if print -r -- "$identities" | awk '{print $1 " " $2}' | grep -Fxq -- "$public"; then
        if ! printf '%s\n' "$public" | SSH_AUTH_SOCK="$socket" ssh-add -d - >/dev/null 2>&1; then
          remaining+="$public"$'\n'
          failed=1
        fi
      fi
    done
    if [[ -n "$remaining" ]]; then
      _dotfiles_managed_keys[$socket]="$remaining"
    else
      unset "_dotfiles_managed_keys[$socket]"
    fi
  done
  for socket in "${(@k)_dotfiles_owned_agents}"; do
    owned_pid="${_dotfiles_owned_agents[$socket]}"
    # If another program added keys to our agent, keep that agent alive.
    SSH_AUTH_SOCK="$socket" ssh-add -l >/dev/null 2>&1
    if (( $? == 1 )); then
      if SSH_AUTH_SOCK="$socket" SSH_AGENT_PID="$owned_pid" ssh-agent -k >/dev/null 2>&1; then
        unset "_dotfiles_owned_agents[$socket]"
        if [[ "${SSH_AUTH_SOCK:-}" == "$socket" ]]; then unset SSH_AUTH_SOCK SSH_AGENT_PID; fi
      else
        failed=1
      fi
    fi
  done
  command bw lock >/dev/null 2>&1 || failed=1
  unset BW_SESSION GH_TOKEN GITHUB_TOKEN
  if (( failed )); then
    print -u2 'Session variables cleared, but some cleanup failed. Retry bwe; unreachable keys retain their TTL.'
  else
    print 'Session cleared. Managed SSH keys removed; existing agents/keys preserved.'
  fi
  return "$failed"
}
