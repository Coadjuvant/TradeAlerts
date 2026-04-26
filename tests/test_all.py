from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tradealerts.alerts import AlertThrottler, format_discord_message
from tradealerts.backtest import run_backtest
from tradealerts.config import AppConfig, ExecutionMode
from tradealerts.data_providers import CSVDataProvider, MockDataProvider
from tradealerts.execution import LiveSafety, PaperExecutionProvider
from tradealerts.indicators import add_indicators, atr, ema, relative_volume, rsi, vwap
from tradealerts.models import Candle, OrderRequest
from tradealerts.performance import summarize_trades
from tradealerts.risk import calculate_position_size
from tradealerts.storage import Storage
from tradealerts.strategies import vwap_breakdown_short, vwap_reclaim_long


def sample_rows() -> list[dict]:
    rows = []
    now = datetime.now(timezone.utc)
    price = 100.0
    for i in range(40):
        price += 0.4 if i < 30 else -0.6 if i < 35 else 0.3
        rows.append({"timestamp": now + timedelta(minutes=i * 5), "symbol": "AAPL", "open": price - 0.2, "high": price + 0.5, "low": price - 0.5, "close": price, "volume": 1000 + (700 if i > 30 else 0)})
    return rows


def test_config_validation():
    assert AppConfig(tickers=["aapl"]).tickers == ["AAPL"]
    with pytest.raises(Exception):
        AppConfig(max_risk_percent_per_trade=10)


def test_candle_model_validation():
    assert Candle(timestamp=datetime.now(timezone.utc), symbol="aapl", open=1, high=2, low=0.5, close=1.5, volume=10).symbol == "AAPL"
    with pytest.raises(Exception):
        Candle(timestamp=datetime.now(timezone.utc), symbol="", open=1, high=0.5, low=0.4, close=0.6, volume=10)


def test_indicators():
    r = sample_rows()
    assert len(vwap(r)) == len(r)
    assert len(ema([x["close"] for x in r], 9)) == len(r)
    assert len(rsi([x["close"] for x in r], 14)) == len(r)
    assert len(atr(r, 14)) == len(r)
    assert len(relative_volume([x["volume"] for x in r])) == len(r)


def test_strategies_and_no_trigger():
    d = add_indicators(sample_rows())
    assert vwap_reclaim_long(d, "AAPL", 1.0) is not None or vwap_breakdown_short(d, "AAPL", 1.0) is not None
    for x in d:
        x["relative_volume"] = 0.1
    assert vwap_reclaim_long(d, "AAPL", 2.0) is None


def test_risk_calc():
    rr = calculate_position_size(10000, 0.5, 100, 99, 0.0005)
    assert rr.dollar_risk == 50


def test_discord_formatting():
    sig = vwap_reclaim_long(add_indicators(sample_rows()), "AAPL", 1.0)
    if sig is None:
        sig = vwap_breakdown_short(add_indicators(sample_rows()), "AAPL", 1.0)
    msg = format_discord_message(sig, "paper", "paper_order_filled", 10, 50)
    assert "No guaranteed outcome" in msg["content"]


def test_mock_csv_provider(tmp_path: Path):
    m = MockDataProvider().get_recent_candles("AAPL", "5m", 10)
    assert len(m) == 10
    p = tmp_path / "x.csv"
    p.write_text("timestamp,symbol,open,high,low,close,volume\n" + "\n".join([f"{r['timestamp'].isoformat()},AAPL,1,2,0.5,1.5,100" for r in m]), encoding="utf-8")
    c = CSVDataProvider(str(p)).get_recent_candles("AAPL", "5m", 5)
    assert len(c) == 5


def test_alert_throttle(tmp_path: Path):
    st = Storage(tmp_path / "a.db")
    sig = vwap_reclaim_long(add_indicators(sample_rows()), "AAPL", 1.0) or vwap_breakdown_short(add_indicators(sample_rows()), "AAPL", 1.0)
    th = AlertThrottler(st, 60, 1)
    ok, _ = th.allow(sig)
    assert ok
    st.insert_signal(sig)
    th.record(sig)
    ok2, _ = th.allow(sig)
    assert not ok2


def test_paper_execution(tmp_path: Path):
    st = Storage(tmp_path / "b.db")
    px = PaperExecutionProvider(st)
    px.place_order(OrderRequest(symbol="AAPL", side="buy", qty=1, limit_price=100, stop_loss=99, take_profit=101))
    px.process_candle("AAPL", 101.5, 99.8)
    assert len(st.fetch_closed_orders("paper")) == 1


def test_performance():
    s = summarize_trades([{"pnl": 1, "side": "buy", "symbol": "AAPL", "strategy_name": "s", "hold_minutes": 1}], "paper-trading")
    assert s["total_trades"] == 1


def test_backtest_and_lookahead(tmp_path: Path):
    cfg = AppConfig()
    out = tmp_path / "o.csv"
    trades, _ = run_backtest(cfg, "data/sample_ohlcv.csv", str(out), None)
    if trades:
        assert trades[0]["entry_time"] < trades[0]["exit_time"]


def test_live_safety_blocks():
    cfg = AppConfig(execution_mode=ExecutionMode.live)
    ok, _ = LiveSafety.validate(cfg, "AAPL", 0, 0)
    assert not ok

    cfg = AppConfig(execution_mode=ExecutionMode.live, enable_live_trading=True, i_understand_live_trading_risk=True, alpaca_base_url="https://api.alpaca.markets", allowed_symbols_whitelist=["AAPL"], max_open_positions=1, max_notional_exposure=1000)
    Path("KILL_SWITCH").write_text("1", encoding="utf-8")
    ok2, reason2 = LiveSafety.validate(cfg, "AAPL", 0, 0)
    Path("KILL_SWITCH").unlink(missing_ok=True)
    assert not ok2 and reason2 == "kill_switch_enabled"
    assert LiveSafety.validate(cfg, "MSFT", 0, 0)[1] == "symbol_not_whitelisted"
    assert LiveSafety.validate(cfg, "AAPL", 10, 0)[1] == "max_daily_loss_reached"
    assert LiveSafety.validate(cfg, "AAPL", 0, 1)[1] == "max_open_positions_reached"
