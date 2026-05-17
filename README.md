# claude-config

Claude Code 개인 설정 저장소 — 스킬과 분석 리포트를 함께 관리합니다.

## 구조

```
claude-config/
├── skills/              # Claude Code 사용자 스킬
│   └── stock-analyst/   # 국내·해외 주식 분석 스킬
└── reports/             # 스킬로 생성한 분석 리포트
    └── YYYY-MM-DD_{티커}_{회사명}.md
```

## 사용 방법

### 1. 다른 컴퓨터에 셋업

```bash
# 1) 레포 클론
git clone {레포-URL} ~/personal/claude-config

# 2) skills 디렉토리를 ~/.claude/skills/로 심볼릭 링크
# (기존 ~/.claude/skills 가 있다면 백업 후 진행)
mv ~/.claude/skills ~/.claude/skills.bak 2>/dev/null
ln -s ~/personal/claude-config/skills ~/.claude/skills
```

### 2. 새 분석 리포트 작성 후 커밋

Claude Code 세션에서 종목 분석을 받은 뒤:

```bash
cd ~/personal/claude-config
git add reports/
git commit -m "Add {종목명} analysis"
git push
```

### 3. 스킬 수정 후 동기화

스킬 내용 수정 후:

```bash
cd ~/personal/claude-config
git add skills/
git commit -m "Update stock-analyst skill"
git push

# 다른 컴퓨터에서
cd ~/personal/claude-config && git pull
```

## 스킬 목록

| 스킬 | 설명 |
|---|---|
| [stock-analyst](skills/stock-analyst/SKILL.md) | 국장·미장 종목 7섹션 종합 분석 (회사 개요·재무·컨센서스·차트·동종업계 비교·뉴스·종합 의견) |

## 리포트 작성 규칙

- 파일명: `reports/YYYY-MM-DD_{종목코드or티커}_{회사명}.md`
  - 예: `reports/2026-05-16_000660_skhynix.md`
  - 예: `reports/2026-05-16_NVDA_nvidia.md`
- 동일 종목 재분석 시 새 파일로 추가 (덮어쓰기 X) → 시계열 추적 가능
- 모든 리포트는 마지막에 면책 문구 필수

## 주의사항

⚠️ 본 레포의 분석 리포트는 공개 정보 기반 참고 자료이며, **투자 권유나 매매 추천이 아닙니다.** 모든 투자 결정과 결과의 책임은 투자자 본인에게 있습니다.

⚠️ 본인의 매매 단가·포지션·전략 등 민감 정보가 포함될 경우 **private repo로 운영**하세요.
