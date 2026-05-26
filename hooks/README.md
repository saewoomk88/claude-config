# Claude Code Hooks

`~/.claude/settings.json`에 적용하는 훅 설정 모음. 비밀값은 포함하지 않는다.

## settings.hooks.json

### Stop 훅 — 응답 완료 알림
Claude Code가 응답을 마치면(`Stop` 이벤트):
- **현재 포커스된 앱이 Ghostty가 아닐 때만** 데스크탑 알림("응답이 완료되었습니다") + `Glass.aiff` 사운드 재생
- 이미 터미널(Ghostty)을 보고 있으면 알림을 띄우지 않음 → 자리 비웠을 때만 알려주는 용도

**의존성**: `terminal-notifier` (`brew install terminal-notifier`), macOS `afplay`, `lsappinfo`

## 적용 방법
`settings.hooks.json`의 `hooks` 키를 `~/.claude/settings.json`에 병합:

```bash
# 수동: ~/.claude/settings.json 의 최상위에 "hooks" 키를 복사
# 또는 jq로 병합 (기존 settings.json 백업 후):
jq -s '.[0] * .[1]' ~/.claude/settings.json hooks/settings.hooks.json > /tmp/merged.json \
  && mv /tmp/merged.json ~/.claude/settings.json
```
