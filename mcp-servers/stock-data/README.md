# stock-data MCP Server

한국 (`pykrx`) + 미국 (`yfinance`) 주식 시세·재무·기술적 지표를 Claude Code에서 호출할 수 있는 MCP 서버.

## 도구 (Tools)

| 도구 | 설명 |
|---|---|
| `get_korean_stock(ticker, date?)` | 한국 종목 6자리 코드로 일봉 OHLCV + 시총 + 52주 고저 + 지표 (RSI/MACD/MA/Stoch/BB) |
| `get_us_stock(ticker, date?)` | 미국 종목 티커로 일봉 OHLCV + 시총 + PER + 52주 고저 + 지표 |
| `get_korean_index(index, date?)` | KOSPI / KOSDAQ / KOSPI200 지수 |
| `get_korean_investor_trading(ticker, date?)` | 외인/기관/개인 5일 순매수 (KRW) |
| `search_korean_ticker(name)` | 회사명으로 종목코드 검색 (KOSPI + KOSDAQ) |

## 설치

```bash
# Homebrew uv 필수
brew install uv

# 의존성 설치
cd ~/personal/claude-config/mcp-servers/stock-data
uv sync
```

## Claude Code 등록

```bash
claude mcp add stock-data --scope user -- \
  uv --directory /Users/woom/personal/claude-config/mcp-servers/stock-data \
  run python -m stock_data_mcp
```

확인:
```bash
claude mcp list   # stock-data: ✓ Connected
```

## 사용 예시

Claude Code 세션에서:
```
mcp__stock-data__get_korean_stock("020150")
# → 롯데에너지머티리얼즈 최신 OHLCV + RSI 49.17, MA20 66,710 등

mcp__stock-data__get_us_stock("NVDA")
# → NVDA 최신 OHLCV + 시총 $5.3T + RSI 57.76 등

mcp__stock-data__get_korean_index("KOSPI")
# → KOSPI 종가·등락
```

## 의존성

- Python 3.11–3.13 (pykrx가 3.14의 `pkg_resources` 제거에 미호환)
- `pykrx>=1.0.45` — KRX 공식 데이터 (일봉 30분~1시간 지연)
- `yfinance>=0.2.40` — Yahoo Finance 미국 주식
- `ta>=0.11.0` — 기술적 지표 (RSI/MACD/MA/Stoch/BB)
- `mcp[cli]>=1.2.0` — Anthropic MCP Python SDK (FastMCP)

## 알려진 제약

- pykrx KRX 백엔드가 가끔 빈 응답 → `get_korean_index` / `get_korean_investor_trading` 일시 실패. 재시도 시 통과.
- yfinance는 yfinance 자체 rate limit 외 무료/무제한.
- 실시간 호가는 미지원 (KIS Developers OpenAPI 필요).

## 🆕 재무 심층 + DCF 밸류에이션 도구 (v2)

### `get_us_financials(ticker)`
미국 종목 펀더멘털 심층 데이터 (yfinance):
- 5년 추세: 매출·EBIT·순이익·EPS·FCF·영업현금흐름·CapEx
- 수익성: 매출총이익률·영업이익률·순이익률·ROE·ROA·**ROIC(근사)**
- 건전성: 총부채·현금·순부채·부채비율·유동비율
- 밸류에이션: PER·선행PER·PBR·EV/EBITDA·PEG·배당수익률
- `dcf_inputs`: latest/3년평균 FCF·발행주식수·순부채·베타·현재가 (DCF 바로 투입)

### `dcf_valuation(ticker=..., growth_rate=..., ...)`
2단계 DCF 1주당 내재가치 계산:
- 티커만 주면 base_fcf(3년평균)·주식수·순부채·**CAPM 할인율(rf 4.2%+β×5%)** 자동
- 반환: 내재가치/주, EV·equity 분해, **민감도 그리드**(할인율±1%×성장±2%), 현재가 대비 상승여력%
- 가드: 음수 FCF·할인율≤영구성장 차단
- ⚠️ 고베타 성장주는 보수적으로 산출됨 → 할인율/성장률 직접 조정 권장

**예시**:
```python
dcf_valuation(ticker="AAPL")                          # 전자동
dcf_valuation(ticker="NVDA", growth_rate=0.25, discount_rate=0.10)  # 가정 조정
dcf_valuation(base_fcf=5e12, shares_outstanding=7e8, net_debt=-1e12)  # 국장 수동
```

