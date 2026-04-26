from __future__ import annotations

import csv
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import json
from urllib import parse, request


class DataProvider(ABC):
    @abstractmethod
    def get_recent_candles(self, symbol: str, timeframe: str, limit: int) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def stream_candles(self, symbols: list[str], timeframe: str, callback: Callable[[str, list[dict]], None]) -> None:
        raise NotImplementedError


class MockDataProvider(DataProvider):
    def __init__(self, seed_price: float = 100.0) -> None:
        self.seed_price = seed_price

    def get_recent_candles(self, symbol: str, timeframe: str, limit: int) -> list[dict]:
        now = datetime.now(timezone.utc)
        rows = []
        price = self.seed_price
        for i in range(limit):
            ts = now - timedelta(minutes=(limit - i) * 5)
            price += (0.2 if i % 2 else -0.1)
            rows.append({"timestamp": ts, "symbol": symbol, "open": price - 0.2, "high": price + 0.4, "low": price - 0.4, "close": price, "volume": 1000 + 10 * i})
        return rows

    def stream_candles(self, symbols: list[str], timeframe: str, callback: Callable[[str, list[dict]], None]) -> None:
        for s in symbols:
            callback(s, self.get_recent_candles(s, timeframe, 100))


class CSVDataProvider(DataProvider):
    def __init__(self, csv_path: str) -> None:
        self.rows: list[dict] = []
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                self.rows.append({
                    "timestamp": datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00")),
                    "symbol": r["symbol"],
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": float(r["volume"]),
                })

    def get_recent_candles(self, symbol: str, timeframe: str, limit: int) -> list[dict]:
        sdf = [r for r in self.rows if r["symbol"] == symbol]
        return sdf[-limit:]

    def stream_candles(self, symbols: list[str], timeframe: str, callback: Callable[[str, list[dict]], None]) -> None:
        for s in symbols:
            callback(s, self.get_recent_candles(s, timeframe, 200))


class AlpacaDataProvider(DataProvider):
    def __init__(self, api_key: str, secret_key: str, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key}

    def get_recent_candles(self, symbol: str, timeframe: str, limit: int) -> list[dict]:
        url = f"{self.base_url}/v2/stocks/{symbol}/bars"
        q = parse.urlencode({"timeframe": timeframe, "limit": limit})
        req = request.Request(f"{url}?{q}", headers=self.headers)
        with request.urlopen(req, timeout=15) as resp:
            bars = json.loads(resp.read().decode("utf-8")).get("bars", [])
        return [{"timestamp": datetime.fromisoformat(b["t"].replace("Z", "+00:00")), "symbol": symbol, "open": b["o"], "high": b["h"], "low": b["l"], "close": b["c"], "volume": b["v"]} for b in bars]

    def stream_candles(self, symbols: list[str], timeframe: str, callback: Callable[[str, list[dict]], None]) -> None:
        for s in symbols:
            callback(s, self.get_recent_candles(s, timeframe, 200))
