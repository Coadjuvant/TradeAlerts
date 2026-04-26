from __future__ import annotations

import argparse
import json
from pathlib import Path

from tradealerts.alerts import send_discord
from tradealerts.backtest import run_backtest
from tradealerts.config import AppConfig, ExecutionMode, load_config
from tradealerts.data_providers import MockDataProvider
from tradealerts.engine import dump_json, export_trades, run_once, show_performance


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tradealerts")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in [
        "generate-sample-config",
        "run-once",
        "run-mock",
        "run-live-alerts-only",
        "run-paper-execution",
        "run-live-execution",
        "show-performance",
        "export-trades",
        "test-discord",
        "kill-switch-on",
        "kill-switch-off",
    ]:
        sub.add_parser(name)
    b = sub.add_parser("backtest")
    b.add_argument("--csv", required=True)
    b.add_argument("--out-csv", default="data/backtest_trades.csv")
    b.add_argument("--out-html", default="data/backtest_report.html")
    et = sub.choices["export-trades"]
    et.add_argument("--out", default="data/orders_export.csv")
    sp = sub.choices["show-performance"]
    sp.add_argument("--mode", choices=["paper", "live"], default=None)
    td = sub.choices["test-discord"]
    td.add_argument("--webhook", default=None)
    return p


def _sample_env() -> str:
    return """TICKERS=AAPL,MSFT
TIMEFRAME=5m
MARKET_TYPE=stocks
ACCOUNT_SIZE=10000
MAX_RISK_PERCENT_PER_TRADE=0.5
MAX_ALERTS_PER_TICKER_PER_DAY=5
COOLDOWN_MINUTES=30
DISCORD_WEBHOOK_URL=
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ALPACA_BASE_URL=https://paper-api.alpaca.markets
PAPER_TRADING=true
EXECUTION_MODE=alerts_only
ALLOWED_SYMBOLS_WHITELIST=AAPL,MSFT
MAX_DAILY_LOSS_PERCENT=3
MAX_TRADES_PER_DAY=10
MAX_OPEN_POSITIONS=5
MAX_NOTIONAL_EXPOSURE=5000
SLIPPAGE_ASSUMPTION=0.0005
FEE_ASSUMPTION=0.0002
ENABLE_LIVE_TRADING=false
I_UNDERSTAND_LIVE_TRADING_RISK=false
"""


def _normalize_env() -> None:
    for old, new in {
        "TICKERS": "tickers",
        "TIMEFRAME": "timeframe",
        "MARKET_TYPE": "market_type",
        "ACCOUNT_SIZE": "account_size",
        "MAX_RISK_PERCENT_PER_TRADE": "max_risk_percent_per_trade",
        "MAX_ALERTS_PER_TICKER_PER_DAY": "max_alerts_per_ticker_per_day",
        "COOLDOWN_MINUTES": "cooldown_minutes",
        "DISCORD_WEBHOOK_URL": "discord_webhook_url",
        "ALPACA_API_KEY": "alpaca_api_key",
        "ALPACA_SECRET_KEY": "alpaca_secret_key",
        "ALPACA_BASE_URL": "alpaca_base_url",
        "PAPER_TRADING": "paper_trading",
        "EXECUTION_MODE": "execution_mode",
        "ALLOWED_SYMBOLS_WHITELIST": "allowed_symbols_whitelist",
        "MAX_DAILY_LOSS_PERCENT": "max_daily_loss_percent",
        "MAX_TRADES_PER_DAY": "max_trades_per_day",
        "MAX_OPEN_POSITIONS": "max_open_positions",
        "MAX_NOTIONAL_EXPOSURE": "max_notional_exposure",
        "SLIPPAGE_ASSUMPTION": "slippage_assumption",
        "FEE_ASSUMPTION": "fee_assumption",
        "ENABLE_LIVE_TRADING": "enable_live_trading",
        "I_UNDERSTAND_LIVE_TRADING_RISK": "i_understand_live_trading_risk",
    }.items():
        import os

        if old in os.environ and new not in os.environ:
            os.environ[new] = os.environ[old]

    import os

    if "tickers" in os.environ and isinstance(os.environ["tickers"], str):
        os.environ["tickers"] = json.dumps([x.strip() for x in os.environ["tickers"].split(",") if x.strip()])
    if "allowed_symbols_whitelist" in os.environ and isinstance(os.environ["allowed_symbols_whitelist"], str):
        os.environ["allowed_symbols_whitelist"] = json.dumps([x.strip() for x in os.environ["allowed_symbols_whitelist"].split(",") if x.strip()])


def main() -> None:
    args = _parser().parse_args()
    if args.cmd == "generate-sample-config":
        Path("config").mkdir(exist_ok=True)
        Path("config/sample.env").write_text(_sample_env(), encoding="utf-8")
        Path(".env.example").write_text(_sample_env(), encoding="utf-8")
        print("Generated config/sample.env and .env.example")
        return
    if args.cmd == "kill-switch-on":
        Path("KILL_SWITCH").write_text("1", encoding="utf-8")
        print("KILL_SWITCH enabled")
        return
    if args.cmd == "kill-switch-off":
        Path("KILL_SWITCH").unlink(missing_ok=True)
        print("KILL_SWITCH disabled")
        return

    _normalize_env()
    config = load_config()
    provider = MockDataProvider()

    if args.cmd in {"run-once", "run-mock"}:
        print("\n".join(run_once(config, provider)))
    elif args.cmd == "run-live-alerts-only":
        config.execution_mode = ExecutionMode.alerts_only
        print("\n".join(run_once(config, provider)))
    elif args.cmd == "run-paper-execution":
        config.execution_mode = ExecutionMode.paper
        print("\n".join(run_once(config, provider)))
    elif args.cmd == "run-live-execution":
        config.execution_mode = ExecutionMode.live
        print("\n".join(run_once(config, provider)))
    elif args.cmd == "backtest":
        _, summary = run_backtest(config, args.csv, args.out_csv, args.out_html)
        print(dump_json(summary))
    elif args.cmd == "show-performance":
        print(dump_json(show_performance(config, mode=args.mode)))
    elif args.cmd == "export-trades":
        print(export_trades(config, args.out))
    elif args.cmd == "test-discord":
        ok = send_discord(args.webhook or str(config.discord_webhook_url) if config.discord_webhook_url else None, {"content": "test"})
        print("ok" if ok else "failed")


if __name__ == "__main__":
    main()
