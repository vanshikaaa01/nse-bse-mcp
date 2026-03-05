# 🇮🇳 NSE/BSE MCP Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server for Indian stock market data — covering the National Stock Exchange (NSE) and Bombay Stock Exchange (BSE).

Plug this into Claude Desktop and ask questions like:
- *"What is the current price and P/E of RELIANCE?"*
- *"Compare HDFCBANK, ICICIBANK, and SBIN on valuation metrics"*
- *"Show me RAIN Industries' 1-year historical data"*
- *"What is the NIFTY50 trading at today?"*
- *"Get the dividend history for ITC"*
- *"Who are the top institutional shareholders of TCS?"*

**No API key required.** Powered by [yfinance](https://github.com/ranaroussi/yfinance).

---

## 🛠️ Tools

| Tool | Description |
|------|-------------|
| `nse_bse_get_quote` | Live price quote with valuation metrics (P/E, P/B, EPS, market cap) |
| `nse_bse_get_historical` | Historical OHLCV data with configurable period and interval |
| `nse_bse_get_fundamentals` | Deep fundamental analysis — revenue, margins, ROE, analyst targets |
| `nse_bse_get_financials` | Annual income statement, balance sheet & cash flow (last 4 years) |
| `nse_bse_compare_stocks` | Side-by-side comparison table for multiple stocks |
| `nse_bse_get_index` | Quote and performance for NIFTY50, SENSEX, and 13 other indices |
| `nse_bse_list_indices` | List all supported Indian market indices |
| `nse_bse_get_dividends` | Full dividend payout history |
| `nse_bse_get_shareholders` | Top institutional holders and ownership breakdown |

---

## 🚀 Installation

### Prerequisites
- Python 3.10+
- Claude Desktop (for local use)

### Steps

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/nse-bse-mcp.git
cd nse-bse-mcp

# 2. Install dependencies
pip install -r requirements.txt
```

### Configure Claude Desktop

Find your Claude Desktop config file:
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

Add this to your config (use full paths):

**Windows:**
```json
{
  "mcpServers": {
    "nse-bse": {
      "command": "C:\\Python312\\python.exe",
      "args": ["C:\\full\\path\\to\\nse-bse-mcp\\server.py"]
    }
  }
}
```

**macOS/Linux:**
```json
{
  "mcpServers": {
    "nse-bse": {
      "command": "python3",
      "args": ["/full/path/to/nse-bse-mcp/server.py"]
    }
  }
}
```

Then **fully restart Claude Desktop** (right-click tray icon → Quit, then reopen).

---

## 💡 Usage Examples

### Get a live stock quote
> *"What is the current quote for RAIN Industries on NSE?"*

### Historical data
> *"Get me 1 year of daily OHLCV data for HDFCBANK on NSE"*

### Peer comparison
> *"Compare RELIANCE, ONGC, and BPCL on P/E, P/B, and ROE"*

### Index tracking
> *"What is NIFTYBANK at today? Show me the past month's performance"*

### Fundamental research
> *"Give me a full fundamental breakdown of Hindustan Zinc"*

---

## 📊 Supported Indices

| Index | Description |
|-------|-------------|
| NIFTY50 | NSE's flagship large-cap index |
| SENSEX | BSE's 30-stock benchmark |
| NIFTYBANK | Banking sector index |
| NIFTYMIDCAP | Midcap 50 index |
| NIFTYIT | IT sector index |
| NIFTYPHARMA | Pharma sector index |
| NIFTYFMCG | FMCG sector index |
| NIFTYAUTO | Automobile sector index |
| NIFTYREALTY | Real estate index |
| NIFTYMETAL | Metals sector index |
| NIFTYENERGY | Energy sector index |
| NIFTY100 | Top 100 stocks |
| NIFTY200 | Top 200 stocks |
| NIFTYNEXT50 | Next 50 after Nifty50 |
| INDIAVIX | India Volatility Index |

---

## 📝 Notes

- Exchange suffixes: `.NS` for NSE, `.BO` for BSE (handled automatically)
- Data is delayed by ~15 minutes during market hours
- Financial data (income statement, balance sheet) is annual and may lag by 1–2 quarters
- For real-time tick data, a broker API (Zerodha Kite, AngelOne, etc.) is recommended

---

## ⚠️ Disclaimer

This tool is for **educational and research purposes only**. Data is sourced from Yahoo Finance and may contain errors or delays. This is not financial advice. Always verify data from official NSE/BSE sources before making investment decisions.

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

## 🤝 Contributing

PRs welcome! Areas for contribution:
- Add support for F&O (futures & options) data
- Add options chain tool
- Add mutual fund NAV tracking
- Add screener integration (Screener.in)
- Add corporate actions (bonus, splits, rights)
