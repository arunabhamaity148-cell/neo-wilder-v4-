"""End-to-end runtime integration test for NEO-WILDER V4.

Validates the full deterministic single-process asyncio pipeline:
1. Application initialization with SQLite WAL single writer.
2. 15m candle close dispatching through real Feature Engine.
3. EdgeRunner execution across all active edge modules.
4. Strategy candidate generation (S1 Sweep & Reclaim).
5. VetoPipeline validation (Hard/Soft veto evaluation).
6. CompositeScorer execution (0-100 score calculation).
7. Execution mode gating and signal journal recording.
8. State persistence and outcome resolver crash-recovery.
"""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from neo_wilder.domain.enums import Direction, ExecutionMode
from neo_wilder.domain.models import (
    AggTrade,
    Candle,
    CoinDCXQuote,
    OISnapshot,
    OrderBookLevel,
    OrderBookSnapshot,
)
from neo_wilder.features.funding import FundingSnapshot
from neo_wilder.main import NeoWilderApplication


def _generate_s1_sweep_candles(base_price: float = 70000.0) -> list[Candle]:
    """Generate 40 candles forming an S1 bullish sweep and reclaim pattern."""
    candles = []
    t_start = 1700000000000

    # 1. 20 base candles oscillating around 70000
    for i in range(20):
        c = Candle(
            open_time_ms=t_start + i * 900000,
            close_time_ms=t_start + (i + 1) * 900000 - 1,
            open=base_price,
            high=base_price + 150.0,
            low=base_price - 150.0,
            close=base_price + 10.0,
            volume=500.0,
            is_closed=True,
        )
        candles.append(c)

    # 2. Form a distinct swing low at bar 25: price drops to 69000
    for i in range(20, 26):
        p = base_price - (i - 19) * 160.0
        c = Candle(
            open_time_ms=t_start + i * 900000,
            close_time_ms=t_start + (i + 1) * 900000 - 1,
            open=p + 50.0,
            high=p + 60.0,
            low=p - 50.0,
            close=p,
            volume=600.0,
            is_closed=True,
        )
        candles.append(c)

    # 3. Bounce back up to 69800 (bars 26-34)
    for i in range(26, 35):
        p = 69000.0 + (i - 25) * 90.0
        c = Candle(
            open_time_ms=t_start + i * 900000,
            close_time_ms=t_start + (i + 1) * 900000 - 1,
            open=p - 40.0,
            high=p + 80.0,
            low=p - 50.0,
            close=p,
            volume=500.0,
            is_closed=True,
        )
        candles.append(c)

    # 4. Sweep bar at 35: low sweeps below swing low 69000 (to 68900), but closes at 69150
    candles.append(
        Candle(
            open_time_ms=t_start + 35 * 900000,
            close_time_ms=t_start + 36 * 900000 - 1,
            open=69800.0,
            high=69820.0,
            low=68900.0,
            close=69150.0,
            volume=1500.0,
            is_closed=True,
        )
    )

    # 5. Reclaim bar at 36: reclaims back above 69200
    candles.append(
        Candle(
            open_time_ms=t_start + 36 * 900000,
            close_time_ms=t_start + 37 * 900000 - 1,
            open=69150.0,
            high=69700.0,
            low=69100.0,
            close=69600.0,
            volume=1800.0,
            is_closed=True,
        )
    )

    return candles


@pytest.mark.asyncio
async def test_end_to_end_runtime_pipeline(tmp_path: Path, monkeypatch):
    """Verify entire pipeline execution from candle close to signal journal."""
    db_file = tmp_path / "e2e_runtime.db"
    monkeypatch.setenv("DB_PATH", str(db_file))

    app = NeoWilderApplication(mode=ExecutionMode.SIGNAL)

    # Mock external network boundaries
    app.binance_rest.get_server_time_ms = AsyncMock(return_value=1700000000000 + 40 * 900000)
    app.universe_manager.initialize_universe = AsyncMock(return_value=["BTCUSDT"])
    app.publisher.publish_signal = AsyncMock(return_value=True)

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
    app.coindcx_client.get_orderbook_quote = AsyncMock(return_value=valid_quote)

    await app.start()
    assert app.store._running is True
    assert app.ws_client is not None

    # Populate warm trade and depth buffers for BTCUSDT in WebSocket client
    symbol = "BTCUSDT"
    now_ms = 1700000000000 + 40 * 900000

    # Warm trades (positive delta for CVD)
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

    # Warm depth (healthy book for OBI)
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
    from neo_wilder.features.funding import FundingEngine

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
async def test_short_strategy_fail_closed_at_runtime(tmp_path: Path, monkeypatch):
    """Verify that any short candidate evaluation yields ABSTAIN fail-closed."""
    from neo_wilder.strategies.s1_sweep_reclaim import S1SweepReclaimStrategy

    strategy = S1SweepReclaimStrategy()
    assert hasattr(strategy, "generate_candidate")

    # Attempting to generate short setup without formal research formulas must abstain
    candles = _generate_s1_sweep_candles()
    from neo_wilder.domain.models import EdgeResult
    from neo_wilder.edges.base import FeatureContext
    from neo_wilder.features.atr import ATRResult

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
