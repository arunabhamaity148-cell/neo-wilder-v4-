"""SQLite WAL persistence manager for NEO-WILDER V4.

Operates with a single asynchronous writer loop over an asyncio.Queue,
enforcing PRAGMA journal_mode=WAL and PRAGMA synchronous=NORMAL.
"""

import asyncio
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from neo_wilder.domain.models import Candle

logger = logging.getLogger(__name__)


class DatabaseStore:
    """Thread-safe SQLite store with single-writer async loop."""

    def __init__(self, db_path: Path | str = "data/neo_wilder_journal.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._write_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._writer_task: Optional[asyncio.Task] = None
        self._running = False
        self._conn: Optional[sqlite3.Connection] = None

    def initialize_schema(self):
        """Initialize SQLite WAL tables synchronously at startup."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA cache_size=-20000;")  # ~20 MB cache

            with conn:
                # Candles table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS candles (
                        symbol TEXT NOT NULL,
                        timeframe TEXT NOT NULL,
                        open_time_ms INTEGER NOT NULL,
                        close_time_ms INTEGER NOT NULL,
                        open REAL NOT NULL,
                        high REAL NOT NULL,
                        low REAL NOT NULL,
                        close REAL NOT NULL,
                        volume REAL NOT NULL,
                        PRIMARY KEY (symbol, timeframe, open_time_ms)
                    );
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_candles_time ON candles(symbol, timeframe, close_time_ms);"
                )

                # Signals table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS signals (
                        signal_id TEXT PRIMARY KEY,
                        created_at_utc TEXT NOT NULL,
                        symbol_binance TEXT NOT NULL,
                        symbol_coindcx TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        strategy_id TEXT NOT NULL,
                        reference_price REAL NOT NULL,
                        entry_zone_low REAL NOT NULL,
                        entry_zone_high REAL NOT NULL,
                        stop_loss REAL NOT NULL,
                        tp1 REAL NOT NULL,
                        tp2 REAL,
                        net_rr REAL NOT NULL,
                        score_0_100 INTEGER NOT NULL,
                        regime TEXT NOT NULL,
                        veto_status TEXT NOT NULL,
                        payload_json TEXT NOT NULL
                    );
                """)

                # Journal Fills table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS fills (
                        fill_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        signal_id TEXT NOT NULL,
                        fill_price REAL NOT NULL,
                        fill_size REAL NOT NULL,
                        timestamp_utc TEXT NOT NULL,
                        FOREIGN KEY (signal_id) REFERENCES signals(signal_id)
                    );
                """)

                # Signal Outcomes table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS outcomes (
                        signal_id TEXT PRIMARY KEY,
                        resolved_status TEXT NOT NULL, -- TP1_HIT, SL_HIT, EXPIRED, MISSED
                        exit_price REAL,
                        realized_r REAL,
                        resolution_time_utc TEXT,
                        FOREIGN KEY (signal_id) REFERENCES signals(signal_id)
                    );
                """)

                # System Health Metrics table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS health_metrics (
                        timestamp_ms INTEGER PRIMARY KEY,
                        rss_mb REAL NOT NULL,
                        clock_skew_ms REAL NOT NULL,
                        event_loop_lag_ms REAL NOT NULL
                    );
                """)
        finally:
            conn.close()

    async def start(self):
        """Start background writer task."""
        self.initialize_schema()
        self._conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        self._running = True
        self._writer_task = asyncio.create_task(self._writer_loop())

    async def stop(self):
        """Flush remaining queue and stop writer."""
        self._running = False
        if self._writer_task:
            await self._write_queue.join()
            self._writer_task.cancel()
            try:
                await self._writer_task
            except asyncio.CancelledError:
                pass
        if self._conn:
            self._conn.close()

    async def record_candle(self, symbol: str, timeframe: str, candle: Candle):
        """Queue candle write."""
        await self._write_queue.put(
            (
                "INSERT OR REPLACE INTO candles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);",
                (
                    symbol,
                    timeframe,
                    candle.open_time_ms,
                    candle.close_time_ms,
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                    candle.volume,
                ),
            )
        )

    async def record_signal(self, signal_dict: Dict[str, Any], payload_json: str):
        """Queue signal write."""
        await self._write_queue.put(
            (
                """
            INSERT OR REPLACE INTO signals VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            );
            """,
                (
                    signal_dict["signal_id"],
                    signal_dict["created_at_utc"],
                    signal_dict["symbol_binance"],
                    signal_dict["symbol_coindcx"],
                    signal_dict["direction"],
                    signal_dict["strategy_id"],
                    signal_dict["reference_price"],
                    signal_dict["entry_zone_low"],
                    signal_dict["entry_zone_high"],
                    signal_dict["stop_loss"],
                    signal_dict["tp1"],
                    signal_dict.get("tp2"),
                    signal_dict["net_rr"],
                    signal_dict["score_0_100"],
                    signal_dict["regime"],
                    signal_dict["veto_status"],
                    payload_json,
                ),
            )
        )

    async def record_fill(self, signal_id: str, price: float, size: float, timestamp_utc: str):
        """Queue manual /fill record."""
        await self._write_queue.put(
            (
                "INSERT INTO fills (signal_id, fill_price, fill_size, timestamp_utc) VALUES (?, ?, ?, ?);",
                (signal_id, price, size, timestamp_utc),
            )
        )

    async def record_outcome(
        self,
        signal_id: str,
        resolved_status: str,
        exit_price: Optional[float],
        realized_r: Optional[float],
        resolution_time_utc: str,
    ):
        """Queue signal resolution outcome write."""
        await self._write_queue.put(
            (
                """
                INSERT OR REPLACE INTO outcomes (
                    signal_id, resolved_status, exit_price, realized_r, resolution_time_utc
                ) VALUES (?, ?, ?, ?, ?);
                """,
                (signal_id, resolved_status, exit_price, realized_r, resolution_time_utc),
            )
        )

    async def record_health(
        self, timestamp_ms: int, rss_mb: float, skew_ms: float, loop_lag_ms: float
    ):
        """Queue health metric write."""
        await self._write_queue.put(
            (
                "INSERT INTO health_metrics VALUES (?, ?, ?, ?);",
                (timestamp_ms, rss_mb, skew_ms, loop_lag_ms),
            )
        )

    async def _writer_loop(self):
        """Single writer asynchronous loop."""
        batch = []
        while self._running or not self._write_queue.empty():
            try:
                # Wait for next item or timeout to flush batch
                try:
                    item = await asyncio.wait_for(self._write_queue.get(), timeout=0.1)
                    batch.append(item)
                except asyncio.TimeoutError:
                    pass

                # Drain available items up to batch size 100
                while len(batch) < 100 and not self._write_queue.empty():
                    batch.append(self._write_queue.get_nowait())

                if batch and self._conn:
                    with self._conn:
                        for sql, params in batch:
                            self._conn.execute(sql, params)
                    for _ in batch:
                        self._write_queue.task_done()
                    batch.clear()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in DatabaseStore writer loop: {e}", exc_info=True)
                await asyncio.sleep(0.05)

    def fetch_recent_candles(self, symbol: str, timeframe: str, limit: int = 100) -> List[Candle]:
        """Synchronously query recent candles for initialization."""
        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT open_time_ms, close_time_ms, open, high, low, close, volume
                FROM candles
                WHERE symbol = ? AND timeframe = ?
                ORDER BY open_time_ms DESC
                LIMIT ?;
                """,
                (symbol, timeframe, limit),
            )
            rows = cursor.fetchall()
            candles = [
                Candle(
                    open_time_ms=r[0],
                    close_time_ms=r[1],
                    open=r[2],
                    high=r[3],
                    low=r[4],
                    close=r[5],
                    volume=r[6],
                )
                for r in reversed(rows)
            ]
            return candles
        finally:
            conn.close()
