from __future__ import annotations

from tradealerts.models import Signal


def _crossed_up(prev_fast: float, prev_slow: float, fast: float, slow: float) -> bool:
    return prev_fast <= prev_slow and fast > slow


def _crossed_down(prev_fast: float, prev_slow: float, fast: float, slow: float) -> bool:
    return prev_fast >= prev_slow and fast < slow


def vwap_breakdown_short(rows: list[dict], symbol: str, rvol_threshold: float, rr: float = 2.0) -> Signal | None:
    if len(rows) < 3:
        return None
    row, prev = rows[-1], rows[-2]
    if not (row["close"] < row["vwap"] and ((row["ema9"] < row["ema21"]) or _crossed_down(prev["ema9"], prev["ema21"], row["ema9"], row["ema21"])) and row["rsi14"] < 50 and row["relative_volume"] >= rvol_threshold):
        return None
    swing_high = max(r["high"] for r in rows[-5:])
    invalidation = max(row["vwap"], swing_high)
    stop = invalidation + row["atr14"] * 0.1
    risk = stop - row["close"]
    if risk <= 0:
        return None
    return Signal(symbol=symbol, direction="short", strategy_name="vwap_breakdown_short", timestamp=row["timestamp"], current_price=row["close"], reason_codes=["close_below_vwap","ema9_below_ema21","rsi_below_50","rvol_high"], indicator_values={k: float(row[k]) for k in ["vwap","ema9","ema21","rsi14","atr14","relative_volume"]}, entry_area=(row["close"]*0.999,row["close"]*1.001), invalidation_level=invalidation, stop_loss=stop, take_profit=row["close"]-risk*rr, atr=row["atr14"], risk_reward_ratio=rr)


def vwap_reclaim_long(rows: list[dict], symbol: str, rvol_threshold: float, rr: float = 2.0) -> Signal | None:
    if len(rows) < 3:
        return None
    row, prev = rows[-1], rows[-2]
    if not (row["close"] > row["vwap"] and ((row["ema9"] > row["ema21"]) or _crossed_up(prev["ema9"], prev["ema21"], row["ema9"], row["ema21"])) and row["rsi14"] > 50 and row["relative_volume"] >= rvol_threshold):
        return None
    swing_low = min(r["low"] for r in rows[-5:])
    invalidation = min(row["vwap"], swing_low)
    stop = invalidation - row["atr14"] * 0.1
    risk = row["close"] - stop
    if risk <= 0:
        return None
    return Signal(symbol=symbol, direction="long", strategy_name="vwap_reclaim_long", timestamp=row["timestamp"], current_price=row["close"], reason_codes=["close_above_vwap","ema9_above_ema21","rsi_above_50","rvol_high"], indicator_values={k: float(row[k]) for k in ["vwap","ema9","ema21","rsi14","atr14","relative_volume"]}, entry_area=(row["close"]*0.999,row["close"]*1.001), invalidation_level=invalidation, stop_loss=stop, take_profit=row["close"]+risk*rr, atr=row["atr14"], risk_reward_ratio=rr)
