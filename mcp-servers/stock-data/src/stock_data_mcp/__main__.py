"""Stock Data MCP Server — Korean (pykrx) + US (yfinance) + technical indicators."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import yfinance as yf
from mcp.server.fastmcp import FastMCP
from pykrx import stock as krx
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, SMAIndicator
from ta.volatility import BollingerBands

mcp = FastMCP("stock-data")


def _today() -> str:
    return datetime.now().strftime("%Y%m%d")


def _days_ago(n: int) -> str:
    return (datetime.now() - timedelta(days=n)).strftime("%Y%m%d")


def _fmt(d: str) -> str:
    """YYYYMMDD → YYYY-MM-DD"""
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def _indicators(close: pd.Series, high: pd.Series, low: pd.Series) -> dict[str, Any]:
    """Compute RSI/MACD/MA/Stochastic/Bollinger from price series."""
    out: dict[str, Any] = {}
    try:
        out["rsi_14"] = round(float(RSIIndicator(close, window=14).rsi().iloc[-1]), 2)
    except Exception:
        out["rsi_14"] = None
    try:
        macd = MACD(close)
        out["macd"] = round(float(macd.macd().iloc[-1]), 2)
        out["macd_signal"] = round(float(macd.macd_signal().iloc[-1]), 2)
        out["macd_diff"] = round(float(macd.macd_diff().iloc[-1]), 2)
    except Exception:
        out["macd"] = out["macd_signal"] = out["macd_diff"] = None
    for w in (5, 20, 60, 120, 200):
        try:
            out[f"ma_{w}"] = round(float(SMAIndicator(close, window=w).sma_indicator().iloc[-1]), 2)
        except Exception:
            out[f"ma_{w}"] = None
    try:
        stoch = StochasticOscillator(high, low, close)
        out["stoch_k"] = round(float(stoch.stoch().iloc[-1]), 2)
        out["stoch_d"] = round(float(stoch.stoch_signal().iloc[-1]), 2)
    except Exception:
        out["stoch_k"] = out["stoch_d"] = None
    try:
        bb = BollingerBands(close)
        out["bb_upper"] = round(float(bb.bollinger_hband().iloc[-1]), 2)
        out["bb_middle"] = round(float(bb.bollinger_mavg().iloc[-1]), 2)
        out["bb_lower"] = round(float(bb.bollinger_lband().iloc[-1]), 2)
    except Exception:
        out["bb_upper"] = out["bb_middle"] = out["bb_lower"] = None
    return out


@mcp.tool()
def get_korean_stock(ticker: str, date: str | None = None) -> dict[str, Any]:
    """Get Korean stock daily OHLCV + indicators (KOSPI/KOSDAQ).

    Args:
        ticker: 6-digit Korean stock code (e.g., "005930" for Samsung, "020150" for Lotte Energy Materials)
        date: Date in YYYY-MM-DD format. Defaults to most recent trading day.

    Returns:
        dict with: ticker, name, date, open, high, low, close, volume, change_pct,
                   week52_high, week52_low, market_cap, indicators (RSI, MACD, MAs, Stoch, BB).
    """
    end_date = date.replace("-", "") if date else _today()
    start_date = _days_ago(365)

    df = krx.get_market_ohlcv(start_date, end_date, ticker)
    if df.empty:
        return {"error": f"No data for ticker {ticker} (KRX)"}

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last
    change_pct = round((last["종가"] - prev["종가"]) / prev["종가"] * 100, 2)

    try:
        name = krx.get_market_ticker_name(ticker)
    except Exception:
        name = "Unknown"

    try:
        cap_df = krx.get_market_cap(end_date, end_date, ticker)
        market_cap = int(cap_df.iloc[-1]["시가총액"]) if not cap_df.empty else None
    except Exception:
        market_cap = None

    week52 = df.tail(252) if len(df) >= 252 else df
    inds = _indicators(df["종가"], df["고가"], df["저가"])

    return {
        "ticker": ticker,
        "name": name,
        "market": "KRX",
        "date": _fmt(df.index[-1].strftime("%Y%m%d")),
        "open": int(last["시가"]),
        "high": int(last["고가"]),
        "low": int(last["저가"]),
        "close": int(last["종가"]),
        "volume": int(last["거래량"]),
        "change_pct": change_pct,
        "week52_high": int(week52["고가"].max()),
        "week52_low": int(week52["저가"].min()),
        "market_cap_krw": market_cap,
        "indicators": inds,
        "trading_days_loaded": len(df),
    }


@mcp.tool()
def get_us_stock(ticker: str, date: str | None = None) -> dict[str, Any]:
    """Get US stock daily OHLCV + indicators (NYSE/NASDAQ).

    Args:
        ticker: US stock ticker (e.g., "NVDA", "AAPL", "MSTR")
        date: Date in YYYY-MM-DD format. Defaults to most recent trading day.

    Returns:
        dict with: ticker, name, date, open, high, low, close, volume, change_pct,
                   week52_high, week52_low, market_cap, indicators.
    """
    end = pd.Timestamp(date) + pd.Timedelta(days=1) if date else pd.Timestamp.now()
    start = end - pd.Timedelta(days=400)

    tk = yf.Ticker(ticker)
    df = tk.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), auto_adjust=False)
    if df.empty:
        return {"error": f"No data for ticker {ticker} (yfinance)"}

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last
    change_pct = round((last["Close"] - prev["Close"]) / prev["Close"] * 100, 2)

    info = {}
    try:
        info = tk.info
    except Exception:
        pass

    week52 = df.tail(252) if len(df) >= 252 else df
    inds = _indicators(df["Close"], df["High"], df["Low"])

    return {
        "ticker": ticker.upper(),
        "name": info.get("shortName") or info.get("longName") or ticker,
        "market": info.get("exchange", "US"),
        "date": df.index[-1].strftime("%Y-%m-%d"),
        "open": round(float(last["Open"]), 2),
        "high": round(float(last["High"]), 2),
        "low": round(float(last["Low"]), 2),
        "close": round(float(last["Close"]), 2),
        "volume": int(last["Volume"]),
        "change_pct": change_pct,
        "week52_high": round(float(week52["High"].max()), 2),
        "week52_low": round(float(week52["Low"].min()), 2),
        "market_cap_usd": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "dividend_yield": info.get("dividendYield"),
        "indicators": inds,
        "trading_days_loaded": len(df),
    }


@mcp.tool()
def get_korean_index(index_name: str = "KOSPI", date: str | None = None) -> dict[str, Any]:
    """Get Korean market index (KOSPI / KOSDAQ / KOSPI200) via Yahoo Finance.

    pykrx의 KRX 지수 API는 최신 버전부터 KRX_ID/KRX_PW 인증을 요구하므로
    yfinance(무인증) 기반으로 전환했다. 종목 OHLCV는 여전히 pykrx 사용.

    Args:
        index_name: "KOSPI" | "KOSDAQ" | "KOSPI200"
        date: YYYY-MM-DD. Defaults to most recent trading day.
    """
    yf_map = {"KOSPI": "^KS11", "KOSDAQ": "^KQ11", "KOSPI200": "^KS200"}
    symbol = yf_map.get(index_name.upper())
    if not symbol:
        return {"error": f"Unknown index: {index_name}. Use KOSPI / KOSDAQ / KOSPI200"}

    t = yf.Ticker(symbol)
    if date:
        end = datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)
        start = end - timedelta(days=60)
        hist = t.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
    else:
        hist = t.history(period="5d")

    if hist.empty:
        return {"error": f"No data for {index_name} via yfinance"}

    last = hist.iloc[-1]
    prev = hist.iloc[-2] if len(hist) > 1 else last
    change = round(float(last["Close"] - prev["Close"]), 2)
    change_pct = round((last["Close"] - prev["Close"]) / prev["Close"] * 100, 2)
    vol_val = last.get("Volume", 0)
    try:
        volume = int(vol_val) if vol_val is not None else 0
    except (ValueError, TypeError):
        volume = 0

    return {
        "index": index_name.upper(),
        "symbol": symbol,
        "date": hist.index[-1].strftime("%Y-%m-%d"),
        "open": round(float(last["Open"]), 2),
        "high": round(float(last["High"]), 2),
        "low": round(float(last["Low"]), 2),
        "close": round(float(last["Close"]), 2),
        "volume": volume,
        "change": change,
        "change_pct": change_pct,
    }


@mcp.tool()
def search_korean_ticker(name: str) -> list[dict[str, str]]:
    """Search Korean stock ticker by company name (partial match).

    Args:
        name: Company name in Korean or English (e.g., "삼성전자", "롯데에너지", "Samsung")

    Returns:
        List of matching tickers with code + name. Limited to 10 results.
    """
    matches = []
    name_lower = name.lower()
    for market in ("KOSPI", "KOSDAQ"):
        try:
            tickers = krx.get_market_ticker_list(market=market)
            for t in tickers:
                try:
                    n = krx.get_market_ticker_name(t)
                    if name_lower in n.lower() or name in n:
                        matches.append({"ticker": t, "name": n, "market": market})
                        if len(matches) >= 10:
                            return matches
                except Exception:
                    continue
        except Exception:
            continue
    return matches


@mcp.tool()
def get_korean_investor_trading(ticker: str, date: str | None = None) -> dict[str, Any]:
    """Get foreign/institutional/individual net buying for a Korean stock (5-day).

    Args:
        ticker: 6-digit Korean stock code
        date: YYYY-MM-DD. Defaults to most recent trading day.
    """
    end_date = date.replace("-", "") if date else _today()
    start_date = _days_ago(10)

    try:
        df = krx.get_market_trading_value_by_date(start_date, end_date, ticker)
        if df.empty:
            return {"error": f"No investor data for {ticker}"}

        last = df.iloc[-1]
        return {
            "ticker": ticker,
            "date": _fmt(df.index[-1].strftime("%Y%m%d")),
            "institutional_krw": int(last.get("기관합계", 0)),
            "foreign_krw": int(last.get("외국인합계", 0)),
            "individual_krw": int(last.get("개인", 0)),
            "history_5day": [
                {
                    "date": _fmt(idx.strftime("%Y%m%d")),
                    "institutional": int(row.get("기관합계", 0)),
                    "foreign": int(row.get("외국인합계", 0)),
                    "individual": int(row.get("개인", 0)),
                }
                for idx, row in df.tail(5).iterrows()
            ],
        }
    except Exception as e:
        return {"error": f"pykrx fetch failed: {e}"}


def _safe(v, default=None):
    """Cast numpy/NaN/None to a clean python float, else default."""
    try:
        if v is None:
            return default
        f = float(v)
        return default if f != f else f  # NaN check
    except (ValueError, TypeError):
        return default


def _series_list(df, label, n=5, scale=1.0):
    """Extract one statement row as [latest..older] (scaled, rounded)."""
    try:
        if df is not None and not df.empty and label in df.index:
            return [round(v / scale, 2) if pd.notna(v) else None for v in df.loc[label].tolist()[:n]]
    except Exception:
        pass
    return []


@mcp.tool()
def get_us_financials(ticker):
    """Deep fundamentals for a US stock: 5yr income/cashflow trends, key ratios,
    and DCF-ready inputs. Complements get_us_stock (price/technicals) for fundamental study.

    Args:
        ticker: US stock ticker (e.g., "NVDA", "AAPL").

    Returns:
        dict with profile, valuation, profitability(ROE/ROA/ROIC/margins), growth,
        health(debt/cash/ratios), trends_billions(5yr), dcf_inputs.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        inc, cf = t.income_stmt, t.cashflow
        years = [str(c)[:10] for c in inc.columns][:5] if inc is not None and not inc.empty else []

        total_debt = _safe(info.get("totalDebt"), 0) or 0
        total_cash = _safe(info.get("totalCash"), 0) or 0
        net_debt = total_debt - total_cash

        roic = None
        try:
            ebit = _safe(inc.loc["EBIT"].iloc[0]) if (inc is not None and "EBIT" in inc.index) else None
            tax_rate = _safe(inc.loc["Tax Rate For Calcs"].iloc[0]) if (inc is not None and "Tax Rate For Calcs" in inc.index) else 0.21
            pb, mcap = _safe(info.get("priceToBook")), _safe(info.get("marketCap"))
            book_equity = (mcap / pb) if (pb and mcap) else None
            if ebit is not None and book_equity:
                invested = total_debt + book_equity - total_cash
                if invested and invested > 0:
                    roic = round(ebit * (1 - (tax_rate if tax_rate is not None else 0.21)) / invested, 4)
        except Exception:
            roic = None

        fcf_hist = _series_list(cf, "Free Cash Flow", 5, 1e9)
        fcf_clean = [v for v in fcf_hist if v is not None]
        fcf_3yr = round(sum(fcf_clean[:3]) / len(fcf_clean[:3]), 2) if fcf_clean[:3] else None

        return {
            "ticker": ticker,
            "profile": {
                "name": info.get("shortName"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
                "market_cap_usd": _safe(info.get("marketCap")),
                "enterprise_value_usd": _safe(info.get("enterpriseValue")),
            },
            "valuation": {
                "trailing_pe": _safe(info.get("trailingPE")),
                "forward_pe": _safe(info.get("forwardPE")),
                "price_to_book": _safe(info.get("priceToBook")),
                "ev_to_ebitda": _safe(info.get("enterpriseToEbitda")),
                "peg_ratio": _safe(info.get("pegRatio")),
                "dividend_yield": _safe(info.get("dividendYield")),
            },
            "profitability": {
                "gross_margin": _safe(info.get("grossMargins")),
                "operating_margin": _safe(info.get("operatingMargins")),
                "net_margin": _safe(info.get("profitMargins")),
                "roe": _safe(info.get("returnOnEquity")),
                "roa": _safe(info.get("returnOnAssets")),
                "roic_approx": roic,
            },
            "growth": {
                "revenue_growth_yoy": _safe(info.get("revenueGrowth")),
                "earnings_growth_yoy": _safe(info.get("earningsGrowth")),
            },
            "health": {
                "total_debt_usd": total_debt,
                "total_cash_usd": total_cash,
                "net_debt_usd": net_debt,
                "debt_to_equity": _safe(info.get("debtToEquity")),
                "current_ratio": _safe(info.get("currentRatio")),
            },
            "trends_billions": {
                "fiscal_years": years,
                "revenue": _series_list(inc, "Total Revenue", 5, 1e9),
                "ebit": _series_list(inc, "EBIT", 5, 1e9),
                "net_income": _series_list(inc, "Net Income", 5, 1e9),
                "diluted_eps": _series_list(inc, "Diluted EPS", 5, 1.0),
                "free_cash_flow": fcf_hist,
                "operating_cash_flow": _series_list(cf, "Operating Cash Flow", 5, 1e9),
                "capex": _series_list(cf, "Capital Expenditure", 5, 1e9),
            },
            "dcf_inputs": {
                "latest_fcf_usd": (fcf_clean[0] * 1e9) if fcf_clean else None,
                "fcf_3yr_avg_usd": (fcf_3yr * 1e9) if fcf_3yr else None,
                "shares_outstanding": _safe(info.get("sharesOutstanding")),
                "net_debt_usd": net_debt,
                "beta": _safe(info.get("beta")),
                "current_price": _safe(info.get("currentPrice") or info.get("regularMarketPrice")),
            },
        }
    except Exception as e:
        return {"error": f"yfinance financials fetch failed for {ticker}: {e}"}


@mcp.tool()
def dcf_valuation(base_fcf=None, shares_outstanding=None, ticker=None, growth_rate=0.10,
                  years=5, terminal_growth=0.025, discount_rate=None, net_debt=0.0):
    """Two-stage DCF intrinsic value per share.

    Provide explicit (base_fcf, shares_outstanding) OR a `ticker` to auto-fetch
    base_fcf (3yr-avg FCF), shares, net_debt, and a CAPM cost-of-equity discount rate.
    Explicit args override auto-fetched values. Currency follows inputs (USD for tickers).

    Args:
        base_fcf: Starting free cash flow (raw currency). Auto from ticker if omitted.
        shares_outstanding: Diluted shares. Auto from ticker if omitted.
        ticker: US ticker to auto-fill inputs (e.g., "NVDA").
        growth_rate: Stage-1 annual FCF growth (default 0.10).
        years: Stage-1 projection years (default 5).
        terminal_growth: Perpetual growth after stage 1 (default 0.025).
        discount_rate: WACC/cost of equity. Auto via CAPM (rf 4.2% + beta*5%) if omitted.
        net_debt: Debt minus cash (subtracted from EV). Auto from ticker if omitted.

    Returns:
        dict with intrinsic_value_per_share, breakdown, sensitivity grid, and (with ticker)
        current_price + upside_pct.
    """
    # MCP 레이어가 숫자 인자를 문자열로 전달할 수 있음 → float 강제 변환
    def _f(x):
        return None if x in (None, "") else float(x)
    base_fcf, shares_outstanding, discount_rate = _f(base_fcf), _f(shares_outstanding), _f(discount_rate)
    growth_rate, terminal_growth = float(growth_rate), float(terminal_growth)
    net_debt, years = float(net_debt or 0), int(float(years))

    current_price = beta = None
    try:
        if ticker:
            yt = yf.Ticker(ticker)
            info = yt.info or {}
            if base_fcf is None:
                cf = yt.cashflow
                fcfs = [float(v) for v in cf.loc["Free Cash Flow"].tolist()[:3] if pd.notna(v)] \
                    if (cf is not None and "Free Cash Flow" in cf.index) else []
                base_fcf = sum(fcfs) / len(fcfs) if fcfs else _safe(info.get("freeCashflow"))
            if shares_outstanding is None:
                shares_outstanding = _safe(info.get("sharesOutstanding"))
            if not net_debt:
                net_debt = (_safe(info.get("totalDebt"), 0) or 0) - (_safe(info.get("totalCash"), 0) or 0)
            beta = _safe(info.get("beta"))
            if discount_rate is None and beta is not None:
                discount_rate = round(0.042 + beta * 0.05, 4)  # CAPM: rf + beta*ERP
            current_price = _safe(info.get("currentPrice") or info.get("regularMarketPrice"))

        if discount_rate is None:
            discount_rate = 0.09
        if base_fcf is None or shares_outstanding is None:
            return {"error": "Need base_fcf and shares_outstanding (or a valid ticker)."}
        if base_fcf <= 0:
            return {"error": f"base_fcf non-positive ({base_fcf}); DCF not meaningful for negative-FCF firms."}
        if discount_rate <= terminal_growth:
            return {"error": f"discount_rate ({discount_rate}) must exceed terminal_growth ({terminal_growth})."}

        def _dcf(fcf0, g, wacc, tg, yrs, nd, sh):
            pv, fcf = 0.0, fcf0
            for k in range(1, yrs + 1):
                fcf *= (1 + g)
                pv += fcf / (1 + wacc) ** k
            tv = fcf * (1 + tg) / (wacc - tg)
            pv_tv = tv / (1 + wacc) ** yrs
            ev = pv + pv_tv
            eq = ev - nd
            return pv, pv_tv, ev, eq, eq / sh

        pv_s1, pv_tv, ev, equity, iv = _dcf(
            base_fcf, growth_rate, discount_rate, terminal_growth, years, net_debt, shares_outstanding)

        sens = {}
        for dw in (-0.01, 0.0, 0.01):
            w = round(discount_rate + dw, 4)
            if w <= terminal_growth:
                continue
            sens[f"wacc={w:.1%}"] = {
                f"g={round(growth_rate + dg, 4):.0%}": round(
                    _dcf(base_fcf, growth_rate + dg, w, terminal_growth, years, net_debt, shares_outstanding)[4], 2)
                for dg in (-0.02, 0.0, 0.02)
            }

        out = {
            "assumptions": {
                "base_fcf": round(base_fcf, 2), "growth_rate": growth_rate, "years": years,
                "terminal_growth": terminal_growth, "discount_rate": discount_rate,
                "net_debt": round(net_debt, 2), "shares_outstanding": shares_outstanding, "beta": beta,
                "discount_rate_method": "CAPM (rf 4.2% + beta*5%)" if (ticker and beta is not None) else "manual/default",
            },
            "breakdown": {
                "pv_stage1": round(pv_s1, 2), "pv_terminal": round(pv_tv, 2),
                "enterprise_value": round(ev, 2), "equity_value": round(equity, 2),
            },
            "intrinsic_value_per_share": round(iv, 2),
            "sensitivity_per_share": sens,
        }
        if current_price:
            out["current_price"] = current_price
            out["upside_pct"] = round((iv / current_price - 1) * 100, 1)
        return out
    except Exception as e:
        return {"error": f"DCF failed: {e}"}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
