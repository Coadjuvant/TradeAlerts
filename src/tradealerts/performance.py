from __future__ import annotations

import math
from collections import defaultdict
from statistics import mean, pstdev


def _max_drawdown(equity: list[float]) -> float:
    peak = -10**18
    mdd = 0.0
    for x in equity:
        peak = max(peak, x)
        mdd = min(mdd, x - peak)
    return abs(mdd)


def summarize_trades(trades: list[dict], label: str) -> dict:
    pnls = [float(t.get("pnl", 0.0)) for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    equity = []
    c = 0.0
    for p in pnls:
        c += p
        equity.append(c)
    holds = [float(t.get("hold_minutes", 0.0)) for t in trades]
    by_side = defaultdict(list); by_symbol = defaultdict(list); by_strategy = defaultdict(list)
    for t in trades:
        by_side[t.get("side","")].append(float(t.get("pnl",0)))
        by_symbol[t.get("symbol","")].append(float(t.get("pnl",0)))
        by_strategy[t.get("strategy_name","")].append(float(t.get("pnl",0)))
    sharpe = None
    if len(pnls) > 1 and pstdev(pnls) > 0:
        sharpe = (mean(pnls) / pstdev(pnls)) * math.sqrt(len(pnls))
    n = len(pnls)
    return {
        "label": f"{label} win rate (historical observed, not predictive)",
        "total_signals": n,
        "total_trades": n,
        "win_rate_percent": (len(wins)/n*100) if n else 0.0,
        "loss_rate_percent": (len(losses)/n*100) if n else 0.0,
        "average_win": mean(wins) if wins else 0.0,
        "average_loss": mean(losses) if losses else 0.0,
        "profit_factor": abs(sum(wins)/sum(losses)) if losses else (float("inf") if wins else 0.0),
        "expectancy": mean(pnls) if pnls else 0.0,
        "max_drawdown": _max_drawdown(equity) if equity else 0.0,
        "sharpe_ratio": sharpe,
        "average_hold_time_minutes": mean(holds) if holds else 0.0,
        "long_win_rate": (sum(1 for p in by_side.get("buy",[]) if p>0)/len(by_side.get("buy",[]))*100) if by_side.get("buy") else 0.0,
        "short_win_rate": (sum(1 for p in by_side.get("sell",[]) if p>0)/len(by_side.get("sell",[]))*100) if by_side.get("sell") else 0.0,
        "per_symbol_stats": {k:{"trades":len(v),"pnl":sum(v)} for k,v in by_symbol.items()},
        "per_strategy_stats": {k:{"trades":len(v),"pnl":sum(v)} for k,v in by_strategy.items()},
        "warnings": ["Small sample size; statistics may be unstable."] if n < 30 else [],
    }
