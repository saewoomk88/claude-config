# claude-config

Claude Code 개인 설정 (스킬·에이전트·세팅) 저장소.

## 구조

```
claude-config/
└── skills/              # Claude Code 사용자 스킬
    └── stock-analyst/   # 국내·해외 주식 분석 스킬
```

> 📦 **분석 리포트는 별도 레포**: [~/personal/stock](https://github.com/saewoomk88/stock) ← 푸시 후 링크 갱신

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

### 2. 스킬 수정 후 동기화

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
| [stock-analyst](skills/stock-analyst/SKILL.md) | 국장·미장 종목 7섹션 종합 분석. 생성된 리포트는 별도 `~/personal/stock/reports/`에 저장 |

## 관련 레포

- **[stock](https://github.com/saewoomk88/stock)**: 분석 리포트 저장소 — stock-analyst 스킬로 생성한 리포트들이 저장됨
