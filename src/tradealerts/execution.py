from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

import json
from urllib import request

from tradealerts.config import AppConfig, ExecutionMode
from tradealerts.models import OrderRequest, OrderResult
from tradealerts.storage import Storage


class ExecutionProvider(ABC):
    @abstractmethod
    def place_order(self, order_request: OrderRequest) -> OrderResult:
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, order_id: str) -> OrderResult:
        raise NotImplementedError

    @abstractmethod
    def get_order(self, order_id: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    def get_positions(self) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def get_account(self) -> dict:
        raise NotImplementedError


class PaperExecutionProvider(ExecutionProvider):
    def __init__(self, storage: Storage) -> None:
        self.storage = storage
        self.orders: dict[str, dict] = {}

    def place_order(self, order_request: OrderRequest) -> OrderResult:
        oid = f"paper-{uuid.uuid4().hex[:10]}"
        now = datetime.now(timezone.utc)
        order = {
            "order_id": oid,
            "mode": "paper",
            "symbol": order_request.symbol,
            "side": order_request.side,
            "qty": order_request.qty,
            "price": order_request.limit_price,
            "stop_loss": order_request.stop_loss,
            "take_profit": order_request.take_profit,
            "status": "filled",
            "created_at": now.isoformat(),
            "strategy_name": "paper_execution",
        }
        self.orders[oid] = order
        self.storage.log_order(order)
        return OrderResult(order_id=oid, status="filled", filled_avg_price=order_request.limit_price, message="paper fill")

    def process_candle(self, symbol: str, high: float, low: float) -> None:
        for oid, o in list(self.orders.items()):
            if o["symbol"] != symbol or o["status"] != "filled":
                continue
            hit_tp = high >= o["take_profit"] if o["side"] == "buy" else low <= o["take_profit"]
            hit_sl = low <= o["stop_loss"] if o["side"] == "buy" else high >= o["stop_loss"]
            if hit_tp or hit_sl:
                exit_price = o["take_profit"] if hit_tp else o["stop_loss"]
                pnl = (exit_price - o["price"]) * o["qty"]
                if o["side"] == "sell":
                    pnl *= -1
                hold = (datetime.now(timezone.utc) - datetime.fromisoformat(o["created_at"])).total_seconds() / 60
                o["status"] = "closed_win" if pnl > 0 else "closed_loss"
                self.storage.update_order_close(oid, o["status"], pnl, hold)

    def cancel_order(self, order_id: str) -> OrderResult:
        return OrderResult(order_id=order_id, status="cancelled")

    def get_order(self, order_id: str) -> dict:
        return self.orders.get(order_id, {})

    def get_positions(self) -> list[dict]:
        return [o for o in self.orders.values() if o["status"] == "filled"]

    def get_account(self) -> dict:
        return {"buying_power": 1_000_000}


class LiveSafety:
    @staticmethod
    def validate(config: AppConfig, symbol: str, current_daily_loss_percent: float, open_positions: int) -> tuple[bool, str]:
        if Path("KILL_SWITCH").exists():
            return False, "kill_switch_enabled"
        if not config.enable_live_trading:
            return False, "ENABLE_LIVE_TRADING=false"
        if config.execution_mode != ExecutionMode.live:
            return False, "EXECUTION_MODE_not_live"
        if not config.i_understand_live_trading_risk:
            return False, "risk_ack_missing"
        if "paper" in config.alpaca_base_url:
            return False, "paper_endpoint_not_allowed_for_live"
        if not config.allowed_symbols_whitelist or symbol not in config.allowed_symbols_whitelist:
            return False, "symbol_not_whitelisted"
        if config.max_daily_loss_percent <= 0:
            return False, "max_daily_loss_not_configured"
        if config.max_notional_exposure <= 0:
            return False, "max_notional_exposure_not_configured"
        if config.max_open_positions <= 0:
            return False, "max_open_positions_not_configured"
        if current_daily_loss_percent >= config.max_daily_loss_percent:
            return False, "max_daily_loss_reached"
        if open_positions >= config.max_open_positions:
            return False, "max_open_positions_reached"
        return True, "ok"


class AlpacaExecutionProvider(ExecutionProvider):
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.headers = {
            "APCA-API-KEY-ID": config.alpaca_api_key or "",
            "APCA-API-SECRET-KEY": config.alpaca_secret_key or "",
        }

    def place_order(self, order_request: OrderRequest) -> OrderResult:
        if order_request.stop_loss <= 0 or order_request.take_profit <= 0:
            return OrderResult(order_id="", status="rejected", message="stop loss and take profit required")
        payload = {
            "symbol": order_request.symbol,
            "qty": str(order_request.qty),
            "side": order_request.side,
            "type": "limit",
            "time_in_force": "day",
            "limit_price": str(order_request.limit_price),
            "order_class": "bracket",
            "take_profit": {"limit_price": str(order_request.take_profit)},
            "stop_loss": {"stop_price": str(order_request.stop_loss)},
        }
        try:
            req = request.Request(f"{self.config.alpaca_base_url}/v2/orders", data=json.dumps(payload).encode("utf-8"), headers={**self.headers, "Content-Type":"application/json"})
            with request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return OrderResult(order_id=data.get("id", ""), status=data.get("status", "accepted"), message="live order sent")
        except Exception as exc:
            return OrderResult(order_id="", status="rejected", message=str(exc))

    def cancel_order(self, order_id: str) -> OrderResult:
        return OrderResult(order_id=order_id, status="cancelled")

    def get_order(self, order_id: str) -> dict:
        return {}

    def get_positions(self) -> list[dict]:
        return []

    def get_account(self) -> dict:
        return {}
