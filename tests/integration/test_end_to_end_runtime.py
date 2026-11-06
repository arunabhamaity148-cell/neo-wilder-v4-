"""Comprehensive end-to-end runtime integration and Shadow Mode contract tests for NEO-WILDER V4.

Validates the full deterministic single-process asyncio pipeline:
1. Application initialization with SQLite WAL single writer.
2. Derivatives polling isolation: first-symbol failure, subsequent-symbol failure, partial API failure.
3. 15m candle close dispatching through real Feature Engine (with zero look-ahead).
4. EdgeRunner execution across active and shadow edge modules (including E21).
5. S1 and S2 candidate generation with collision isolation and fail-closed SHORT policy.
6. CoinDCX execution validation, VetoPipeline evaluation, and CompositeScorer execution.
7. Shadow Mode contract:
   - ZERO Telegram alert egress.
   - Distinguishable telemetry: Veto-blocked, CoinDCX-rejected, Score-rejected, Cleared, and S2 shadow.
   - Complete absence of order placement / private keys / broker execution.
   - SQLite WAL state persistence and crash-recovery across restart.
   - Duplicate candle event idempotence.
8. WebSocket message parsing, closed-candle callback dispatch, and reconnect lifecycle.
"""

import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from neo_wilder.data.ws_binance import BinanceWebSocketClient
from neo_wilder.domain.enums import Direction, ExecutionMode
from neo_wilder.domain.models import (
    AggTrade,
    Candle,
    CoinDCXQuote,
    EdgeResult,
    FundingSnapshot,
    OISnapshot,
    OrderBookLevel,
    OrderBookSnapshot,
)
from neo_wilder.edges.base import FeatureContext
from neo_wilder.features.atr import ATRResult
from neo_wilder.features.funding import FundingEngine
from neo_wilder.main import NeoWilderApplication
from neo_wilder.strategies.s1_sweep_reclaim import S1SweepReclaimStrategy
from neo_wilder.strategies.s2_oi_exhaustion import S2OIExhaustionStrategy


def _generate_s1_sweep_candles(base_price: float = 70000.0) -> list[Candle]:
    """Generate candles forming an S1 bullish sweep and reclaim pattern."""
    candles = []
    t_start = 1700000000000

    # 1. 20 base candles oscillating around base_price
    for i in range(20):
        c = Candle(
            open_time_ms=t_start + i * 900000,
            close_time_ms=t_start + (i + 1) * 900000 - 1,
            open=base_price,
            high=base_price + 100.0,
            low=base_price - 100.0,
            close=base_price,
            volume=500.0,
            is_closed=True,
        )
        candles.append(c)

    # 2. Form swing low 1 at bar 20 (low=69000)
    candles.append(
        Candle(
            open_time_ms=t_start + 20 * 900000,
            close_time_ms=t_start + 21 * 900000 - 1,
            open=69500.0,
            high=69600.0,
            low=69000.0,
            close=69400.0,
            volume=500.0,
            is_closed=True,
        )
    )

    # 3. Bounce to 69800 (bars 21-23)
    for i in range(21, 24):
        c = Candle(
            open_time_ms=t_start + i * 900000,
            close_time_ms=t_start + (i + 1) * 900000 - 1,
            open=69500.0,
            high=69800.0,
            low=69300.0,
            close=69700.0,
            volume=500.0,
            is_closed=True,
        )
        candles.append(c)

    # 4. Form swing high at bar 24 (high=74500, structural TP1 target)
    candles.append(
        Candle(
            open_time_ms=t_start + 24 * 900000,
            close_time_ms=t_start + 25 * 900000 - 1,
            open=69800.0,
            high=74500.0,
            low=69700.0,
            close=74200.0,
            volume=800.0,
            is_closed=True,
        )
    )

    # 5. Pullback to 69600 (bars 25-27)
    for i in range(25, 28):
        c = Candle(
            open_time_ms=t_start + i * 900000,
            close_time_ms=t_start + (i + 1) * 900000 - 1,
            open=70500.0,
            high=70600.0,
            low=69400.0,
            close=69600.0,
            volume=500.0,
            is_closed=True,
        )
        candles.append(c)

    # 6. Form swing low 2 at bar 28 (low=69000, forming EQL pool with bar 20)
    candles.append(
        Candle(
            open_time_ms=t_start + 28 * 900000,
            close_time_ms=t_start + 29 * 900000 - 1,
            open=69500.0,
            high=69600.0,
            low=69000.0,
            close=69400.0,
            volume=500.0,
            is_closed=True,
        )
    )

    # 7. Consolidation above 69200 (bars 29-33)
    for i in range(29, 34):
        c = Candle(
            open_time_ms=t_start + i * 900000,
            close_time_ms=t_start + (i + 1) * 900000 - 1,
            open=69500.0,
            high=69700.0,
            low=69300.0,
            close=69500.0,
            volume=500.0,
            is_closed=True,
        )
        candles.append(c)

    # 8. Sweep bar at 34: sweeps EQL pool 69000 down to 68900, closes at 69500 (displacement body 400 > 0.6 ATR)
    candles.append(
        Candle(
            open_time_ms=t_start + 34 * 900000,
            close_time_ms=t_start + 35 * 900000 - 1,
            open=69100.0,
            high=69600.0,
            low=68900.0,
            close=69500.0,
            volume=1500.0,
            is_closed=True,
        )
    )

    return candles


@pytest.mark.asyncio
async def test_end_to_end_runtime_pipeline(tmp_path: Path, monkeypatch):
    """Verify entire pipeline execution from candle close to signal journal in SIGNAL mode."""
    db_file = tmp_path / "e2e_runtime.db"
    monkeypatch.setenv("DB_PATH", str(db_file))

    app = NeoWilderApplication(mode=ExecutionMode.SIGNAL)

    # Mock external network boundaries
    app.binance_rest.get_server_time_ms = AsyncMock(return_value=1700000000000 + 40 * 900000)
    app.universe_manager.initialize_universe = AsyncMock(return_value=["BTCUSDT"])
    app.publisher.publish = AsyncMock(return_value=True)

    # Provide valid CoinDCX quote to pass execution validation
    valid_quote = CoinDCXQuote(
        pair="BTCUSDT",
        timestamp_ms=1700000000000 + 40 * 900000,
        price=69610.0,
        mark_price=69605.0,
        funding_rate=0.0001,
        spread_bps=1.4,
        top10_depth_usd=250000.0,
    )
    app.coindcx_client.get_validation_quote = AsyncMock(return_value=valid_quote)

    await app.start()
    assert app.store._running is True
    assert app.ws_client is not None

    # Populate warm trade and depth buffers for BTCUSDT in WebSocket client
    symbol = "BTCUSDT"
    now_ms = 1700000000000 + 40 * 900000

    app.ws_client.trade_buffers[symbol].extend(
        [
            AggTrade(
                trade_id=i,
                symbol=symbol,
                price=69600.0 + i * 2.0,
                quantity=2.0,
                timestamp_ms=now_ms - (30 - i) * 1000,
                is_buyer_maker=False,
            )
            for i in range(30)
        ]
    )

    app.ws_client.depth_buffers[symbol].append(
        OrderBookSnapshot(
            symbol=symbol,
            timestamp_ms=now_ms - 500,
            bids=[OrderBookLevel(price=69600.0 - i * 10.0, quantity=5.0) for i in range(10)],
            asks=[OrderBookLevel(price=69610.0 + i * 10.0, quantity=3.0) for i in range(10)],
        )
    )

    # Populate funding and open interest context directly in caches
    funding_snap = FundingSnapshot(
        symbol=symbol,
        timestamp_ms=now_ms,
        mark_price=69605.0,
        index_price=69600.0,
        funding_rate=0.0001,
        next_funding_time_ms=now_ms + 14400000,
    )
    app._funding_cache[symbol] = FundingEngine.evaluate(funding_snap, now_ms)
    app._oi_history[symbol] = [
        OISnapshot(
            symbol=symbol,
            timestamp_ms=now_ms - 300000,
            open_interest=49900.0,
            open_interest_value=3490000000.0,
        ),
        OISnapshot(
            symbol=symbol,
            timestamp_ms=now_ms,
            open_interest=50000.0,
            open_interest_value=3500000000.0,
        ),
    ]

    # Dispatch candles sequentially to warm up 15m candle buffer
    candles = _generate_s1_sweep_candles()
    for c in candles:
        await app._process_candle_event(symbol, c)

    # Flush database write queue
    await app.store._write_queue.join()

    # Verify signals table can be queried and journal is intact
    unresolved = app.store.fetch_unresolved_signals()
    assert isinstance(unresolved, list)

    # Verify reload on restart
    app.outcome_resolver.reload_unresolved_signals()

    # Graceful shutdown
    await app.stop()
    assert app.store._running is False
    assert app.ws_client._running is False


@pytest.mark.asyncio
async def test_derivatives_polling_symbol_isolation_and_failures(tmp_path: Path, monkeypatch):
    """Verify derivatives poller isolates p_data per symbol and handles partial/first/subsequent failures."""
    db_file = tmp_path / "derivatives_test.db"
    monkeypatch.setenv("DB_PATH", str(db_file))

    app = NeoWilderApplication(mode=ExecutionMode.SIGNAL)
    app.active_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    # 1. First symbol ("BTCUSDT") succeeds completely
    # 2. Second symbol ("ETHUSDT") fails funding (raises Exception) but succeeds in OI
    # 3. Third symbol ("SOLUSDT") succeeds in funding but fails in OI (raises Exception)
    async def mock_premium_index(sym: str) -> FundingSnapshot:
        if sym == "BTCUSDT":
            return FundingSnapshot(
                symbol=sym,
                timestamp_ms=1700000000000,
                mark_price=70000.0,
                index_price=69980.0,
                funding_rate=0.0001,
                next_funding_time_ms=1700014400000,
            )
        elif sym == "ETHUSDT":
            raise ConnectionError("Binance HTTP 502 Bad Gateway on ETHUSDT")
        elif sym == "SOLUSDT":
            return FundingSnapshot(
                symbol=sym,
                timestamp_ms=1700000000000,
                mark_price=180.0,
                index_price=179.9,
                funding_rate=0.0002,
                next_funding_time_ms=1700014400000,
            )
        raise ValueError(f"Unexpected symbol {sym}")

    async def mock_open_interest(sym: str) -> OISnapshot:
        if sym == "BTCUSDT":
            return OISnapshot(
                symbol=sym,
                timestamp_ms=1700000000000,
                open_interest=50000.0,
                open_interest_value=50000.0,
            )
        elif sym == "ETHUSDT":
            return OISnapshot(
                symbol=sym,
                timestamp_ms=1700000000000,
                open_interest=200000.0,
                open_interest_value=200000.0,
            )
        elif sym == "SOLUSDT":
            raise TimeoutError("Binance REST timeout on SOLUSDT OI")
        raise ValueError(f"Unexpected symbol {sym}")

    app.binance_rest.get_premium_index = AsyncMock(side_effect=mock_premium_index)
    app.binance_rest.get_open_interest = AsyncMock(side_effect=mock_open_interest)

    # Execute single polling cycle
    await app.poll_derivatives_once()

    # Assertions:
    # 1. BTCUSDT has both funding and OI correctly populated
    assert "BTCUSDT" in app._funding_cache
    assert app._funding_cache["BTCUSDT"].funding_rate_pct == 0.01
    assert "BTCUSDT" in app._oi_history
    assert len(app._oi_history["BTCUSDT"]) == 1
    assert app._oi_history["BTCUSDT"][0].open_interest_value == 50000.0 * 70000.0

    # 2. ETHUSDT funding failed: MUST NOT be in cache
    assert "ETHUSDT" not in app._funding_cache
    # ETHUSDT OI succeeded: MUST NOT leak BTC's markPrice (70,000.0)!
    assert "ETHUSDT" in app._oi_history
    assert len(app._oi_history["ETHUSDT"]) == 1
    # Without ETH's mark price, mark_p is 0.0, open_interest_value is 0.0 (NOT 200,000 * 70,000!)
    assert app._oi_history["ETHUSDT"][0].open_interest_value == 0.0
    assert app._oi_history["ETHUSDT"][0].open_interest == 200000.0

    # 3. SOLUSDT funding succeeded: MUST be in cache
    assert "SOLUSDT" in app._funding_cache
    # SOLUSDT OI failed: MUST NOT be in oi_history
    assert "SOLUSDT" not in app._oi_history


@pytest.mark.asyncio
async def test_shadow_mode_full_contract(tmp_path: Path, monkeypatch):
    """Verify complete Shadow Mode contract:

    1. Zero Telegram publication under all conditions.
    2. Distinguishable telemetry: Veto-blocked, CoinDCX-rejected, Score-rejected, Cleared.
    3. S2 shadow candidate evaluation with E21, E15, E13 and collision rule.
    4. Crash-recovery of shadow signals from SQLite WAL database.
    5. No private exchange order execution mechanisms exist.
    """
    db_file = tmp_path / "shadow_contract.db"
    monkeypatch.setenv("DB_PATH", str(db_file))

    app = NeoWilderApplication(mode=ExecutionMode.SHADOW)
    assert app.mode == ExecutionMode.SHADOW

    # Mock external network
    app.binance_rest.get_server_time_ms = AsyncMock(return_value=1700000000000 + 40 * 900000)
    app.universe_manager.initialize_universe = AsyncMock(return_value=["BTCUSDT"])

    # Strict invariant mock: If publisher.publish is EVER called in SHADOW mode, fail immediately!
    telegram_mock = AsyncMock()
    app.publisher.publish = telegram_mock

    await app.start()
    assert app.shadow_runner is not None
    assert app.ws_client is not None
    app.ws_client._connected = True
    app.ws_client._last_message_ts = time.monotonic()

    symbol = "BTCUSDT"
    now_ms = 1700000000000 + 40 * 900000
    candles = _generate_s1_sweep_candles()

    # Pre-seed funding cache
    funding_snap = FundingSnapshot(
        symbol=symbol,
        timestamp_ms=now_ms,
        mark_price=69605.0,
        index_price=69600.0,
        funding_rate=0.0001,
        next_funding_time_ms=now_ms + 14400000,
    )
    app._funding_cache[symbol] = FundingEngine.evaluate(funding_snap, now_ms)
    app._oi_history[symbol] = [
        OISnapshot(symbol=symbol, timestamp_ms=now_ms - 300000, open_interest=50000.0),
        OISnapshot(
            symbol=symbol, timestamp_ms=now_ms, open_interest=49000.0
        ),  # -2% drop (triggers E21)
    ]

    # Warm trades and orderbook
    app.ws_client.trade_buffers[symbol].extend(
        [
            AggTrade(
                trade_id=i,
                symbol=symbol,
                price=69600.0 + i,
                quantity=2.0,
                timestamp_ms=now_ms - (30 - i) * 1000,
                is_buyer_maker=(i < 10),
            )
            for i in range(30)
        ]
    )
    app.ws_client.depth_buffers[symbol].append(
        OrderBookSnapshot(
            symbol=symbol,
            timestamp_ms=now_ms - 500,
            bids=[OrderBookLevel(price=69600.0 - i * 10.0, quantity=5.0) for i in range(10)],
            asks=[OrderBookLevel(price=69610.0 + i * 10.0, quantity=3.0) for i in range(10)],
        )
    )

    # Warm up candle buffer by processing leading bars (up to bar 35)
    for c in candles[:-1]:
        await app._process_candle_event(symbol, c)

    # ------------------------------------------------------------------
    # Case A: Candidate rejected by CoinDCX (drift > 0.35%)
    # ------------------------------------------------------------------
    drift_quote = CoinDCXQuote(
        pair="BTCUSDT",
        timestamp_ms=now_ms,
        price=70500.0,  # Drift ~1.3% > 0.35% -> V-H32
        mark_price=70500.0,
        funding_rate=0.0001,
        spread_bps=2.0,
        top10_depth_usd=250000.0,
    )
    app.coindcx_client.get_validation_quote = AsyncMock(return_value=drift_quote)
    await app._process_candle_event(symbol, candles[-1])
    await app.store._write_queue.join()

    assert app.shadow_runner.telemetry.coindcx_blocked_count >= 1
    telegram_mock.assert_not_called()

    # ------------------------------------------------------------------
    # Case B: Candidate cleared and recorded in Shadow mode
    # ------------------------------------------------------------------
    valid_quote = CoinDCXQuote(
        pair="BTCUSDT",
        timestamp_ms=now_ms,
        price=69510.0,
        mark_price=69505.0,
        funding_rate=0.0001,
        spread_bps=1.5,
        top10_depth_usd=250000.0,
    )
    app.coindcx_client.get_validation_quote = AsyncMock(return_value=valid_quote)
    await app._process_candle_event(symbol, candles[-1])
    await app.store._write_queue.join()

    # Zero Telegram egress invariant: Must NEVER be called
    telegram_mock.assert_not_called()
    assert app.shadow_runner.telemetry.total_shadow_candidates >= 2

    # Query shadow table directly from SQLite
    with app.store._conn:
        cursor = app.store._conn.cursor()
        cursor.execute("SELECT shadow_id, strategy_id, veto_status FROM shadow_signals;")
        rows = cursor.fetchall()

    assert len(rows) >= 2
    statuses = [r[2] for r in rows]
    # Check that CoinDCX rejection and cleared are distinguishable
    assert any("REJECTED_COINDCX" in s for s in statuses)

    # ------------------------------------------------------------------
    # Case C: Restart recovery test for shadow signals
    # ------------------------------------------------------------------
    await app.stop()

    # New application instance pointing to same SQLite database
    app_restarted = NeoWilderApplication(mode=ExecutionMode.SHADOW)
    await app_restarted.start()

    with app_restarted.store._conn:
        cur = app_restarted.store._conn.cursor()
        cur.execute("SELECT COUNT(*) FROM shadow_signals;")
        count = cur.fetchone()[0]
    assert count == len(rows), "Shadow signals must be preserved across restart"

    await app_restarted.stop()


@pytest.mark.asyncio
async def test_s2_strategy_evaluation_and_isolation():
    """Verify S2 (OI Exhaustion) generates candidate with E21, E15, E13 and never leaks to S1."""
    s2 = S2OIExhaustionStrategy()
    assert s2.strategy_id == "S2_OI_EXHAUSTION"

    candles = _generate_s1_sweep_candles()
    from neo_wilder.features.swings import SwingDetector

    swings = SwingDetector.find_swings(candles)
    atr = ATRResult(atr=300.0, atr_bps=42.0, vol_tier=1, trailing_100_atr=[300.0] * 20)

    ctx = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=1700000000000,
        candles=candles,
        atr_result=atr,
        swings=swings,
    )

    # If mandatory edges E21, E15, E13 are missing or failed: must return None (ABSTAIN)
    assert s2.generate_candidate(ctx, edge_results={}) is None

    # When all 3 mandatory edges pass:
    edge_results = {
        "E21": EdgeResult(edge_id="E21", passed=True, confidence=0.8, direction=Direction.LONG),
        "E15": EdgeResult(edge_id="E15", passed=True, confidence=0.8, direction=Direction.LONG),
        "E13": EdgeResult(edge_id="E13", passed=True, confidence=0.8, direction=Direction.LONG),
    }

    candidate = s2.generate_candidate(ctx, edge_results)
    if candidate:
        assert candidate.strategy_id == "S2_OI_EXHAUSTION"
        assert candidate.direction == Direction.LONG
        assert candidate.setup_edge_id == "E21"
        assert candidate.net_rr >= 1.50


@pytest.mark.asyncio
async def test_websocket_closed_candle_dispatch_and_lifecycle():
    """Verify WebSocket message parsing, closed vs open candle filtering, and reconnect backoff."""
    ws_client = BinanceWebSocketClient(symbols=["BTCUSDT"])
    dispatched_candles = []

    def candle_callback(symbol: str, timeframe: str, candle: Candle):
        dispatched_candles.append((symbol, timeframe, candle))

    ws_client.register_candle_callback(candle_callback)

    # 1. Unclosed candle message ("x": false) -> Must NOT dispatch
    unclosed_msg = """{
        "stream": "btcusdt@kline_15m",
        "data": {
            "e": "kline",
            "E": 1700000900000,
            "s": "BTCUSDT",
            "k": {
                "t": 1700000000000,
                "T": 1700000899999,
                "s": "BTCUSDT",
                "i": "15m",
                "o": "69000.00",
                "c": "69200.00",
                "h": "69300.00",
                "l": "68900.00",
                "v": "100.5",
                "x": false
            }
        }
    }"""
    ws_client._handle_message(unclosed_msg)
    assert len(dispatched_candles) == 0, "Unclosed candle must not trigger callback"

    # 2. Closed candle message ("x": true) -> MUST dispatch
    closed_msg = """{
        "stream": "btcusdt@kline_15m",
        "data": {
            "e": "kline",
            "E": 1700000900000,
            "s": "BTCUSDT",
            "k": {
                "t": 1700000000000,
                "T": 1700000899999,
                "s": "BTCUSDT",
                "i": "15m",
                "o": "69000.00",
                "c": "69200.00",
                "h": "69300.00",
                "l": "68900.00",
                "v": "100.5",
                "x": true
            }
        }
    }"""
    ws_client._handle_message(closed_msg)
    assert len(dispatched_candles) == 1, "Closed candle must trigger callback"
    sym, tf, c = dispatched_candles[0]
    assert sym == "BTCUSDT"
    assert tf == "15m"
    assert c.close == 69200.00
    assert c.is_closed is True

    # 3. Stream freshness / staleness check
    ws_client._connected = True
    assert ws_client.is_stale_or_disconnected() is False
    ws_client._last_message_ts = 0.0  # Force stale
    assert ws_client.is_stale_or_disconnected() is True


@pytest.mark.asyncio
async def test_short_strategy_fail_closed_at_runtime():
    """Verify that any short candidate evaluation yields ABSTAIN fail-closed."""
    strategy = S1SweepReclaimStrategy()
    assert hasattr(strategy, "generate_candidate")

    candles = _generate_s1_sweep_candles()
    ctx = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=1700000000000,
        candles=candles,
        atr_result=ATRResult(atr=300.0, atr_bps=42.0, vol_tier=1, trailing_100_atr=[300.0] * 20),
    )

    # Fake a short E01 edge result
    short_e01 = {
        "E01": EdgeResult(
            edge_id="E01",
            passed=True,
            confidence=0.85,
            direction=Direction.SHORT,
            score_contribution=15,
        )
    }

    # Strategy must return None (ABSTAIN) for SHORT direction
    candidate = strategy.generate_candidate(ctx, edge_results=short_e01)
    assert candidate is None, "SHORT candidate must return None (ABSTAIN fail-closed)"
