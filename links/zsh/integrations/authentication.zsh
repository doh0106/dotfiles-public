# Public key tracking stays in this shell; no private key/token files are created.
typeset -gA _dotfiles_managed_keys _dotfiles_owned_agents

_dotfiles_auth_script() {
  local integration="${functions_source[_dotfiles_auth_script]:A}"
  print -r -- "${integration:h:h:h:h}/bin/auth.py"
}

bwu() {
  command -v bw >/dev/null 2>&1 || {
    print -u2 'Install bw first.'; return 1
  }
  local vault_status session
  vault_status="$(python3 "$(_dotfiles_auth_script)" vault-status)" || return 1
  case "$vault_status" in
    unlocked) typeset -g _dotfiles_vault_used=1; return 0 ;;
    unauthenticated) print -u2 'Bitwarden 로그인이 필요합니다. bwl로 로그인한 뒤 다시 실행하세요.'; return 1 ;;
    locked)
      session="$(bw unlock --raw)" || return 1
      [[ -n "$session" ]] || return 1
      export BW_SESSION="$session"
      typeset -g _dotfiles_vault_used=1 ;;
    *) print -u2 'Unexpected Bitwarden status.'; return 1 ;;
  esac
}

# Capture the raw session instead of printing the session key in terminal output.
bwl() {
  local session
  unset BW_SESSION
  session="$(command bw login --raw)" || {
    unset session
    print -u2 'Bitwarden 로그인 실패. 계속 invalid_grant가 나오면 bw logout 후 bwl을 다시 실행하세요.'
    return 1
  }
  if [[ -n "$session" ]]; then
    export BW_SESSION="$session"
  fi
  unset session
  bwu
}

bws() {
  local agent_result added result public socket script mode action=load
  script="$(_dotfiles_auth_script)" || return 1
  if [[ "${1:-}" == --extras ]]; then
    [[ $# == 1 ]] || return 2
    action=extras
    set --
    mode=ssh-bitwarden
  else
    if [[ -n "${1:-}" && "$1" != -* ]]; then
      set -- --profile "$1" "${@:2}"
    fi
    mode="$(python3 "$script" prepare "$@")" || return 1
  fi
  if [[ "$mode" == *-bitwarden ]]; then bwu || return 1; fi
  if [[ "$mode" == https-* || "$mode" == ssh-system ]]; then
    python3 "$script" load "$@"
    return $?
  fi
  ssh-add -l >/dev/null 2>&1
  agent_result=$?
  if (( agent_result == 2 )); then
    # Existing-agent mode must not silently create an empty replacement agent.
    [[ "$mode" == ssh-agent ]] && { print -u2 '선택한 기존 SSH agent에 연결할 수 없습니다.'; return 1; }
    eval "$(env -i PATH="$PATH" HOME="$HOME" TMPDIR="${TMPDIR:-/tmp}" ssh-agent -s)" >/dev/null || return 1
    _dotfiles_owned_agents[$SSH_AUTH_SOCK]="$SSH_AGENT_PID"
  elif (( agent_result > 2 )); then
    return "$agent_result"
  fi
  socket="$SSH_AUTH_SOCK"
  added="$(python3 "$script" "$action" "$@")"
  result=$?
  for public in "${(@f)added}"; do
    [[ -n "$public" ]] || continue
    _dotfiles_managed_keys[$socket]+="$public"$'\n'
  done
  (( result == 0 )) && print '연결 인증 준비 완료. 새로 로드한 키에는 설정한 TTL이 적용됩니다. 사용 후 bwe.'
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
  if [[ "${_dotfiles_vault_used:-0}" == 1 ]]; then
    command bw lock >/dev/null 2>&1 || failed=1
  fi
  unset BW_SESSION GH_TOKEN GITHUB_TOKEN GH_ENTERPRISE_TOKEN GITHUB_ENTERPRISE_TOKEN GITLAB_TOKEN GLAB_TOKEN GITLAB_ACCESS_TOKEN
  if (( failed )); then
    print -u2 'Session variables cleared, but some cleanup failed. Retry bwe; unreachable keys retain their TTL.'
  else
    print 'Session cleared. Managed SSH keys removed; existing agents/keys preserved.'
  fi
  return "$failed"
}
