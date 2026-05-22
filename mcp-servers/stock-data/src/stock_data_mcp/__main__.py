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
    """Get Korean market index (KOSPI / KOSDAQ / KOSPI200).

    Args:
        index_name: "KOSPI" | "KOSDAQ" | "KOSPI200"
        date: YYYY-MM-DD. Defaults to most recent trading day.
    """
    code_map = {"KOSPI": "1001", "KOSDAQ": "2001", "KOSPI200": "1028"}
    code = code_map.get(index_name.upper())
    if not code:
        return {"error": f"Unknown index: {index_name}. Use KOSPI / KOSDAQ / KOSPI200"}

    end_date = date.replace("-", "") if date else _today()
    start_date = _days_ago(30)

    df = krx.get_index_ohlcv(start_date, end_date, code)
    if df.empty:
        return {"error": f"No index data for {index_name}"}

    last = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else last
    change = round(float(last["종가"] - prev["종가"]), 2)
    change_pct = round((last["종가"] - prev["종가"]) / prev["종가"] * 100, 2)

    return {
        "index": index_name.upper(),
        "date": _fmt(df.index[-1].strftime("%Y%m%d")),
        "open": round(float(last["시가"]), 2),
        "high": round(float(last["고가"]), 2),
        "low": round(float(last["저가"]), 2),
        "close": round(float(last["종가"]), 2),
        "volume": int(last["거래량"]),
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


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
