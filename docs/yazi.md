# Yazi 설정

macOS에서 Yazi를 두 가지 방식으로 사용한다.

- Dock이나 Spotlight에서는 `Yazi.app`을 열어 Yazi 전용 Ghostty 창을 띄운다.
- 일반 Ghostty 셸에서는 `y`로 실행하고, 종료한 위치를 현재 zsh에 반영한다.

전용 앱은 Yazi를 macOS 네이티브 앱으로 다시 만드는 것이 아니다. 저장소의 작은
`Yazi.app` 실행기가 별도 Ghostty 인스턴스를 전용 설정으로 열고, Ghostty가 셸 대신
Yazi를 직접 실행하는 구조다.

```text
Dock / Spotlight
→ ~/Applications/Yazi.app
→ 별도 Ghostty 인스턴스
→ /opt/homebrew/bin/yazi
```

Finder의 기본 앱이나 일반 Ghostty 설정은 바꾸지 않는다.

## 왜 이렇게 구성하는가

Yazi는 터미널 사용자 인터페이스라 스스로 macOS 창, Dock 아이콘이나 Spotlight 진입점을
제공하지 않는다. Ghostty는 Yazi가 화면을 그릴 터미널을 제공하고, 얇은 `.app` 실행기는
macOS에서 그 전용 창을 앱처럼 시작할 진입점만 제공한다.

이 구성을 쓰면 다음이 분리된다.

- 평소 Ghostty: zsh와 기존 Ghostty 사용자 설정을 사용한다.
- Yazi 전용 창: 홈 디렉터리에서 Yazi를 바로 실행하고 `q`로 끝나면 창도 닫힌다.
- Yazi 앱 재실행: 이미 전용 창이 있으면 새로 만들지 않고 그 창을 앞으로 가져온다.
- 일반 셸의 `y`: 탐색을 끝낸 디렉터리로 현재 zsh를 이동한다.

## 관리하는 파일

| 저장소 파일 | 연결 위치 | 역할 |
|---|---|---|
| `links/apps/Yazi.app` | `~/Applications/Yazi.app` | macOS용 실행기와 Ghostty 전용 설정 |
| `links/yazi/yazi.toml` | `~/.config/yazi/yazi.toml` | 파일·폴더 opener |
| `links/yazi/keymap.toml` | `~/.config/yazi/keymap.toml` | `gi` 경로 이동 단축키 |
| `links/zsh/integrations/yazi.zsh` | zsh 시작 시 자동 로드 | 종료 위치로 `cd`하는 `y` 함수 |

Yazi의 기본 설정은 바이너리에 포함되어 있다. 사용자 설정 파일이 없는 것은 정상이며,
`~/.config/yazi/`에 만든 항목만 기본값 위에 적용한다. 이 저장소에서는 필요한 opener만
관리한다.

## 설치와 연결

전용 앱에는 Ghostty와 Yazi가 필요하다. Yazi 자체의 필수 보조 명령은 파일 형식을
판별하는 `file`이며 macOS에 기본으로 들어 있다. 미리보기와 검색 기능을 제대로 쓰려면
기능별 선택 의존성도 함께 설치한다.

공식 문서가 제시하는 Homebrew 전체 설치 명령은 다음과 같다.

```bash
brew update
brew install --cask ghostty
brew install yazi ffmpeg-full sevenzip jq poppler fd ripgrep fzf zoxide \
  resvg imagemagick-full font-symbols-only-nerd-font
brew link ffmpeg-full imagemagick-full -f --overwrite
```

`brew link` 명령은 일반 `ffmpeg`·ImageMagick 대신 `-full` 변형의 실행 파일을 PATH에
노출한다. 이미 원하는 실행 파일이 연결되어 있다면 다시 실행할 필요가 없다.

| 패키지 | Yazi에서 사용하는 기능 |
|---|---|
| `ffmpeg-full` | 동영상 썸네일 |
| `sevenzip` | 압축 파일 미리보기와 해제 |
| `jq` | JSON 미리보기 |
| `poppler` | PDF 미리보기 |
| `fd` | 파일 이름 검색 |
| `ripgrep` | 파일 내용 검색 |
| `fzf` | 빠른 하위 경로 탐색; 0.53.0 이상 |
| `zoxide` | 방문 기록 기반 디렉터리 이동; `fzf` 필요 |
| `resvg` | SVG 미리보기 |
| `imagemagick-full` | 폰트, HEIC와 JPEG XL 미리보기 |
| `font-symbols-only-nerd-font` | 파일 아이콘 표시; 권장 항목 |

모든 항목이 Yazi 실행 자체에 필수인 것은 아니다. 사용하지 않는 미리보기나 검색 기능의
패키지는 생략해도 된다. 패키지 목록과 최소 버전은
[Yazi 공식 Installation 문서](https://yazi-rs.github.io/docs/installation/)를 기준으로
하며, 특정 기능이 동작하지 않으면 먼저 해당 보조 도구가 최신 버전인지 확인한다.

설치 결과는 실제 실행 파일을 기준으로 점검한다.

```bash
command -v file yazi ffmpeg 7zz jq pdftoppm fd rg fzf zoxide resvg magick
```

dotfiles의 Yazi 설정과 앱을 홈 디렉터리에 연결한다.

```bash
./bin/bootstrap.sh
source ~/.zshrc
```

`bootstrap.sh`는 기존 `~/.config/yazi/yazi.toml`이 일반 파일이면
`.bak.<timestamp>` 이름으로 보관한 뒤 심볼릭 링크를 만든다. 앱은
`~/Applications/Yazi.app`에 연결한다.

## Yazi 전용 Ghostty 앱

앱 실행 파일은 먼저 실행 중인 Ghostty 프로세스 중 같은 전용 설정 파일을 사용하는
프로세스를 찾는다. 있으면 macOS의 `NSRunningApplication`으로 해당 PID를 활성화하고
끝난다. 없을 때만 다음 명령으로 새 인스턴스를 만든다.

```zsh
open -na Ghostty --args \
  --config-default-files=false \
  --config-file=/path/to/Yazi.app/Contents/Resources/ghostty.conf
```

- `-n`: 실행 중인 일반 Ghostty와 다른 인스턴스를 연다.
- `--config-default-files=false`: 일반 Ghostty 설정 파일을 읽지 않는다.
- `--config-file`: 앱 안의 Yazi 전용 설정만 추가로 읽는다.

따라서 처음 실행할 때는 일반 Ghostty와 분리된 Yazi 전용 인스턴스를 만들지만, Dock이나
Spotlight에서 다시 실행할 때는 그 인스턴스에 포커스만 옮긴다.

전용 설정은 다음과 같다.

```ini
command = direct:/opt/homebrew/bin/yazi
env = PATH=/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin
working-directory = home
title = Yazi
window-width = 140
window-height = 40
window-save-state = never
quit-after-last-window-closed = true
```

`command`가 로그인 셸 대신 Yazi를 직접 실행한다. `direct:`는 명령을 셸로 해석하지 않고
지정한 실행 파일을 바로 시작한다. Yazi가 `q`로 끝나면 마지막 전용 창이 닫히고 별도
Ghostty 인스턴스도 종료된다.

전용 앱은 zsh를 시작하지 않으므로 `~/.zprofile`의 `brew shellenv`도 실행하지 않는다.
따라서 `env`에 Homebrew 경로를 직접 넣어 Yazi가 `fzf`, `ffmpeg`와 `ffprobe` 같은
보조 명령을 찾게 한다. 패키지를 다시 설치하거나 일반 Ghostty의 PATH를 바꾸지는 않는다.

Ghostty의 설정 키와 CLI flag가 같은 이름을 사용한다는 점, `window-width`와
`window-height`를 함께 지정해야 한다는 점은
[Ghostty 설정 문서](https://ghostty.org/docs/config)와
[설정 옵션 레퍼런스](https://ghostty.org/docs/config/reference)를 기준으로 한다.

### Dock과 Spotlight에서 사용

연결 후 Finder의 `~/Applications`에서 `Yazi.app`을 한 번 열 수 있다. 앱이 보이면 Dock에
끌어다 놓거나 Spotlight에서 `Yazi`를 검색한다. LaunchServices 반영이 늦을 때는 다음
명령으로 다시 등록한다.

```bash
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
  -f ~/Applications/Yazi.app
```

이 앱은 Ghostty를 실행하는 얇은 진입점이므로 실제 터미널 창과 실행 중 표시에는 Ghostty가
나타날 수 있다. 일반 Ghostty 앱과 설정은 그대로 유지된다.

## 파일과 폴더 opener

실제 설정은 [`links/yazi/yazi.toml`](../links/yazi/yazi.toml)에 있다.

```toml
[opener]
chrome = [
  { run = 'open -a "Google Chrome" %s', orphan = true, desc = "Chrome", for = "macos" },
]
vscode = [
  { run = 'open -a "Visual Studio Code" %s', orphan = true, desc = "VS Code", for = "macos" },
]

[open]
prepend_rules = [
  { url = "*/",   use = [ "vscode", "open", "reveal" ] },
  { url = "*.md", use = [ "chrome", "edit", "reveal" ] },
]
```

규칙은 위에서부터 매칭되며 opener 배열의 첫 항목이 기본 동작이다.

- 폴더에서 `o` 또는 Enter: VS Code로 폴더를 연다.
- 폴더에서 `O` 또는 Shift-Enter: `VS Code`, `open`, `reveal` 중 고른다.
- Markdown에서 `o` 또는 Enter: Chrome으로 파일을 연다.
- Markdown에서 `O` 또는 Shift-Enter: `Chrome`, `edit`, `reveal` 중 고른다.

`%s`는 선택한 파일 경로로 바뀌고, `orphan = true`는 Yazi가 끝난 뒤에도 GUI 앱을
유지한다. `for = "macos"`는 이 opener를 macOS에서만 제공한다. `prepend_rules`는
Yazi의 내장 규칙을 없애지 않고 사용자 규칙을 앞에 추가한다. `url = "*/"`는 모든
폴더를, `url = "*.md"`는 Markdown 확장자를 매칭한다. 같은 방식으로 확장자별 규칙을
추가할 수 있다.

현재 문법은
[Yazi의 `yazi.toml` 문서](https://yazi-rs.github.io/docs/configuration/yazi/#opener)를
기준으로 한다. 설정을 바꾼 뒤에는 Yazi를 `q`로 끝내고 다시 실행한다.

## `gi`로 경로를 입력해 이동

[`links/yazi/keymap.toml`](../links/yazi/keymap.toml)은 다음 단축키를 기본 keymap보다
앞에 추가한다.

```toml
[mgr]
prepend_keymap = [
  { on = [ "g", "i" ], run = "cd --interactive", desc = "경로를 입력해 이동" },
]
```

Yazi에서 `g` 다음 `i`를 누르면 경로 입력창이 열린다. 절대 경로와 `~`로 시작하는
홈 상대 경로를 입력할 수 있고, 입력 중에는 경로 완성 후보가 표시된다. 별도 프로세스에
이벤트를 보내는 `ya emit`이나 `YAZI_ID`는 필요하지 않다.

`prepend_keymap`은 기본 단축키 전체를 대체하지 않고 `gi`만 높은 우선순위로 추가한다.
문법과 `cd --interactive` 동작은
[Yazi keymap 공식 문서](https://yazi-rs.github.io/docs/configuration/keymap/#mgr.cd)를
기준으로 한다. 현재 Yazi에는 비슷한 기본 단축키 `g` 다음 Space도 있지만, `gi`를
기억하기 쉬운 별칭으로 둔다.

## 일반 셸에서 사용하는 `y` 함수

전용 앱과 별개로 일반 셸에서도 Yazi를 쓸 수 있다. `y`는 임시 `--cwd-file`을 넘기고,
Yazi가 종료 위치를 기록하면 현재 zsh가 그 디렉터리로 이동한다.

```text
y [경로]
→ Yazi에서 탐색
→ q
→ 현재 zsh가 마지막 디렉터리로 이동
```

- `q`: 종료 위치를 기록하고 끝낸다.
- `Q`: 위치를 기록하지 않고 끝내므로 현재 셸 디렉터리를 유지한다.

이 패턴은
[Yazi Quick Start의 공식 shell wrapper](https://yazi-rs.github.io/docs/quick-start/#shell-wrapper)를
따른다.

## 점검

저장소가 제공하는 자동 검증:

```bash
./bin/verify.sh
```

개별 확인:

```bash
# 설치와 셸 함수
command -v ghostty
command -v yazi
type y

# 심볼릭 링크
readlink ~/Applications/Yazi.app
readlink ~/.config/yazi/yazi.toml
readlink ~/.config/yazi/keymap.toml

# 앱과 설정 문법
plutil -lint ~/Applications/Yazi.app/Contents/Info.plist
ghostty +validate-config \
  --config-file=~/Applications/Yazi.app/Contents/Resources/ghostty.conf

# Yazi가 사용자 설정을 읽는지 확인
yazi --debug 2>&1 | sed -n '/^Config/,+8p'
```

기능은 다음 순서로 확인한다.

1. Finder나 Spotlight에서 `Yazi.app`을 열었을 때 전용 Ghostty 창에 Yazi가 바로
   실행되는지 본다.
2. 다른 앱으로 포커스를 옮긴 뒤 `Yazi.app`을 다시 열어 새 창 대신 기존 창이 앞으로
   오는지 본다.
3. `q`로 종료했을 때 전용 창도 닫히는지 본다.
4. `gi`를 눌러 경로 입력창이 열리고, `~/work-vault`로 이동하는지 본다.
5. 폴더에서 `o`를 눌러 VS Code로 열리는지 본다.
6. Markdown 파일에서 `O`를 눌러 `Chrome`이 보이고, `o`로 Chrome에서 열리는지 본다.
7. 일반 셸에서는 `y`로 이동한 뒤 `q`로 끝내 `pwd`가 마지막 디렉터리인지 본다.

## Finder와 역할 분담

Yazi는 터미널 안의 파일 탐색, 이동, 복사, 이름 변경과 미리보기를 담당한다. Finder는
다른 앱의 열기·저장 대화상자, AirDrop, iCloud 상태, 태그, Spotlight와 드래그 앤
드롭 같은 macOS 통합에 계속 사용한다. Yazi에서 Finder가 필요하면 Markdown의 `O`
목록에 포함된 `reveal` opener를 선택한다.

## 롤백

대상이 이 저장소를 가리키는 심볼릭 링크인지 확인한 뒤 연결만 끊는다.

```bash
test -L ~/Applications/Yazi.app && unlink ~/Applications/Yazi.app
test -L ~/.config/yazi/yazi.toml && unlink ~/.config/yazi/yazi.toml
test -L ~/.config/yazi/keymap.toml && unlink ~/.config/yazi/keymap.toml
```

새 zsh를 열기 전 현재 셸에서 `y` 함수도 제거하려면 다음을 실행한다.

```zsh
unfunction y
```

Yazi 설정 링크가 없으면 Yazi는 내장 기본값으로 동작한다. `bootstrap.sh`가 기존 파일을
백업했다면 `~/.config/yazi/yazi.toml.bak.<timestamp>`를 원래 이름으로 복구할 수 있다.
