# 도구별 설정은 integrations/에서 소유하고 이 파일은 로드 순서만 담당한다.
_dotfiles_zsh_dir="${${(%):-%x}:A:h}"

# 사용자 설치 명령의 공용 진입점. 중복 항목은 zsh가 제거한다.
typeset -U path
path=("$HOME/.local/bin" $path)

for _dotfiles_integration in "$_dotfiles_zsh_dir"/integrations/*.zsh(N); do
  source "$_dotfiles_integration"
done

unset _dotfiles_integration _dotfiles_zsh_dir
