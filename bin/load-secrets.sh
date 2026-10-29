#!/usr/bin/env bash
# Source from bash/zsh so eval-env can modify the caller's environment.
if [ -n "${BASH_VERSION:-}" ] && [ "${BASH_SOURCE[0]}" = "$0" ]; then
  echo 'Source this file from bash/zsh, or run bws in zsh.' >&2
  exit 2
fi
_dotfiles_load_secrets() {
  local manifest="${1:-${DOTFILES_SECRETS_MANIFEST:-}}" cmd count item name kind field action dest mode value key line invalid failures=0 tmp parent
  if [ -z "$manifest" ]; then
    echo 'Pass the secrets.json path (normally use bws).' >&2; return 2
  fi
  for cmd in bw jq ssh-add; do
    command -v "$cmd" >/dev/null 2>&1 || { echo "Missing: $cmd" >&2; return 1; }
  done
  # Validate the entire manifest before fetching any value.
  jq -e '
    .secrets | type == "array" and all(.[];
      (.bw_name | type == "string" and length > 0) and
      (.bw_type == "sshkey" or .bw_type == "note" or .bw_type == "login") and
      ((.field // "private") == "private" or .field == "public") and
      (.action == "ssh-add" or .action == "write-file" or .action == "eval-env") and
      (if .action == "write-file" then
        (.dest | type == "string" and length > 0) and
        ((.mode // "600") | test("^0?[0-7]{3}$"))
       else true end))' "$manifest" >/dev/null || { echo 'Invalid secret manifest.' >&2; return 1; }
  [ "$(bw status | jq -r '.status')" = unlocked ] || { echo 'Run bwu first.' >&2; return 1; }
  bw sync >/dev/null || return 1
  while IFS= read -r item; do
    name=$(printf '%s' "$item" | jq -r '.bw_name')
    kind=$(printf '%s' "$item" | jq -r '.bw_type')
    field=$(printf '%s' "$item" | jq -r '.field // "private"')
    action=$(printf '%s' "$item" | jq -r '.action')
    value=''
    case "$kind" in
      sshkey)
        value=$(bw get item "$name") || { failures=$((failures+1)); continue; }
        if [ "$field" = public ]; then key=publicKey; else key=privateKey; fi
        value=$(printf '%s' "$value" | jq -er --arg key "$key" '.sshKey[$key] | select(type == "string" and length > 0)') || {
          unset value; failures=$((failures+1)); continue;
        } ;;
      note) value=$(bw get notes "$name") || { failures=$((failures+1)); continue; } ;;
      login) value=$(bw get password "$name") || { failures=$((failures+1)); continue; } ;;
    esac
    [ -n "$value" ] || { echo "Empty secret: $name" >&2; failures=$((failures+1)); continue; }
    case "$action" in
      ssh-add)
        printf '%s\n' "$value" | ssh-add - >/dev/null 2>&1 || { failures=$((failures+1)); unset value; continue; } ;;
      write-file)
        dest=$(printf '%s' "$item" | jq -r '.dest')
        mode=$(printf '%s' "$item" | jq -r '.mode // "600"')
        case "$dest" in '~/'*) dest="$HOME/${dest#\~/}" ;; esac
        parent=$(dirname "$dest")
        mkdir -p "$parent" || { failures=$((failures+1)); unset value; continue; }
        tmp=$(umask 077; mktemp "$parent/.dotfiles-secret.XXXXXX") || { failures=$((failures+1)); unset value; continue; }
        if ! (printf '%s\n' "$value" > "$tmp" && chmod "$mode" "$tmp" && mv -f "$tmp" "$dest"); then
          rm -f "$tmp"; failures=$((failures+1)); unset value; continue
        fi ;;
      eval-env)
        # First validate every line so a malformed bundle exports nothing.
        invalid=0
        while IFS= read -r line || [ -n "$line" ]; do
          case "$line" in ''|\#*) continue ;; esac
          key=${line%%=*}
          if [ "$key" = "$line" ] || ! printf '%s' "$key" | LC_ALL=C grep -Eq '^[A-Za-z_][A-Za-z0-9_]*$'; then
            invalid=1
          fi
        done <<ENV
$value
ENV
        [ "$invalid" -eq 0 ] || { echo "Invalid env bundle: $name" >&2; failures=$((failures+1)); unset value; continue; }
        while IFS= read -r line || [ -n "$line" ]; do
          case "$line" in ''|\#*) continue ;; esac
          export "$line"
        done <<ENV
$value
ENV
        ;;
    esac
    unset value
    echo "Loaded: $name"
  done < <(jq -c '.secrets[]' "$manifest")
  unset value
  [ "$failures" -eq 0 ] || { echo "Secret loading failed: $failures item(s)." >&2; return 1; }
}
_dotfiles_load_secrets "$@"
