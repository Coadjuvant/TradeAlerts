from __future__ import annotations

from statistics import mean


def ema(values: list[float], period: int) -> list[float]:
    out: list[float] = []
    alpha = 2 / (period + 1)
    prev = values[0] if values else 0.0
    for v in values:
        prev = alpha * v + (1 - alpha) * prev
        out.append(prev)
    return out


def rsi(values: list[float], period: int = 14) -> list[float]:
    out = [50.0]
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(values)):
        d = values[i] - values[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
        g = mean(gains[-period:]) if gains else 0.0
        l = mean(losses[-period:]) if losses else 0.0
        out.append(100.0 if l == 0 else 100 - (100 / (1 + g / l)))
    return out


def vwap(rows: list[dict]) -> list[float]:
    cum_pv = 0.0
    cum_v = 0.0
    out: list[float] = []
    for r in rows:
        t = (r["high"] + r["low"] + r["close"]) / 3
        cum_pv += t * r["volume"]
        cum_v += r["volume"]
        out.append(cum_pv / cum_v if cum_v else r["close"])
    return out


def atr(rows: list[dict], period: int = 14) -> list[float]:
    out: list[float] = []
    trs: list[float] = []
    prev_close = rows[0]["close"] if rows else 0.0
    for r in rows:
        tr = max(r["high"] - r["low"], abs(r["high"] - prev_close), abs(r["low"] - prev_close))
        trs.append(tr)
        prev_close = r["close"]
        out.append(mean(trs[-period:]))
    return out


def relative_volume(volumes: list[float], period: int = 20) -> list[float]:
    out: list[float] = []
    for i, v in enumerate(volumes):
        m = mean(volumes[max(0, i - period + 1) : i + 1])
        out.append(v / m if m else 1.0)
    return out


def add_indicators(rows: list[dict]) -> list[dict]:
    closes = [r["close"] for r in rows]
    vols = [r["volume"] for r in rows]
    vw = vwap(rows)
    e9 = ema(closes, 9)
    e21 = ema(closes, 21)
    rs = rsi(closes, 14)
    at = atr(rows, 14)
    rv = relative_volume(vols, 20)
    out = []
    for i, r in enumerate(rows):
        n = dict(r)
        n.update({"vwap": vw[i], "ema9": e9[i], "ema21": e21[i], "rsi14": rs[i], "atr14": at[i], "relative_volume": rv[i]})
        out.append(n)
    return out
