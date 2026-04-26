from __future__ import annotations

import csv
from pathlib import Path

from tradealerts.config import AppConfig
from tradealerts.indicators import add_indicators
from tradealerts.performance import summarize_trades
from tradealerts.risk import calculate_position_size
from tradealerts.strategies import vwap_breakdown_short, vwap_reclaim_long


def _read_csv(path: str) -> list[dict]:
    rows: list[dict] = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({"timestamp": r["timestamp"], "symbol": r["symbol"], "open": float(r["open"]), "high": float(r["high"]), "low": float(r["low"]), "close": float(r["close"]), "volume": float(r["volume"])})
    return sorted(rows, key=lambda x: (x["symbol"], x["timestamp"]))


def run_backtest(config: AppConfig, csv_path: str, out_csv: str | None = None, out_html: str | None = None) -> tuple[list[dict], dict]:
    rows = _read_csv(csv_path)
    trades: list[dict] = []
    symbols = sorted({r["symbol"] for r in rows})
    for symbol in symbols:
        sdf = add_indicators([r for r in rows if r["symbol"] == symbol])
        i = 30
        while i < len(sdf) - 1:
            hist = sdf[: i + 1]
            signal = vwap_reclaim_long(hist, symbol, config.strategy.relative_volume_threshold, config.strategy.risk_reward_ratio) or vwap_breakdown_short(hist, symbol, config.strategy.relative_volume_threshold, config.strategy.risk_reward_ratio)
            if not signal:
                i += 1
                continue
            entry_bar = sdf[i + 1]
            entry = entry_bar["open"]
            side = "buy" if signal.direction == "long" else "sell"
            qty = max(1.0, calculate_position_size(config.account_size, config.max_risk_percent_per_trade, entry, signal.stop_loss, config.slippage_assumption).quantity)
            j = i + 1
            while j < len(sdf):
                r = sdf[j]
                hit_tp = r["high"] >= signal.take_profit if side == "buy" else r["low"] <= signal.take_profit
                hit_sl = r["low"] <= signal.stop_loss if side == "buy" else r["high"] >= signal.stop_loss
                if hit_tp or hit_sl:
                    exit_px = signal.take_profit if hit_tp else signal.stop_loss
                    pnl = (exit_px - entry) * qty
                    if side == "sell":
                        pnl *= -1
                    pnl -= (entry + exit_px) * qty * config.fee_assumption
                    trades.append({"symbol": symbol, "side": side, "entry_time": entry_bar["timestamp"], "exit_time": r["timestamp"], "entry": entry, "exit": exit_px, "qty": qty, "pnl": pnl, "hold_minutes": (j - (i + 1)) * 5, "strategy_name": signal.strategy_name})
                    i = j + 1
                    break
                j += 1
            else:
                i += 1
    summary = summarize_trades(trades, "historical backtest")
    if out_csv:
        Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            if trades:
                writer = csv.DictWriter(f, fieldnames=list(trades[0].keys()))
                writer.writeheader(); writer.writerows(trades)
    if out_html:
        Path(out_html).write_text("<html><body><pre>" + str(trades) + "</pre></body></html>", encoding="utf-8")
    return trades, summary
