# TradeAlerts Bot

A ready-to-run Python trading research bot for:
- setup alerts (Discord)
- paper-trading execution (default-safe)
- backtesting from CSV
- SQLite logging and performance tracking
- optional Alpaca live execution behind strict safety gates

## What it does
- Watches configured tickers and timeframe.
- Computes VWAP, EMA(9), EMA(21), RSI(14), ATR(14), relative volume.
- Generates two strategies:
  - VWAP breakdown short
  - VWAP reclaim long
- Sends Discord webhook messages.
- Prevents duplicate/cooldown/day-cap spam.
- Logs signals/orders/fills/exits in SQLite.
- Calculates historical observed win rate and other metrics.

## What it does **not** do
- It does not predict guaranteed outcomes.
- It is not investment advice.
- It does not guarantee profit.

## Install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Configure
```bash
cp .env.example .env
# edit .env
```

## Run modes
```bash
tradealerts run-mock
tradealerts run-live-alerts-only
tradealerts run-paper-execution
tradealerts run-live-execution
```

## Backtest
```bash
tradealerts backtest --csv data/sample_ohlcv.csv --out-csv data/backtest_trades.csv --out-html data/backtest_report.html
```

## Performance and exports
```bash
tradealerts show-performance --mode paper
tradealerts export-trades --out data/orders_export.csv
```

## Discord webhook test
```bash
tradealerts test-discord --webhook https://discord.com/api/webhooks/...
```

## Kill switch
```bash
tradealerts kill-switch-on
tradealerts kill-switch-off
```
If `./KILL_SWITCH` exists, all **new live orders** are blocked.

## Live safety warnings
Live execution only proceeds when **all** checks pass:
- `ENABLE_LIVE_TRADING=true`
- `EXECUTION_MODE=live`
- `I_UNDERSTAND_LIVE_TRADING_RISK=true`
- live Alpaca endpoint (not paper)
- symbol in whitelist
- risk limits configured
- daily loss / open position limits not breached
- kill switch absent

## Win rate language
All win rates are reported as historical backtest / paper / live observed performance only. They are not predictions.

## Run tests
```bash
pytest
```

## Troubleshooting
- No signals: lower relative-volume threshold or use richer market data.
- Discord failures: verify webhook URL.
- Live blocked: inspect status reason; safety gate intentionally strict.
