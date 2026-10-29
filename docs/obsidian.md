# Obsidian 빠른 Inbox 기록

## 왜 쓰는가

업무 중 떠오른 질문, 확인할 일, 전달받은 문장을 기록하려고 현재 앱을 벗어나 Obsidian을
열고 날짜별 파일을 찾으면 생각의 흐름이 끊긴다. 이 구성은 어느 앱에서든 `⌃⇧O`를 눌러
입력창만 띄우고, 내용을 오늘의 inbox에 시간과 함께 저장한다.

기록할 때는 분류할 위치나 노트 제목을 정하지 않는다. 먼저 하나의 날짜별 inbox에 모은 뒤
나중에 정리함으로써 캡처 단계의 마찰을 줄이는 것이 목적이다.

```text
⌃⇧O
→ macOS Shortcuts의 Open URLs
→ obsidian://quickadd URI
→ work-vault의 QuickAdd Inbox choice
→ inbox/YYYY-MM-DD.md
```

## 현재 구성

- vault: `~/work-vault`
- macOS 단축어 이름: `Open URLs`
- 전역 키보드 단축키: `⌃⇧O`
- URI: `obsidian://quickadd?vault=work-vault&choice=Inbox`
- QuickAdd choice: `Inbox` (`Capture`)
- 대상 파일: `inbox/{{DATE:}}.md`
- 파일이 없으면 자동 생성
- 입력 형식:

  ```markdown
  ## {{DATE:HH:mm}}
  {{VALUE:entry}}
  ```

결과는 날짜별 파일에 아래처럼 시간순으로 쌓인다.

```markdown
## 17:10
확인할 내용
```

## macOS Shortcuts와 연결

Obsidian을 한 번 실행해 `obsidian://` URI를 macOS에 등록하고, vault에서 QuickAdd를
설치·활성화한다. QuickAdd에 위의 `Inbox` Capture choice를 만든 뒤 URI부터 직접 시험한다.

```bash
open 'obsidian://quickadd?vault=work-vault&choice=Inbox'
```

입력창이 열리고 내용이 날짜별 inbox에 저장되면 Shortcuts 앱에서 다음과 같이 연결한다.

1. `URL` action에 위 URI를 넣는다.
2. 그 URL을 `Open URLs` action으로 연다.
3. shortcut의 Details에서 `Add Keyboard Shortcut`을 선택한다.
4. `⌃⇧O`를 지정한다.

QuickAdd는 `obsidian://quickadd` URI로 외부 앱에서 choice를 실행할 수 있으며, `vault`와
`choice`가 각각 대상 vault와 choice를 선택한다. 자세한 형식은
[QuickAdd의 URI 문서](https://quickadd.obsidian.guide/docs/Advanced/ObsidianUri/)를 참고한다.

현재 Mac에서 shortcut과 로컬 키 등록 여부는 다음처럼 확인한다.

```bash
shortcuts list --show-identifiers | grep '^Open URLs '
defaults read pbs NSServicesStatus
```

두 번째 출력에서 `runShortcutAsService` 항목의 `key_equivalent`가 `^$O`이면
Control-Shift-O가 등록된 상태다. 이 값은 shortcut UUID를 참조하므로 다른 Mac에 plist
내용을 그대로 복사하지 않는다.

## 동기화와 새 Mac 복구

Shortcuts 앱의 **Settings → General → iCloud Sync**를 켠다. 설정이 켜졌다는 사실만으로
업로드 완료를 확정할 수는 없으므로, 같은 Apple ID를 사용하는 다른 기기에서 `Open URLs`가
보이는지 확인하는 것이 가장 확실하다. 다른 Mac에서는 shortcut이 보이더라도 `⌃⇧O`가 실제로
동작하는지 별도로 시험한다.

Obsidian 쪽 실제 설정은 **Settings → Sync → Vault configuration sync**로 동기화한다.
QuickAdd 설정은 vault의 `.obsidian/plugins/quickadd/data.json`에 들어간다. 새 기기에서는
QuickAdd 플러그인도 설치·활성화해야 하며, 설정 파일이 동기화된 뒤 Obsidian을 다시 시작하거나
플러그인을 껐다 켜야 한다. 자세한 내용은
[QuickAdd 동기화 안내](https://quickadd.obsidian.guide/docs/FAQ/#syncing-quickadd-between-devices)를
참고한다.

## 이 저장소에 두는 범위

현재 구성은 이 문서로만 관리한다. QuickAdd의 `data.json`은 기본값, 버전별 migration,
AI provider 설정까지 함께 들어가 변경 잡음이 크고, `workspace.json`은 열린 탭과 최근
파일에 따라 계속 바뀌기 때문이다.

나중에 Capture choice가 여러 개로 늘어나거나 별도 템플릿·스크립트를 사용하면 재현에 필요한
템플릿과 스크립트만 선별해 버전 관리한다. `workspace.json`, 최근 파일 목록, API key와 token은
커밋하지 않는다.
