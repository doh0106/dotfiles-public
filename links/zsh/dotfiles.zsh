# Only explicitly selected integrations are loaded. Settings are generated locally.
_dotfiles_zsh_dir="${${(%):-%x}:A:h}"
typeset -a _dotfiles_enabled
_dotfiles_enabled=()
[[ -r "$HOME/.config/dotfiles/dashboard/enabled.zsh" ]] && source "$HOME/.config/dotfiles/dashboard/enabled.zsh"
typeset -U path
path=("$HOME/.local/bin" $path)
for _dotfiles_feature in "${_dotfiles_enabled[@]}"; do
  case "$_dotfiles_feature" in
    ohmyzsh|authentication|bitwarden|gh|glab|zoxide|zellij|yazi|nvm)
      source "$_dotfiles_zsh_dir/integrations/$_dotfiles_feature.zsh" ;;
    colors)
      source "$_dotfiles_zsh_dir/integrations/terminal-colors.zsh"
      source "$_dotfiles_zsh_dir/integrations/terminal-project-color.zsh" ;;
  esac
done
unset _dotfiles_feature _dotfiles_zsh_dir
