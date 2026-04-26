from __future__ import annotations

from datetime import datetime, timezone, timedelta

import json
from urllib import request

from tradealerts.models import Signal
from tradealerts.storage import Storage


def format_discord_message(
    signal: Signal,
    mode: str,
    status: str,
    qty: float,
    risk_amount: float,
) -> dict:
    text = (
        f"**{signal.symbol}** | Direction: potential {signal.direction}\n"
        f"Price: {signal.current_price:.2f} | Strategy: {signal.strategy_name}\n"
        f"Reasons: {', '.join(signal.reason_codes)}\n"
        f"Entry: {signal.entry_area[0]:.2f}-{signal.entry_area[1]:.2f}\n"
        f"Stop: {signal.stop_loss:.2f} | TP: {signal.take_profit:.2f} | Invalidation: {signal.invalidation_level:.2f}\n"
        f"ATR: {signal.atr:.4f} | Suggested size: {qty:.2f} | Risk amount: ${risk_amount:.2f}\n"
        f"Timestamp: {signal.timestamp.isoformat()} | Mode: {mode} | Status: {status}\n"
        "Alert only / research tool. Not financial advice. No guaranteed outcome."
    )
    return {"content": text}


def send_discord(webhook_url: str | None, payload: dict) -> bool:
    if not webhook_url:
        return False
    try:
        req = request.Request(webhook_url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type":"application/json"})
        with request.urlopen(req, timeout=10) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False


class AlertThrottler:
    def __init__(self, storage: Storage, cooldown_minutes: int, max_alerts_per_day: int) -> None:
        self.storage = storage
        self.cooldown_minutes = cooldown_minutes
        self.max_alerts_per_day = max_alerts_per_day

    def allow(self, signal: Signal) -> tuple[bool, str]:
        if self.storage.is_duplicate_signal(signal):
            return False, "duplicate_signal"
        if self.storage.count_alerts_today(signal.symbol) >= self.max_alerts_per_day:
            return False, "daily_alert_cap"
        last = self.storage.last_alert_time(signal.symbol)
        if last and datetime.now(timezone.utc) - last < timedelta(minutes=self.cooldown_minutes):
            return False, "cooldown_active"
        return True, "ok"

    def record(self, signal: Signal) -> None:
        sig = self.storage.signal_signature(signal)
        self.storage.log_alert(signal.symbol, sig)
