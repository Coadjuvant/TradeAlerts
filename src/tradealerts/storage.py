from __future__ import annotations

import json
from dataclasses import asdict
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tradealerts.models import Signal


class Storage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self.conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                symbol TEXT,
                direction TEXT,
                strategy_name TEXT,
                signature TEXT UNIQUE,
                payload TEXT
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY,
                symbol TEXT,
                signal_signature TEXT,
                alert_date TEXT,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY,
                order_id TEXT,
                mode TEXT,
                symbol TEXT,
                side TEXT,
                qty REAL,
                price REAL,
                stop_loss REAL,
                take_profit REAL,
                status TEXT,
                created_at TEXT,
                closed_at TEXT,
                pnl REAL DEFAULT 0,
                hold_minutes REAL DEFAULT 0,
                strategy_name TEXT
            );
            """
        )
        self.conn.commit()

    def signal_signature(self, signal: Signal) -> str:
        ts = signal.timestamp.isoformat(timespec="minutes")
        return f"{signal.symbol}:{signal.direction}:{signal.strategy_name}:{ts}:{round(signal.current_price,4)}"

    def insert_signal(self, signal: Signal) -> int | None:
        sig = self.signal_signature(signal)
        payload = json.dumps(asdict(signal), default=str)
        cur = self.conn.cursor()
        try:
            cur.execute(
                "INSERT INTO signals(timestamp,symbol,direction,strategy_name,signature,payload) VALUES (?,?,?,?,?,?)",
                (signal.timestamp.isoformat(), signal.symbol, signal.direction, signal.strategy_name, sig, payload),
            )
            self.conn.commit()
            return int(cur.lastrowid)
        except sqlite3.IntegrityError:
            return None

    def is_duplicate_signal(self, signal: Signal) -> bool:
        sig = self.signal_signature(signal)
        cur = self.conn.execute("SELECT 1 FROM signals WHERE signature=?", (sig,))
        return cur.fetchone() is not None

    def log_alert(self, symbol: str, signal_signature: str) -> None:
        now = datetime.now(timezone.utc)
        self.conn.execute(
            "INSERT INTO alerts(symbol,signal_signature,alert_date,created_at) VALUES (?,?,?,?)",
            (symbol, signal_signature, now.date().isoformat(), now.isoformat()),
        )
        self.conn.commit()

    def count_alerts_today(self, symbol: str) -> int:
        today = datetime.now(timezone.utc).date().isoformat()
        cur = self.conn.execute("SELECT count(*) c FROM alerts WHERE symbol=? AND alert_date=?", (symbol, today))
        return int(cur.fetchone()["c"])

    def last_alert_time(self, symbol: str) -> datetime | None:
        cur = self.conn.execute("SELECT created_at FROM alerts WHERE symbol=? ORDER BY id DESC LIMIT 1", (symbol,))
        row = cur.fetchone()
        if not row:
            return None
        return datetime.fromisoformat(row["created_at"])

    def log_order(self, record: dict[str, Any]) -> None:
        cols = ",".join(record.keys())
        marks = ",".join(["?"] * len(record))
        self.conn.execute(f"INSERT INTO orders({cols}) VALUES ({marks})", tuple(record.values()))
        self.conn.commit()

    def update_order_close(self, order_id: str, status: str, pnl: float, hold_minutes: float) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE orders SET status=?, pnl=?, hold_minutes=?, closed_at=? WHERE order_id=?",
            (status, pnl, hold_minutes, now, order_id),
        )
        self.conn.commit()

    def fetch_closed_orders(self, mode: str | None = None) -> list[sqlite3.Row]:
        if mode:
            cur = self.conn.execute("SELECT * FROM orders WHERE closed_at IS NOT NULL AND mode=?", (mode,))
        else:
            cur = self.conn.execute("SELECT * FROM orders WHERE closed_at IS NOT NULL")
        return list(cur.fetchall())

    def fetch_all_orders(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM orders ORDER BY id"))
