from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Candle:
    timestamp: datetime
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        if not self.symbol:
            raise ValueError("symbol cannot be empty")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("prices must be > 0")
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close) or self.high < self.low:
            raise ValueError("invalid OHLC")


@dataclass
class Signal:
    symbol: str
    direction: str
    strategy_name: str
    timestamp: datetime
    current_price: float
    reason_codes: list[str]
    indicator_values: dict[str, float]
    entry_area: tuple[float, float]
    invalidation_level: float
    stop_loss: float
    take_profit: float
    atr: float
    risk_reward_ratio: float


@dataclass
class OrderRequest:
    symbol: str
    side: str
    qty: float
    limit_price: float
    stop_loss: float
    take_profit: float
    signal_id: int | None = None


@dataclass
class OrderResult:
    order_id: str
    status: str
    filled_avg_price: float | None = None
    message: str = ""
