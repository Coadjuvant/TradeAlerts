from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ExecutionMode(str, Enum):
    alerts_only = "alerts_only"
    paper = "paper"
    live = "live"


class MarketType(str, Enum):
    stocks = "stocks"
    crypto = "crypto"


@dataclass
class StrategySettings:
    relative_volume_threshold: float = 1.2
    risk_reward_ratio: float = 2.0
    atr_stop_multiplier: float = 1.0


@dataclass
class AppConfig:
    tickers: list[str] = field(default_factory=lambda: ["AAPL", "MSFT"])
    timeframe: str = "5m"
    market_type: MarketType = MarketType.stocks
    strategy: StrategySettings = field(default_factory=StrategySettings)
    account_size: float = 10000.0
    max_risk_percent_per_trade: float = 0.5
    max_alerts_per_ticker_per_day: int = 5
    cooldown_minutes: int = 30
    discord_webhook_url: str | None = None
    alpaca_api_key: str | None = None
    alpaca_secret_key: str | None = None
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    paper_trading: bool = True
    execution_mode: ExecutionMode = ExecutionMode.alerts_only
    allowed_symbols_whitelist: list[str] = field(default_factory=list)
    max_daily_loss_percent: float = 3.0
    max_trades_per_day: int = 10
    max_open_positions: int = 5
    max_notional_exposure: float = 5000.0
    slippage_assumption: float = 0.0005
    fee_assumption: float = 0.0002
    enable_live_trading: bool = False
    i_understand_live_trading_risk: bool = False
    data_dir: Path = Path("data")
    db_path: Path = Path("data/tradealerts.db")

    def __post_init__(self) -> None:
        self.tickers = [t.upper() for t in self.tickers]
        self.allowed_symbols_whitelist = [t.upper() for t in self.allowed_symbols_whitelist]
        if not (0 < self.max_risk_percent_per_trade <= 5):
            raise ValueError("max_risk_percent_per_trade must be in (0,5]")


def _read_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def _as_bool(v: str, default: bool) -> bool:
    if v is None:
        return default
    return v.lower() in {"1", "true", "yes", "on"}


def load_config(env_file: str | None = None) -> AppConfig:
    _read_dotenv(env_file or ".env")
    tickers = os.getenv("tickers") or os.getenv("TICKERS")
    whitelist = os.getenv("allowed_symbols_whitelist") or os.getenv("ALLOWED_SYMBOLS_WHITELIST")
    return AppConfig(
        tickers=[x.strip().upper() for x in (tickers.split(",") if tickers else ["AAPL", "MSFT"]) if x.strip()],
        timeframe=os.getenv("timeframe", os.getenv("TIMEFRAME", "5m")),
        market_type=MarketType(os.getenv("market_type", os.getenv("MARKET_TYPE", "stocks"))),
        account_size=float(os.getenv("account_size", os.getenv("ACCOUNT_SIZE", "10000"))),
        max_risk_percent_per_trade=float(os.getenv("max_risk_percent_per_trade", os.getenv("MAX_RISK_PERCENT_PER_TRADE", "0.5"))),
        max_alerts_per_ticker_per_day=int(os.getenv("max_alerts_per_ticker_per_day", os.getenv("MAX_ALERTS_PER_TICKER_PER_DAY", "5"))),
        cooldown_minutes=int(os.getenv("cooldown_minutes", os.getenv("COOLDOWN_MINUTES", "30"))),
        discord_webhook_url=os.getenv("discord_webhook_url", os.getenv("DISCORD_WEBHOOK_URL")) or None,
        alpaca_api_key=os.getenv("alpaca_api_key", os.getenv("ALPACA_API_KEY")) or None,
        alpaca_secret_key=os.getenv("alpaca_secret_key", os.getenv("ALPACA_SECRET_KEY")) or None,
        alpaca_base_url=os.getenv("alpaca_base_url", os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")),
        paper_trading=_as_bool(os.getenv("paper_trading", os.getenv("PAPER_TRADING", "true")), True),
        execution_mode=ExecutionMode(os.getenv("execution_mode", os.getenv("EXECUTION_MODE", "alerts_only"))),
        allowed_symbols_whitelist=[x.strip().upper() for x in (whitelist.split(",") if whitelist else []) if x.strip()],
        max_daily_loss_percent=float(os.getenv("max_daily_loss_percent", os.getenv("MAX_DAILY_LOSS_PERCENT", "3"))),
        max_trades_per_day=int(os.getenv("max_trades_per_day", os.getenv("MAX_TRADES_PER_DAY", "10"))),
        max_open_positions=int(os.getenv("max_open_positions", os.getenv("MAX_OPEN_POSITIONS", "5"))),
        max_notional_exposure=float(os.getenv("max_notional_exposure", os.getenv("MAX_NOTIONAL_EXPOSURE", "5000"))),
        slippage_assumption=float(os.getenv("slippage_assumption", os.getenv("SLIPPAGE_ASSUMPTION", "0.0005"))),
        fee_assumption=float(os.getenv("fee_assumption", os.getenv("FEE_ASSUMPTION", "0.0002"))),
        enable_live_trading=_as_bool(os.getenv("enable_live_trading", os.getenv("ENABLE_LIVE_TRADING", "false")), False),
        i_understand_live_trading_risk=_as_bool(os.getenv("i_understand_live_trading_risk", os.getenv("I_UNDERSTAND_LIVE_TRADING_RISK", "false")), False),
    )
