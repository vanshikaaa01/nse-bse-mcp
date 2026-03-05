"""
NSE/BSE MCP Server
==================
A Model Context Protocol server for Indian stock market data.
Covers NSE (National Stock Exchange) and BSE (Bombay Stock Exchange).

Data source: Yahoo Finance via yfinance (no API key required)
Exchange suffixes: .NS for NSE, .BO for BSE

Author: Vanshika
License: MIT
"""

import json
import asyncio
from typing import Optional, List
from datetime import datetime, timedelta
from enum import Enum

import yfinance as yf
from pydantic import BaseModel, Field, field_validator, ConfigDict
from mcp.server.fastmcp import FastMCP

# ─── Server Init ────────────────────────────────────────────────────────────────

mcp = FastMCP(
    "nse_bse_mcp",
    instructions=(
        "This server provides Indian stock market data for NSE and BSE listed companies. "
        "Use symbol names like RELIANCE, TCS, INFY (without exchange suffix) and specify "
        "the exchange as 'NSE' or 'BSE'. For indices, use NIFTY50, SENSEX, NIFTYBANK, etc."
    ),
)

# ─── Constants ───────────────────────────────────────────────────────────────────

NSE_SUFFIX = ".NS"
BSE_SUFFIX = ".BO"

INDICES = {
    "NIFTY50": "^NSEI",
    "SENSEX": "^BSESN",
    "NIFTYBANK": "^NSEBANK",
    "NIFTYMIDCAP": "^NSEMDCP50",
    "NIFTYIT": "^CNXIT",
    "NIFTYPHARMA": "^CNXPHARMA",
    "NIFTYFMCG": "^CNXFMCG",
    "NIFTYAUTO": "^CNXAUTO",
    "NIFTYREALTY": "^CNXREALTY",
    "NIFTYINFRA": "^CNXINFRA",
    "NIFTYMETAL": "^CNXMETAL",
    "NIFTYENERGY": "^CNXENERGY",
    "NIFTY100": "^CNX100",
    "NIFTY200": "^CNX200",
    "NIFTYNEXT50": "^NSMIDCP",
    "INDIAVIX": "^INDIAVIX",
}

VALID_PERIODS = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"]
VALID_INTERVALS = ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def build_ticker(symbol: str, exchange: str) -> str:
    """Build Yahoo Finance ticker string from symbol and exchange."""
    symbol = symbol.upper().strip()
    if exchange.upper() == "BSE":
        return f"{symbol}{BSE_SUFFIX}"
    return f"{symbol}{NSE_SUFFIX}"  # Default to NSE


def fmt_crore(value: float) -> str:
    """Format a number in Indian crore notation."""
    if value is None:
        return "N/A"
    crore = value / 1e7
    if crore >= 1e5:
        return f"₹{crore/1e5:.2f} Lakh Cr"
    elif crore >= 1e2:
        return f"₹{crore:.2f} Cr"
    else:
        return f"₹{value:,.2f}"


def safe_get(d: dict, *keys, default="N/A"):
    """Safely get a nested key from a dict."""
    for key in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(key, default)
    return d if d not in (None, "", float("inf"), float("-inf")) else default


def fmt_pct(value) -> str:
    """Format a decimal as percentage string."""
    if value is None or value == "N/A":
        return "N/A"
    try:
        return f"{float(value)*100:.2f}%"
    except (TypeError, ValueError):
        return "N/A"


def fmt_num(value, decimals=2) -> str:
    """Format a number safely."""
    if value is None or value == "N/A":
        return "N/A"
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"


def handle_error(e: Exception, context: str = "") -> str:
    """Return a standardized, actionable error message."""
    msg = str(e)
    if "No data found" in msg or "404" in msg:
        return f"Error: Symbol not found on this exchange. Try the other exchange (NSE/BSE) or check the symbol spelling. Context: {context}"
    if "Rate" in msg or "429" in msg:
        return "Error: Rate limit hit. Please wait a few seconds and retry."
    if "timeout" in msg.lower():
        return "Error: Request timed out. NSE/BSE servers may be slow. Please retry."
    return f"Error fetching data: {msg}. Context: {context}"


# ─── Pydantic Models ──────────────────────────────────────────────────────────

class Exchange(str, Enum):
    NSE = "NSE"
    BSE = "BSE"


class StockInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    symbol: str = Field(
        ...,
        description="Stock symbol/ticker as listed on NSE/BSE. E.g. RELIANCE, TCS, INFY, HDFCBANK, RAIN",
        min_length=1,
        max_length=20,
    )
    exchange: Exchange = Field(
        default=Exchange.NSE,
        description="Exchange to use: 'NSE' (default) or 'BSE'",
    )

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        return v.upper()


class HistoricalInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    symbol: str = Field(..., description="Stock symbol. E.g. RELIANCE, TCS, RAIN, HDFCBANK", min_length=1, max_length=20)
    exchange: Exchange = Field(default=Exchange.NSE, description="Exchange: 'NSE' or 'BSE'")
    period: str = Field(
        default="3mo",
        description="Period for historical data. Options: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max",
    )
    interval: str = Field(
        default="1d",
        description="Data interval. Options: 1m, 5m, 15m, 1h, 1d, 1wk, 1mo. Note: intraday only for last 60 days.",
    )

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        return v.upper()

    @field_validator("period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        if v not in VALID_PERIODS:
            raise ValueError(f"period must be one of: {', '.join(VALID_PERIODS)}")
        return v

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, v: str) -> str:
        if v not in VALID_INTERVALS:
            raise ValueError(f"interval must be one of: {', '.join(VALID_INTERVALS)}")
        return v


class CompareInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    symbols: List[str] = Field(
        ...,
        description="List of stock symbols to compare. E.g. ['RELIANCE', 'TCS', 'INFY']. Max 10.",
        min_length=2,
        max_length=10,
    )
    exchange: Exchange = Field(default=Exchange.NSE, description="Exchange: 'NSE' or 'BSE'")

    @field_validator("symbols")
    @classmethod
    def uppercase_symbols(cls, v: List[str]) -> List[str]:
        return [s.upper().strip() for s in v]


class IndexInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    index: str = Field(
        ...,
        description=(
            "Index name. Options: NIFTY50, SENSEX, NIFTYBANK, NIFTYMIDCAP, NIFTYIT, "
            "NIFTYPHARMA, NIFTYFMCG, NIFTYAUTO, NIFTYREALTY, NIFTYMETAL, NIFTYENERGY, "
            "NIFTY100, NIFTY200, NIFTYNEXT50, INDIAVIX"
        ),
    )
    period: str = Field(default="1d", description="Period: 1d, 5d, 1mo, 3mo, 6mo, 1y")

    @field_validator("index")
    @classmethod
    def uppercase_index(cls, v: str) -> str:
        return v.upper().strip()


# ─── Tools ────────────────────────────────────────────────────────────────────

@mcp.tool(
    name="nse_bse_get_quote",
    annotations={
        "title": "Get Live Stock Quote",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def nse_bse_get_quote(params: StockInput) -> str:
    """
    Get a real-time quote for any NSE or BSE listed stock.

    Returns current price, change, volume, 52-week range, and key valuation
    metrics (P/E, P/B, EPS, market cap, dividend yield).

    Args:
        params (StockInput): symbol (str), exchange (str: 'NSE'|'BSE')

    Returns:
        str: Formatted markdown with live quote data in INR.
    """
    try:
        ticker_str = build_ticker(params.symbol, params.exchange)
        ticker = yf.Ticker(ticker_str)
        info = ticker.info

        if not info or info.get("regularMarketPrice") is None:
            return f"Error: No data found for {params.symbol} on {params.exchange}. Check the symbol or try BSE instead."

        price = info.get("regularMarketPrice") or info.get("currentPrice", "N/A")
        prev_close = info.get("previousClose", "N/A")
        change = round(float(price) - float(prev_close), 2) if prev_close != "N/A" else "N/A"
        pct_change = round((change / float(prev_close)) * 100, 2) if prev_close != "N/A" and prev_close != 0 else "N/A"
        direction = "▲" if isinstance(change, float) and change >= 0 else "▼"

        result = f"""## {info.get('longName', params.symbol)} ({params.symbol}.{params.exchange})

### 📈 Live Quote
| Field | Value |
|-------|-------|
| **Last Price** | ₹{fmt_num(price)} |
| **Change** | {direction} ₹{fmt_num(abs(change) if change != "N/A" else change)} ({pct_change}%) |
| **Open** | ₹{fmt_num(info.get('open'))} |
| **Day High** | ₹{fmt_num(info.get('dayHigh'))} |
| **Day Low** | ₹{fmt_num(info.get('dayLow'))} |
| **Prev Close** | ₹{fmt_num(prev_close)} |
| **Volume** | {info.get('volume', 'N/A'):,} |
| **Avg Volume (10d)** | {info.get('averageVolume10days', 'N/A'):,} |

### 📊 52-Week Range
| | Value |
|--|-------|
| **52W High** | ₹{fmt_num(info.get('fiftyTwoWeekHigh'))} |
| **52W Low** | ₹{fmt_num(info.get('fiftyTwoWeekLow'))} |
| **50-Day MA** | ₹{fmt_num(info.get('fiftyDayAverage'))} |
| **200-Day MA** | ₹{fmt_num(info.get('twoHundredDayAverage'))} |

### 🏦 Valuation Metrics
| Metric | Value |
|--------|-------|
| **Market Cap** | {fmt_crore(info.get('marketCap'))} |
| **P/E Ratio (TTM)** | {fmt_num(info.get('trailingPE'))} |
| **Forward P/E** | {fmt_num(info.get('forwardPE'))} |
| **P/B Ratio** | {fmt_num(info.get('priceToBook'))} |
| **EPS (TTM)** | ₹{fmt_num(info.get('trailingEps'))} |
| **Dividend Yield** | {fmt_pct(info.get('dividendYield'))} |
| **Beta** | {fmt_num(info.get('beta'))} |

### 🏭 Company Info
| Field | Value |
|-------|-------|
| **Sector** | {info.get('sector', 'N/A')} |
| **Industry** | {info.get('industry', 'N/A')} |
| **Exchange** | {params.exchange} |
| **Currency** | {info.get('currency', 'INR')} |
"""
        return result

    except Exception as e:
        return handle_error(e, f"{params.symbol} on {params.exchange}")


@mcp.tool(
    name="nse_bse_get_historical",
    annotations={
        "title": "Get Historical OHLCV Data",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def nse_bse_get_historical(params: HistoricalInput) -> str:
    """
    Get historical OHLCV (Open, High, Low, Close, Volume) data for a stock.

    Useful for technical analysis, backtesting, and price trend review.
    Returns a table of data with date, OHLCV, and % daily return.

    Args:
        params (HistoricalInput): symbol, exchange, period (e.g. '1y'), interval (e.g. '1d')

    Returns:
        str: JSON string with list of OHLCV records and summary statistics.
    """
    try:
        ticker_str = build_ticker(params.symbol, params.exchange)
        ticker = yf.Ticker(ticker_str)
        df = ticker.history(period=params.period, interval=params.interval)

        if df.empty:
            return f"Error: No historical data found for {params.symbol} on {params.exchange} for period '{params.period}'."

        df = df.reset_index()
        df["Date"] = df["Date"].astype(str).str[:10]
        df["Return_%"] = df["Close"].pct_change().mul(100).round(2)

        records = []
        for _, row in df.tail(100).iterrows():  # last 100 rows max to keep context manageable
            records.append({
                "date": str(row["Date"]),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
                "daily_return_pct": round(float(row["Return_%"]), 2) if not str(row["Return_%"]) == "nan" else None,
            })

        # Summary stats
        first_close = float(df["Close"].iloc[0])
        last_close = float(df["Close"].iloc[-1])
        total_return = round(((last_close - first_close) / first_close) * 100, 2)
        high = round(float(df["High"].max()), 2)
        low = round(float(df["Low"].min()), 2)
        avg_vol = int(df["Volume"].mean())

        result = {
            "symbol": params.symbol,
            "exchange": params.exchange,
            "period": params.period,
            "interval": params.interval,
            "summary": {
                "start_date": records[0]["date"] if records else "N/A",
                "end_date": records[-1]["date"] if records else "N/A",
                "start_price": first_close,
                "end_price": last_close,
                "total_return_pct": total_return,
                "period_high": high,
                "period_low": low,
                "avg_daily_volume": avg_vol,
                "total_records_shown": len(records),
            },
            "data": records,
        }
        return json.dumps(result, indent=2)

    except Exception as e:
        return handle_error(e, f"historical data for {params.symbol}")


@mcp.tool(
    name="nse_bse_get_fundamentals",
    annotations={
        "title": "Get Stock Fundamentals & Financials",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def nse_bse_get_fundamentals(params: StockInput) -> str:
    """
    Get detailed fundamental and financial data for a stock.

    Covers income statement highlights, balance sheet, cash flows,
    growth metrics, profitability ratios, and analyst estimates.

    Args:
        params (StockInput): symbol (str), exchange (str)

    Returns:
        str: Formatted markdown with fundamental analysis data.
    """
    try:
        ticker_str = build_ticker(params.symbol, params.exchange)
        ticker = yf.Ticker(ticker_str)
        info = ticker.info

        if not info:
            return f"Error: No fundamental data found for {params.symbol} on {params.exchange}."

        result = f"""## {info.get('longName', params.symbol)} — Fundamental Analysis

### 💰 Revenue & Profitability
| Metric | Value |
|--------|-------|
| **Revenue (TTM)** | {fmt_crore(info.get('totalRevenue'))} |
| **Gross Profit** | {fmt_crore(info.get('grossProfits'))} |
| **EBITDA** | {fmt_crore(info.get('ebitda'))} |
| **Operating Income** | {fmt_crore(info.get('operatingIncome'))} |
| **Net Income (TTM)** | {fmt_crore(info.get('netIncomeToCommon'))} |
| **Gross Margin** | {fmt_pct(info.get('grossMargins'))} |
| **Operating Margin** | {fmt_pct(info.get('operatingMargins'))} |
| **Net Profit Margin** | {fmt_pct(info.get('profitMargins'))} |
| **ROE** | {fmt_pct(info.get('returnOnEquity'))} |
| **ROA** | {fmt_pct(info.get('returnOnAssets'))} |

### 📊 Balance Sheet Snapshot
| Metric | Value |
|--------|-------|
| **Total Assets** | {fmt_crore(info.get('totalAssets'))} |
| **Total Debt** | {fmt_crore(info.get('totalDebt'))} |
| **Cash & Equivalents** | {fmt_crore(info.get('totalCash'))} |
| **Book Value/Share** | ₹{fmt_num(info.get('bookValue'))} |
| **Debt/Equity** | {fmt_num(info.get('debtToEquity'))} |
| **Current Ratio** | {fmt_num(info.get('currentRatio'))} |
| **Quick Ratio** | {fmt_num(info.get('quickRatio'))} |

### 📈 Per Share Data
| Metric | Value |
|--------|-------|
| **EPS (TTM)** | ₹{fmt_num(info.get('trailingEps'))} |
| **Forward EPS** | ₹{fmt_num(info.get('forwardEps'))} |
| **Revenue/Share** | ₹{fmt_num(info.get('revenuePerShare'))} |
| **Cash/Share** | ₹{fmt_num(info.get('totalCashPerShare'))} |
| **Dividend/Share** | ₹{fmt_num(info.get('lastDividendValue'))} |
| **Payout Ratio** | {fmt_pct(info.get('payoutRatio'))} |

### 🚀 Growth Metrics
| Metric | Value |
|--------|-------|
| **Earnings Growth (YoY)** | {fmt_pct(info.get('earningsGrowth'))} |
| **Revenue Growth (YoY)** | {fmt_pct(info.get('revenueGrowth'))} |

### 🎯 Analyst Estimates
| Metric | Value |
|--------|-------|
| **Target Price (Mean)** | ₹{fmt_num(info.get('targetMeanPrice'))} |
| **Target Price (High)** | ₹{fmt_num(info.get('targetHighPrice'))} |
| **Target Price (Low)** | ₹{fmt_num(info.get('targetLowPrice'))} |
| **Analyst Recommendation** | {info.get('recommendationKey', 'N/A').upper()} |
| **No. of Analysts** | {info.get('numberOfAnalystOpinions', 'N/A')} |

### 🏢 Company Description
{info.get('longBusinessSummary', 'No description available.')[:500]}...
"""
        return result

    except Exception as e:
        return handle_error(e, f"fundamentals for {params.symbol}")


@mcp.tool(
    name="nse_bse_get_financials",
    annotations={
        "title": "Get Financial Statements",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def nse_bse_get_financials(params: StockInput) -> str:
    """
    Get annual income statement, balance sheet, and cash flow statement for a stock.

    Returns last 4 years of annual financials in JSON format. Useful for
    multi-year trend analysis and valuation models.

    Args:
        params (StockInput): symbol (str), exchange (str)

    Returns:
        str: JSON with income statement, balance sheet, and cash flow data.
    """
    try:
        ticker_str = build_ticker(params.symbol, params.exchange)
        ticker = yf.Ticker(ticker_str)

        financials = {}

        # Income Statement
        try:
            income = ticker.financials
            if income is not None and not income.empty:
                income_dict = {}
                for col in income.columns:
                    col_str = str(col)[:10]
                    income_dict[col_str] = {
                        row: (round(float(val) / 1e7, 2) if val is not None and str(val) != "nan" else None)
                        for row, val in income[col].items()
                    }
                financials["income_statement_crore"] = income_dict
        except Exception:
            financials["income_statement_crore"] = "unavailable"

        # Balance Sheet
        try:
            balance = ticker.balance_sheet
            if balance is not None and not balance.empty:
                balance_dict = {}
                for col in balance.columns:
                    col_str = str(col)[:10]
                    balance_dict[col_str] = {
                        row: (round(float(val) / 1e7, 2) if val is not None and str(val) != "nan" else None)
                        for row, val in balance[col].items()
                    }
                financials["balance_sheet_crore"] = balance_dict
        except Exception:
            financials["balance_sheet_crore"] = "unavailable"

        # Cash Flow
        try:
            cashflow = ticker.cashflow
            if cashflow is not None and not cashflow.empty:
                cf_dict = {}
                for col in cashflow.columns:
                    col_str = str(col)[:10]
                    cf_dict[col_str] = {
                        row: (round(float(val) / 1e7, 2) if val is not None and str(val) != "nan" else None)
                        for row, val in cashflow[col].items()
                    }
                financials["cash_flow_crore"] = cf_dict
        except Exception:
            financials["cash_flow_crore"] = "unavailable"

        financials["symbol"] = params.symbol
        financials["exchange"] = params.exchange
        financials["note"] = "All monetary values in Indian Crore (₹). Columns are fiscal year end dates."

        return json.dumps(financials, indent=2, default=str)

    except Exception as e:
        return handle_error(e, f"financials for {params.symbol}")


@mcp.tool(
    name="nse_bse_compare_stocks",
    annotations={
        "title": "Compare Multiple Stocks",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def nse_bse_compare_stocks(params: CompareInput) -> str:
    """
    Compare key metrics across multiple NSE/BSE stocks side by side.

    Useful for peer analysis, sector screening, and portfolio comparison.
    Returns a markdown table with price, valuation, and profitability metrics.

    Args:
        params (CompareInput): symbols (list of str), exchange (str)

    Returns:
        str: Markdown comparison table for all requested stocks.
    """
    try:
        rows = []
        for sym in params.symbols:
            ticker_str = build_ticker(sym, params.exchange)
            try:
                info = yf.Ticker(ticker_str).info
                price = info.get("regularMarketPrice") or info.get("currentPrice")
                prev_close = info.get("previousClose")
                change_pct = round(((float(price) - float(prev_close)) / float(prev_close)) * 100, 2) if price and prev_close else None
                rows.append({
                    "symbol": sym,
                    "name": info.get("shortName", sym),
                    "price": price,
                    "change_pct": change_pct,
                    "market_cap_cr": round(info.get("marketCap", 0) / 1e7, 0) if info.get("marketCap") else None,
                    "pe": info.get("trailingPE"),
                    "pb": info.get("priceToBook"),
                    "roe_pct": round(info.get("returnOnEquity", 0) * 100, 1) if info.get("returnOnEquity") else None,
                    "npm_pct": round(info.get("profitMargins", 0) * 100, 1) if info.get("profitMargins") else None,
                    "div_yield_pct": round(info.get("dividendYield", 0) * 100, 2) if info.get("dividendYield") else None,
                    "52w_high": info.get("fiftyTwoWeekHigh"),
                    "52w_low": info.get("fiftyTwoWeekLow"),
                    "beta": info.get("beta"),
                    "sector": info.get("sector", "N/A"),
                })
            except Exception:
                rows.append({"symbol": sym, "name": "Error fetching", "error": True})

        # Build markdown table
        header = "| Symbol | Name | Price (₹) | Chg% | Mkt Cap (Cr) | P/E | P/B | ROE% | NPM% | Div Yield | Beta | Sector |"
        sep = "|--------|------|-----------|------|--------------|-----|-----|------|------|-----------|------|--------|"
        table_rows = [header, sep]

        for r in rows:
            if r.get("error"):
                table_rows.append(f"| {r['symbol']} | Error | - | - | - | - | - | - | - | - | - | - |")
            else:
                def v(x): return fmt_num(x) if x is not None else "N/A"
                chg = f"{'▲' if r['change_pct'] and r['change_pct']>=0 else '▼'}{abs(r['change_pct']):.2f}%" if r.get("change_pct") else "N/A"
                table_rows.append(
                    f"| {r['symbol']} | {r['name'][:20]} | ₹{v(r['price'])} | {chg} | "
                    f"{int(r['market_cap_cr']) if r['market_cap_cr'] else 'N/A'} | "
                    f"{v(r['pe'])} | {v(r['pb'])} | {v(r['roe_pct'])} | {v(r['npm_pct'])} | "
                    f"{v(r['div_yield_pct'])} | {v(r['beta'])} | {r.get('sector','N/A')[:15]} |"
                )

        return f"## Stock Comparison — {params.exchange}\n\n" + "\n".join(table_rows)

    except Exception as e:
        return handle_error(e, "stock comparison")


@mcp.tool(
    name="nse_bse_get_index",
    annotations={
        "title": "Get Index Quote & Performance",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def nse_bse_get_index(params: IndexInput) -> str:
    """
    Get current quote and recent performance for major Indian market indices.

    Supported indices: NIFTY50, SENSEX, NIFTYBANK, NIFTYMIDCAP, NIFTYIT,
    NIFTYPHARMA, NIFTYFMCG, NIFTYAUTO, NIFTYREALTY, NIFTYMETAL, NIFTYENERGY,
    NIFTY100, NIFTY200, NIFTYNEXT50, INDIAVIX.

    Args:
        params (IndexInput): index (str), period (str)

    Returns:
        str: Markdown with index quote and historical performance summary.
    """
    try:
        if params.index not in INDICES:
            return (
                f"Error: '{params.index}' is not a valid index. "
                f"Valid options: {', '.join(INDICES.keys())}"
            )

        ticker_str = INDICES[params.index]
        ticker = yf.Ticker(ticker_str)
        info = ticker.info
        hist = ticker.history(period=params.period, interval="1d")

        price = info.get("regularMarketPrice") or info.get("previousClose", "N/A")
        prev_close = info.get("previousClose", "N/A")
        change = round(float(price) - float(prev_close), 2) if prev_close != "N/A" else "N/A"
        pct_change = round((change / float(prev_close)) * 100, 2) if prev_close != "N/A" and prev_close != 0 else "N/A"
        direction = "▲" if isinstance(change, float) and change >= 0 else "▼"

        perf_str = ""
        if not hist.empty:
            start_price = float(hist["Close"].iloc[0])
            end_price = float(hist["Close"].iloc[-1])
            period_return = round(((end_price - start_price) / start_price) * 100, 2)
            period_high = round(float(hist["High"].max()), 2)
            period_low = round(float(hist["Low"].min()), 2)
            perf_str = f"""
### 📅 Period Performance ({params.period})
| Metric | Value |
|--------|-------|
| **Period Return** | {period_return}% |
| **Period High** | {period_high:,.2f} |
| **Period Low** | {period_low:,.2f} |
"""

        return f"""## {params.index} — Index Quote

### 📈 Current Level
| Field | Value |
|-------|-------|
| **Level** | {price:,.2f} |
| **Change** | {direction} {abs(change) if change != "N/A" else change:,.2f} ({pct_change}%) |
| **52W High** | {fmt_num(info.get('fiftyTwoWeekHigh'))} |
| **52W Low** | {fmt_num(info.get('fiftyTwoWeekLow'))} |
| **50-Day MA** | {fmt_num(info.get('fiftyDayAverage'))} |
| **200-Day MA** | {fmt_num(info.get('twoHundredDayAverage'))} |
{perf_str}
"""
    except Exception as e:
        return handle_error(e, f"index {params.index}")


@mcp.tool(
    name="nse_bse_list_indices",
    annotations={
        "title": "List Available Indian Market Indices",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def nse_bse_list_indices() -> str:
    """
    List all Indian market indices available in this MCP server.

    Returns:
        str: Markdown table of all supported index names and their Yahoo Finance tickers.
    """
    lines = ["## Available Indian Market Indices\n", "| Index Name | Yahoo Finance Ticker |", "|------------|----------------------|"]
    for name, ticker in INDICES.items():
        lines.append(f"| {name} | {ticker} |")
    lines.append("\nUse these index names with the `nse_bse_get_index` tool.")
    return "\n".join(lines)


@mcp.tool(
    name="nse_bse_get_dividends",
    annotations={
        "title": "Get Dividend History",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def nse_bse_get_dividends(params: StockInput) -> str:
    """
    Get the full dividend payout history for a stock.

    Useful for dividend yield analysis, income investing research,
    and identifying consistent dividend payers.

    Args:
        params (StockInput): symbol (str), exchange (str)

    Returns:
        str: JSON with list of dividend payments with dates and amounts in INR.
    """
    try:
        ticker_str = build_ticker(params.symbol, params.exchange)
        ticker = yf.Ticker(ticker_str)
        divs = ticker.dividends

        if divs is None or divs.empty:
            return json.dumps({
                "symbol": params.symbol,
                "exchange": params.exchange,
                "message": "No dividend history found. This stock may not pay dividends.",
                "dividends": []
            })

        div_list = [
            {"date": str(date)[:10], "dividend_inr": round(float(amt), 4)}
            for date, amt in divs.items()
        ]
        div_list.reverse()  # most recent first

        total_last_5yr = sum(
            d["dividend_inr"] for d in div_list
            if int(d["date"][:4]) >= datetime.now().year - 5
        )

        return json.dumps({
            "symbol": params.symbol,
            "exchange": params.exchange,
            "total_dividends_last_5y_inr": round(total_last_5yr, 2),
            "total_payments": len(div_list),
            "dividends": div_list[:20],  # last 20 payments
        }, indent=2)

    except Exception as e:
        return handle_error(e, f"dividends for {params.symbol}")


@mcp.tool(
    name="nse_bse_get_shareholders",
    annotations={
        "title": "Get Institutional & Promoter Shareholding",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def nse_bse_get_shareholders(params: StockInput) -> str:
    """
    Get major institutional shareholders and ownership breakdown for a stock.

    Returns top mutual fund / FII / DII holders and promoter holding percentage.
    Useful for tracking institutional interest and ownership concentration.

    Args:
        params (StockInput): symbol (str), exchange (str)

    Returns:
        str: JSON with institutional holders, major holders breakdown.
    """
    try:
        ticker_str = build_ticker(params.symbol, params.exchange)
        ticker = yf.Ticker(ticker_str)

        result = {"symbol": params.symbol, "exchange": params.exchange}

        # Major holders
        try:
            major = ticker.major_holders
            if major is not None and not major.empty:
                result["major_holders"] = {
                    str(row[1]): str(row[0])
                    for _, row in major.iterrows()
                }
        except Exception:
            result["major_holders"] = "unavailable"

        # Institutional holders
        try:
            inst = ticker.institutional_holders
            if inst is not None and not inst.empty:
                result["top_institutional_holders"] = [
                    {
                        "holder": str(row.get("Holder", "")),
                        "shares": int(row.get("Shares", 0)),
                        "date_reported": str(row.get("Date Reported", ""))[:10],
                        "pct_held": round(float(row.get("% Out", 0)) * 100, 2),
                        "value_inr_cr": round(float(row.get("Value", 0)) / 1e7, 2),
                    }
                    for _, row in inst.head(15).iterrows()
                ]
        except Exception:
            result["top_institutional_holders"] = "unavailable"

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        return handle_error(e, f"shareholders for {params.symbol}")


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
