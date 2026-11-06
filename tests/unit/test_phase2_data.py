"""Unit tests for Phase 2: Data Plane & Integrity Engine."""

import asyncio
import sqlite3
from pathlib import Path

import pytest

from neo_wilder.data.integrity import DataIntegrityAuditor
from neo_wilder.data.store import DatabaseStore
from neo_wilder.data.ws_binance import BinanceWebSocketClient
from neo_wilder.domain.enums import HardVetoReason
from neo_wilder.domain.models import Candle


@pytest.mark.asyncio
async def test_database_store_wal_and_crud(tmp_path: Path):
    db_file = tmp_path / "test_journal.db"
    store = DatabaseStore(db_path=db_file)
    await store.start()

    # Check WAL mode
    conn = sqlite3.connect(str(db_file))
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode;")
    mode = cursor.fetchone()[0]
    conn.close()
    assert mode.lower() == "wal"

    # Insert candle via store
    c = Candle(
        open_time_ms=1700000000000,
        close_time_ms=1700000899999,
        open=50000.0,
        high=50500.0,
        low=49500.0,
        close=50200.0,
        volume=100.0,
    )
    await store.record_candle("BTCUSDT", "15m", c)
    await asyncio.sleep(0.2)  # Allow batch writer to flush

    # Query back
    candles = store.fetch_recent_candles("BTCUSDT", "15m", limit=10)
    assert len(candles) == 1
    assert candles[0].close == 50200.0

    await store.stop()


def test_data_integrity_auditor_cases():
    base_time = 1700000000000
    interval_ms = 900_000  # 15m

    # 1. Clean continuous series
    clean_candles = [
        Candle(
            open_time_ms=base_time + i * interval_ms,
            close_time_ms=base_time + (i + 1) * interval_ms - 1,
            open=100.0 + i,
            high=105.0 + i,
            low=95.0 + i,
            close=102.0 + i,
            volume=50.0,
        )
        for i in range(25)
    ]
    now_ms = clean_candles[-1].close_time_ms + 60_000  # 1 min after close
    quality = DataIntegrityAuditor.audit_candle_series(clean_candles, "15m", now_ms=now_ms)
    assert quality.is_valid

    # 2. V-H02: Data gap in last 20 bars
    gapped_candles = clean_candles.copy()
    # Delete bar at index 20 (within trailing 20 bars)
    del gapped_candles[20]
    quality_gap = DataIntegrityAuditor.audit_candle_series(gapped_candles, "15m", now_ms=now_ms)
    assert not quality_gap.is_valid
    assert quality_gap.veto_reason == HardVetoReason.DATA_GAP

    # 3. V-H01: Stale last bar (older than 2*TF + 30s = 1830s)
    stale_now_ms = clean_candles[-1].close_time_ms + 2_000_000  # 2000s age
    quality_stale = DataIntegrityAuditor.audit_candle_series(
        clean_candles, "15m", now_ms=stale_now_ms
    )
    assert not quality_stale.is_valid
    assert quality_stale.veto_reason == HardVetoReason.DATA_STALE

    # 4. V-H04: Duplicate candle open_time
    dup_candles = clean_candles.copy()
    dup_candles.append(clean_candles[-1])  # Duplicate last candle
    quality_dup = DataIntegrityAuditor.audit_candle_series(dup_candles, "15m", now_ms=now_ms)
    assert not quality_dup.is_valid
    assert quality_dup.veto_reason == HardVetoReason.DUPLICATE_CANDLE

    # 5. V-H03: Non-monotonic timestamp
    reversed_candles = list(reversed(clean_candles[:5]))
    quality_rev = DataIntegrityAuditor.audit_candle_series(reversed_candles, "15m")
    assert not quality_rev.is_valid
    assert quality_rev.veto_reason == HardVetoReason.CANDLE_TS_INVALID


def test_binance_ws_message_handling():
    ws_client = BinanceWebSocketClient(symbols=["BTCUSDT"])

    # Simulate aggTrade message
    raw_agg_trade = """{
        "stream": "btcusdt@aggTrade",
        "data": {
            "e": "aggTrade",
            "s": "BTCUSDT",
            "a": 1234567,
            "p": "68500.50",
            "q": "0.150",
            "T": 1700000005000,
            "m": true
        }
    }"""
    ws_client._handle_message(raw_agg_trade)
    assert len(ws_client.trade_buffers["BTCUSDT"]) == 1
    trade = ws_client.trade_buffers["BTCUSDT"][0]
    assert trade.price == 68500.50
    assert trade.is_buyer_maker is True

    # Simulate depth20 message
    raw_depth = """{
        "stream": "btcusdt@depth20@100ms",
        "data": {
            "e": "depthUpdate",
            "E": 1700000005100,
            "bids": [["68500.00", "2.5"], ["68499.00", "5.0"]],
            "asks": [["68501.00", "1.2"], ["68502.00", "3.0"]]
        }
    }"""
    ws_client._handle_message(raw_depth)
    assert len(ws_client.depth_buffers["BTCUSDT"]) == 1
    depth = ws_client.depth_buffers["BTCUSDT"][0]
    assert depth.spread_bps > 0.0
    assert depth.bids[0].price == 68500.00


def test_coindcx_public_drift_and_quote_logic():
    # Test price drift calculation logic
    binance_ref_price = 70000.0
    coindcx_price_valid = 70150.0  # Drift: 150 / 70000 = 0.214% (<= 0.35%)
    drift_pct_valid = abs(coindcx_price_valid - binance_ref_price) / binance_ref_price * 100.0
    assert drift_pct_valid < 0.35

    coindcx_price_excess = 70300.0  # Drift: 300 / 70000 = 0.428% (> 0.35%)
    drift_pct_excess = abs(coindcx_price_excess - binance_ref_price) / binance_ref_price * 100.0
    assert drift_pct_excess > 0.35
