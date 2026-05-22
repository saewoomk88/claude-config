---
name: stock-news
description: 주식 관련 뉴스를 빠르게 모아서 정리합니다. 국장·미장 시장 종합 뉴스(Daily Brief), 특정 종목 뉴스, 섹터별 동향(반도체·이차전지·바이오 등), 테마/키워드별 뉴스(HBM·AI·양자컴퓨팅 등) 4가지 모드 지원. 사용자가 "오늘 뉴스 정리", "장 마감 정리", "주식 뉴스 모아줘", "삼성전자 뉴스", "반도체 동향", "HBM 뉴스" 같이 뉴스 수집·정리·브리핑을 요청할 때 사용. 종목 분석/리서치 요청은 [[stock-analyst]] 스킬 사용.
---

# Stock News — 주식 뉴스 빠른 정리

다양한 출처의 뉴스를 **병렬 수집 → 중복 제거 → 영향 종목 태깅 → 구조화 요약**으로 빠르게 정리한다.

## 모드 4가지

| 모드 | 트리거 예시 | 출력 범위 |
|---|---|---|
| **Daily Brief** | "오늘 뉴스", "장 마감 정리", "시장 뉴스" | 한·미 시장 종합 + Top 이슈 + 매크로 |
| **종목별** | "삼성전자 뉴스", "NVDA 뉴스" | 특정 종목 관련 뉴스만 |
| **섹터별** | "반도체 뉴스", "이차전지 동향", "바이오 뉴스" | 섹터 내 주요 뉴스 + 대장주 영향 |
| **테마/키워드** | "HBM 뉴스", "양자컴퓨팅", "AI 칩" | 키워드 중심 + 관련 종목 자동 매핑 |

## 🆕 MCP 우선 사용 (stock-data 서버)

`stock-data` MCP 서버가 등록되어 있다면 **시세 데이터는 MCP를 먼저 사용한다** (WebSearch보다 빠르고 정확).

| 데이터 | MCP 도구 | 대체 (MCP 미가용 시) |
|---|---|---|
| 한국 종목 OHLCV + 지표 | `mcp__stock-data__get_korean_stock("005930")` | WebSearch + WebFetch |
| 미국 종목 OHLCV + 지표 | `mcp__stock-data__get_us_stock("NVDA")` | WebSearch + WebFetch |
| KOSPI/KOSDAQ 지수 | `mcp__stock-data__get_korean_index("KOSPI")` | WebSearch |
| 외인/기관/개인 수급 | `mcp__stock-data__get_korean_investor_trading("005930")` | WebSearch |
| 종목 검색 | `mcp__stock-data__search_korean_ticker("삼성")` | WebSearch |

**Daily Brief 시 권장 호출 순서**:
1. MCP `get_korean_index` → KOSPI / KOSDAQ 종가·등락
2. MCP `get_korean_stock` → 삼성전자(005930) / SK하이닉스(000660) / 기타 주도주
3. MCP `get_us_stock` → S&P 500(^GSPC) / NASDAQ(^IXIC) / DOW(^DJI) / NVDA 등
4. MCP `get_korean_investor_trading` → 주요 종목 수급
5. WebSearch — 뉴스 헤드라인·정성 정보만 수집 (시세는 MCP에서 이미 확보)

> 💡 뉴스 헤드라인 매체 검색(언제·왜·어떻게)은 여전히 WebSearch가 더 효율적. 숫자(가격·등락·RSI·MA)는 MCP가 정확.

## 워크플로우

### 1. 모드 판별 및 시간 범위 결정

- 모드 판별: 사용자 입력에서 종목명/티커/섹터명/테마 키워드 추출 → 위 표에 매핑
- 시간 범위 기본값:
  - Daily Brief: **최근 24시간** (장 마감 시점이면 당일 + 전일 야간)
  - 종목/섹터/테마: **최근 7일** (특별 지정 없으면)
- 사용자가 "이번 주", "최근 한 달" 같이 명시하면 그 범위 사용

### 2. 데이터 수집 (병렬 실행 필수)

**한국 뉴스 (WebSearch 우선 — 다양한 소스 한 번에)**
- `WebSearch` → `{키워드} 뉴스 {YYYY년 M월 D일}` (날짜 명시 필수)
- `WebSearch` → `{키워드} site:hankyung.com` (한국경제)
- `WebSearch` → `{키워드} site:mk.co.kr` (매일경제)
- `WebSearch` → `{키워드} site:edaily.co.kr` (이데일리)
- `WebSearch` → `{키워드} site:biz.chosun.com` (조선비즈)
- `WebSearch` → `{키워드} site:news.einfomax.co.kr` (인포맥스 — 시장 데이터 강함)

**미국/글로벌 뉴스**
- `WebSearch` → `{keyword} news {month} {year}` (영문 + 연·월)
- `WebSearch` → `{keyword} site:bloomberg.com`
- `WebSearch` → `{keyword} site:reuters.com`
- `WebSearch` → `{keyword} site:cnbc.com`
- `WebSearch` → `{keyword} site:marketwatch.com`
- `WebSearch` → `{ticker} site:seekingalpha.com` (종목별)

**Daily Brief 전용 — 시장 종합**
- `WebSearch` → `KOSPI 마감 {YYYY년 M월 D일}` / `KOSDAQ 마감 {YYYY년 M월 D일}`
- `WebSearch` → `Wall Street close {date}` / `S&P 500 NASDAQ close {date}`
- `WebSearch` → `달러 원 환율 {날짜}` / `미국 10년물 국채금리 {날짜}`
- `WebSearch` → `오늘 뉴욕증시 마감 {YYYY년 M월 D일}`

**기사 전문 필요 시 WebFetch**
- 헤드라인만으로 의미 파악 어려운 경우만 선별적으로 WebFetch
- 헤드라인 기반 요약으로 충분하면 fetch 생략 (속도 우선)

> 💡 **속도 최적화**: 한 모드당 WebSearch 4-6개를 **단일 메시지에서 병렬 호출**. 절대 순차 호출 X.

### 3. 중복 제거 및 영향 종목 태깅

- 같은 사건을 다른 매체가 보도한 경우 **1개로 통합** (가장 정보량 많은 헤드라인 선택)
- 각 뉴스 항목마다 영향받는 종목/티커 자동 태깅:
  - 명시적 종목 언급: 직접 인용
  - 섹터 뉴스: 대장주 1-3개 매핑 (반도체→삼성전자/SK하이닉스/엔비디아 등)
  - 테마 뉴스: 테마 대표 종목 매핑

### 4. 리포트 구성

#### Daily Brief 포맷
```markdown
# 📰 {YYYY-MM-DD} 주식 뉴스 브리핑
*생성: {timestamp} · 범위: 최근 24시간*

## 🌐 시장 한 줄 요약
- **KOSPI**: {지수} ({등락}) · 주도 섹터: {섹터}
- **KOSDAQ**: {지수} ({등락})
- **S&P 500**: {지수} ({등락})
- **NASDAQ**: {지수} ({등락})
- **USD/KRW**: {환율} · 미국채 10Y: {금리}

## 🔥 Top 핵심 이슈
1. **{헤드라인 한 줄}** _{날짜}_
   - 핵심 요약 (1-2줄)
   - 📌 관련 종목: {티커1}, {티커2}
   - [출처](URL)
2. ...
(최대 5-7개)

## 📊 섹터별 동향
### 반도체
- 핵심 뉴스 2-3개
### 이차전지
- ...
### 바이오/제약
- ...

## 🌎 매크로 & 글로벌
- 🇺🇸 미국: 금리/지표/연준 발언 등
- 🇨🇳 중국: 정책/지표
- 🇰🇷 한국: 정책/지표
- 🛢️ 원자재/환율: 유가, 금, 환율

## 📅 곧 다가올 주요 이벤트 (선택)
- {날짜}: {이벤트} (예: NVDA 실적, FOMC, CPI 발표)
```

#### 종목별 포맷
```markdown
# 📰 {회사명} ({티커}) 뉴스
*생성: {timestamp} · 범위: {기간}*

## 📌 핵심 이슈 한눈에
- 가장 중요한 흐름 한 줄 (예: "HBM 수주 호재 + 노조 파업 우려 혼재")

## 🔥 주요 뉴스 ({개수}건)
1. **{헤드라인}** _{날짜}_
   - 요약
   - 📈/📉 주가 영향 (가능 시): 발표 후 {±%}
   - [출처](URL)
(중요도 순으로 5-10개)

## 🔗 관련 이슈 (있을 시)
- 경쟁사 동향, 섹터 이슈, 정책 변화 등

## 📅 예정 이벤트
- 다음 실적 발표일, 주총, 컨퍼런스 등
```

#### 섹터/테마 포맷
```markdown
# 📰 {섹터/테마} 동향
*생성: {timestamp} · 범위: {기간}*

## 🌐 한 줄 요약
- 섹터 전반 흐름 (강세/약세, 주도 이슈)

## 🔥 주요 뉴스
(헤드라인 + 요약 + 관련 종목, 5-7개)

## 🏆 대장주 동향
| 종목 | 최근 흐름 | 주요 이슈 |
|---|---|---|
| ... | ... | ... |

## 📊 글로벌 비교 (해당 시)
- 한국 vs 미국 vs 중국 동향
```

### 5. 면책 문구 (필수)
모든 리포트 마지막에:
> ⚠️ 본 뉴스 정리는 공개 정보의 요약이며, **투자 권유나 매매 추천이 아닙니다.** 기사 원문 확인 및 투자 판단의 책임은 투자자 본인에게 있습니다.

### 6. 리포트 자동 저장 + Git 커밋 + Push

`~/personal/stock/news/` 디렉토리가 존재하면, **리포트 출력 후 자동으로 저장 + git commit + push까지 진행한다**.

**파일명 규칙**:
- Daily Brief: `YYYY-MM-DD_daily-brief.md`
- 종목별: `YYYY-MM-DD_news_{티커}_{영문회사명}.md`
- 섹터별: `YYYY-MM-DD_news_sector_{섹터명}.md`
- 테마별: `YYYY-MM-DD_news_theme_{테마키워드}.md`
- 같은 날 동일 파일 있으면 `_v2`, `_v3` 추가

**자동 실행 흐름** (리포트 출력 직후):
1. 파일 저장: `~/personal/stock/news/{파일명}.md`
2. Git commit: `cd ~/personal/stock && git add news/ && git commit -m "Add {타입} {날짜}"`
3. Git push: `git push`
4. **노션 업로드**: `python3 ~/personal/claude-config/scripts/upload_notion.py ~/personal/stock/news/{파일명}.md`
   - 스크립트가 `~/personal/claude-config/.env` 에서 자동으로 NOTION_TOKEN 로드
   - 본문 마크다운 → 노션 블록 자동 변환 + 메타데이터 자동 추출
5. 사용자에게 결과 짧게 알림: 파일 경로 + commit hash + GitHub URL + **Notion URL**

**자동 저장을 건너뛰는 경우**:
- 사용자가 "저장하지마", "저장 X", "임시", "테스트", "don't save" 등 명시적 거부
- 사용자가 가벼운 톤 ("그냥 궁금해서", "한번 보고 싶어")로 요청
- 단순 질문/답변 형태로 정형 리포트가 생성되지 않은 경우

## 출력 규칙

- **시간성 우선**: 최신 뉴스가 위에 (시간 역순 정렬)
- **출처 명시**: 모든 뉴스에 [매체명](URL) 링크 필수
- **헤드라인 그대로 인용 X**: 한국어로 의미 압축 (영문 기사도 한국어 요약 — 사용자 한국어 사용 시)
- **숫자 보존**: 매출, 영업이익, 주가 등락률 등 숫자는 정확히 인용
- **추측 금지**: 기사에 없는 내용 추가 X. 영향 분석은 "기사 인용" 명시
- **속보 표시**: 24시간 이내 핵심 뉴스에는 🚨 또는 _NEW_ 표시

## 주의사항

- **뉴스는 시점 데이터**: 검색 시점 이후 새 뉴스 누락 가능 → "이 시점 기준" 명시
- **언론사 편향 인식**: 같은 사건이라도 매체별 톤 다름 → 가능하면 복수 출처 교차
- **루머/미확인 정보 구분**: "보도", "분석", "전망"인지 명확히 구분
- **종목 영향 추정 신중**: "이 뉴스로 주가 OO% 갈 것" 같은 단정적 표현 X
- **언어**: 사용자 입력 언어 따름 (한국어 → 한국어 요약, 영어 → 영어 요약)

## 알려진 도메인 차단/이슈

WebFetch가 작동하지 않는 도메인 — 처음부터 우회 방법을 사용한다.

### 🚫 명시적 차단 (403 Forbidden 반환)

| 도메인 | 용도 | 대체 방법 |
|---|---|---|
| `bloomberg.com` | 글로벌 시장 뉴스, 매크로 | `WebSearch site:bloomberg.com` → 헤드라인+요약 수집 (본문 X) |
| `*.naver.com` 계열 | 한국 뉴스 | WebSearch만 사용 / 원본 매체 직접 (한경·매경 등) |
| `finance.naver.com` | 국내 시세/리서치 | WebSearch만 (한경 컨센서스·FnGuide로 보완) |

### 📱 SPA (JS 렌더링 필요 — WebFetch는 빈 콘텐츠 반환)

| 도메인 | 용도 | 대체 방법 |
|---|---|---|
| `saveticker.com` | 미장 뉴스 (오선/SAVE 앱) | 사용자가 모바일 앱 SAVE로 직접 보거나, 아래 미장 대체 사이트 활용 |

> 💡 SPA 사이트는 `WebFetch`가 200 OK를 반환해도 본문은 비어있음 — HTTP 응답만 보고 성공으로 착각하지 말 것.

### ✅ 권장 우회 출처

**미장 뉴스 (WebFetch 잘 됨)**
- `kr.investing.com/news/stock-market-news` (한국어, 미장+글로벌)
- `finance.yahoo.com/news` (영문, 가장 빠른 미장 뉴스)
- `cnbc.com/world/?region=world` (영문 시황)
- `marketwatch.com/latest-news` (영문, 종목 태그 좋음)
- `m.finance.daum.net/global` (한국어 간단 요약)

**한국 뉴스 (WebFetch 잘 됨)**
- `hankyung.com` (한국경제)
- `mk.co.kr` (매일경제)
- `edaily.co.kr` (이데일리)
- `biz.chosun.com` (조선비즈)
- `news.einfomax.co.kr` (인포맥스 - 시장 데이터 강점)

> 새로운 차단/SPA 도메인을 발견하면 위 표에 추가하고 대체재를 기록할 것.

## 확장 옵션 (요청 시)

- **이메일 다이제스트 포맷**: 메일로 보낼 수 있는 깔끔한 텍스트 버전
- **모바일 푸시 포맷**: 짧은 알림 스타일 (한 줄 헤드라인 + 종목 태그)
- **포트폴리오 종목 추적**: 사용자가 보유 종목 리스트 제공 시 → 보유 종목만 필터링
- **감성 분석**: 호재/악재/중립 라벨링 (보수적으로 사용)
- **시계열 비교**: 동일 종목/섹터 일주일 전 vs 오늘 흐름 변화

## 관련 스킬

- 종목 심층 분석: [[stock-analyst]] (재무·차트·컨센서스·동종업계 비교)
- 본 스킬은 뉴스 수집·정리에 특화, 분석은 stock-analyst가 담당
