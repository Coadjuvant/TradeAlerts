from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from tradealerts.alerts import AlertThrottler, format_discord_message, send_discord
from tradealerts.config import AppConfig, ExecutionMode
from tradealerts.data_providers import DataProvider
from tradealerts.execution import AlpacaExecutionProvider, LiveSafety, PaperExecutionProvider
from tradealerts.indicators import add_indicators
from tradealerts.models import OrderRequest
from tradealerts.performance import summarize_trades
from tradealerts.risk import calculate_position_size
from tradealerts.storage import Storage
from tradealerts.strategies import vwap_breakdown_short, vwap_reclaim_long

logger = logging.getLogger(__name__)


def run_once(config: AppConfig, provider: DataProvider) -> list[str]:
    storage = Storage(config.db_path)
    throttler = AlertThrottler(storage, config.cooldown_minutes, config.max_alerts_per_ticker_per_day)
    paper = PaperExecutionProvider(storage)
    live = AlpacaExecutionProvider(config)
    statuses: list[str] = []

    for symbol in config.tickers:
        candles = provider.get_recent_candles(symbol, config.timeframe, 200)
        if not candles:
            statuses.append(f"{symbol}: no_data")
            continue
        df = add_indicators(candles)
        signals = [
            vwap_reclaim_long(df, symbol, config.strategy.relative_volume_threshold, config.strategy.risk_reward_ratio),
            vwap_breakdown_short(df, symbol, config.strategy.relative_volume_threshold, config.strategy.risk_reward_ratio),
        ]
        for sig in [s for s in signals if s is not None]:
            allow, reason = throttler.allow(sig)
            risk = calculate_position_size(config.account_size, config.max_risk_percent_per_trade, sig.current_price, sig.stop_loss, config.slippage_assumption)
            qty = max(1.0, risk.quantity)
            status = "alert_only"
            if not allow:
                status = f"blocked:{reason}"
            else:
                sid = storage.insert_signal(sig)
                throttler.record(sig)
                if config.execution_mode == ExecutionMode.paper:
                    result = paper.place_order(
                        OrderRequest(
                            symbol=sig.symbol,
                            side="buy" if sig.direction == "long" else "sell",
                            qty=qty,
                            limit_price=sig.current_price,
                            stop_loss=sig.stop_loss,
                            take_profit=sig.take_profit,
                            signal_id=sid,
                        )
                    )
                    status = f"paper_order_{result.status}"
                elif config.execution_mode == ExecutionMode.live:
                    ok, why = LiveSafety.validate(config, sig.symbol, current_daily_loss_percent=0.0, open_positions=0)
                    if not ok:
                        status = f"blocked:{why}"
                        storage.log_order(
                            {
                                "order_id": f"blocked-{datetime.now(timezone.utc).timestamp()}",
                                "mode": "live",
                                "symbol": sig.symbol,
                                "side": "buy" if sig.direction == "long" else "sell",
                                "qty": qty,
                                "price": sig.current_price,
                                "stop_loss": sig.stop_loss,
                                "take_profit": sig.take_profit,
                                "status": status,
                                "created_at": datetime.now(timezone.utc).isoformat(),
                                "strategy_name": sig.strategy_name,
                            }
                        )
                    else:
                        result = live.place_order(
                            OrderRequest(
                                symbol=sig.symbol,
                                side="buy" if sig.direction == "long" else "sell",
                                qty=qty,
                                limit_price=sig.current_price,
                                stop_loss=sig.stop_loss,
                                take_profit=sig.take_profit,
                            )
                        )
                        status = f"live_order_{result.status}"
            payload = format_discord_message(sig, config.execution_mode.value, status, qty, risk.dollar_risk)
            send_discord(str(config.discord_webhook_url) if config.discord_webhook_url else None, payload)
            statuses.append(f"{sig.symbol}:{sig.strategy_name}:{status}")
            logger.info(statuses[-1])
    return statuses


def show_performance(config: AppConfig, mode: str | None = None) -> dict:
    storage = Storage(config.db_path)
    rows = storage.fetch_closed_orders(mode)
    trades = [dict(r) for r in rows]
    label = "paper-trading" if mode == "paper" else "live-trading" if mode == "live" else "all"
    return summarize_trades(trades, label=label)


def export_trades(config: AppConfig, out_file: str) -> str:
    import csv

    storage = Storage(config.db_path)
    rows = [dict(r) for r in storage.fetch_all_orders()]
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        if rows:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
    return out_file


def dump_json(data: dict) -> str:
    return json.dumps(data, indent=2, default=str)
