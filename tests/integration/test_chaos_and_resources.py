"""Integration tests for Phase 11: Chaos, Replay, and Resource Stress Testing."""

import gc
import time
from pathlib import Path

import numpy as np
import pytest

from neo_wilder.clock import SystemClock
from neo_wilder.data.integrity import DataIntegrityAuditor
from neo_wilder.data.ws_binance import BinanceWebSocketClient
from neo_wilder.domain.enums import Direction, HardVetoReason, RegimeState
from neo_wilder.domain.models import AggTrade, Candidate, Candle, EdgeResult
from neo_wilder.edges.base import FeatureContext
from neo_wilder.edges.registry import EdgeRegistry
from neo_wilder.features.atr import ATREngine
from neo_wilder.features.regime import RegimeClassifier
from neo_wilder.observability.health import TARGET_CEILING_RSS_MB, SystemHealthMonitor
from neo_wilder.observability.watchdog import DegradationLevel, ProcessWatchdog
from neo_wilder.scoring.groups import CompositeScorer
from neo_wilder.vetoes.governor import PortfolioGovernor
from neo_wilder.vetoes.hard import HardVetoEvaluator


def test_feed_kill_and_watchdog_escalation():
    """Verify feed stall causes watchdog emergency halt and triggers V-H10 fail-closed block."""
    dog = ProcessWatchdog(interval_seconds=5.0, max_misses=3)
    t0 = 1000.0
    dog.last_heartbeat = t0

    # Step 1: Normal heartbeat
    assert dog.evaluate_liveness(t0 + 2.0) == DegradationLevel.NORMAL
    assert not dog.is_halted

    # Step 2: Feed dies! 20 seconds elapse without beat (> 3 missed 5s ticks)
    lvl = dog.evaluate_liveness(t0 + 20.0)
    assert lvl == DegradationLevel.EMERGENCY_HALT
    assert dog.is_halted
    assert dog.missed_ticks >= 3

    # Step 3: Governor reflects watchdog state
    governor = PortfolioGovernor()
    governor.state.watchdog_missed_beats = dog.missed_ticks
    governor.state.watchdog_healthy = not dog.is_halted

    # Step 4: Run hard veto evaluator with governor
    candidate = Candidate(
        symbol="BTCUSDT",
        direction=Direction.LONG,
        strategy_id="S1_SWEEP_RECLAIM",
        setup_edge_id="E01",
        reference_price=50000.0,
        entry_zone_low=49950.0,
        entry_zone_high=50050.0,
        stop_loss=49500.0,
        tp1=51000.0,
        tp2=None,
        gross_rr=2.0,
        net_rr=1.85,
        active_edge_ids=["E01", "E03", "E04"],
        confirming_edge_ids=["E15"],
        expiry_bars=12,
        regime=RegimeState.MEAN_REVERSION_ROTATIONAL,
        created_at_utc="2026-11-06T12:00:00Z",
    )

    candle = Candle(
        open_time_ms=0,
        close_time_ms=900000,
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50050.0,
        volume=10.0,
    )
    ctx = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=900000,
        candles=[candle],
    )
    clock = SystemClock()

    result = HardVetoEvaluator.evaluate(
        candidate=candidate,
        ctx=ctx,
        quote=None,
        clock=clock,
        governor=governor,
    )

    # Must be FAIL-CLOSED blocked by V-H10
    assert result.passed is False
    assert result.blocking_id == "V-H10"
    assert result.reason_code == HardVetoReason.WATCHDOG_FAILURE.value


def test_clock_skew_and_corrupt_candle_chaos():
    """Verify clock skew > 1000 ms asserts V-H07, and corrupted candles are rejected."""
    # 1. Clock skew test with HardVetoEvaluator
    clock = SystemClock()
    clock.update_server_time(int(time.time() * 1000.0 + 1500.0))  # Skew = 1500 ms > 1000 ms
    assert clock.is_desynced()

    candidate = Candidate(
        symbol="BTCUSDT",
        direction=Direction.LONG,
        strategy_id="S1_SWEEP_RECLAIM",
        setup_edge_id="E01",
        reference_price=50000.0,
        entry_zone_low=49950.0,
        entry_zone_high=50050.0,
        stop_loss=49500.0,
        tp1=51000.0,
        tp2=None,
        gross_rr=2.0,
        net_rr=1.85,
        active_edge_ids=["E01"],
        confirming_edge_ids=[],
        expiry_bars=12,
        regime=RegimeState.MEAN_REVERSION_ROTATIONAL,
        created_at_utc="2026-11-06T12:00:00Z",
    )
    c1 = Candle(
        open_time_ms=0,
        close_time_ms=900000,
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50050.0,
        volume=10.0,
    )
    ctx = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=900000,
        candles=[c1],
    )
    governor = PortfolioGovernor()

    res_skew = HardVetoEvaluator.evaluate(
        candidate=candidate,
        ctx=ctx,
        quote=None,
        clock=clock,
        governor=governor,
    )
    assert res_skew.passed is False
    assert res_skew.blocking_id == "V-H07"
    assert res_skew.reason_code == HardVetoReason.CLOCK_DESYNC.value

    # 2. Corrupt candle tests via domain model validation & DataIntegrityAuditor
    # Valid candle 1
    c1 = Candle(
        open_time_ms=0,
        close_time_ms=900000,
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50050.0,
        volume=10.0,
    )
    q1 = DataIntegrityAuditor.audit_candle_series([c1], timeframe="15m", check_freshness=False)
    assert q1.is_valid is True

    # Corrupt candle A: inverted close_time <= open_time -> raises ValueError at domain creation
    with pytest.raises(ValueError, match="Invalid candle timestamps"):
        Candle(
            open_time_ms=1800000,
            close_time_ms=1000000,  # invalid: close <= open
            open=50050.0,
            high=50150.0,
            low=49950.0,
            close=50100.0,
            volume=10.0,
        )

    # Corrupt candle B: negative price -> raises ValueError at domain creation
    with pytest.raises(ValueError, match="strictly positive"):
        Candle(
            open_time_ms=900000,
            close_time_ms=1800000,
            open=-500.0,  # invalid negative
            high=500.0,
            low=-600.0,
            close=100.0,
            volume=10.0,
        )

    # Corrupt candle C: Duplicate timestamp caught by DataIntegrityAuditor (V-H04)
    c_dup = Candle(
        open_time_ms=0,  # Duplicate of c1
        close_time_ms=900000,
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50050.0,
        volume=10.0,
    )
    q_dup = DataIntegrityAuditor.audit_candle_series(
        [c1, c_dup], timeframe="15m", check_freshness=False
    )
    assert q_dup.is_valid is False
    assert q_dup.veto_reason == HardVetoReason.DUPLICATE_CANDLE


def test_bounded_ringbuffer_memory_stress():
    """Verify ringbuffers remain strictly bounded under high volume, RSS stays under ceiling."""
    client = BinanceWebSocketClient(symbols=["BTCUSDT"])

    # Inject 100,000 trades into bounded deque
    for i in range(100000):
        client.trade_buffers["BTCUSDT"].append(
            AggTrade(
                symbol="BTCUSDT",
                trade_id=i,
                price=50000.0 + (i % 100),
                quantity=0.05,
                timestamp_ms=i * 10,
                is_buyer_maker=bool(i % 2),
            )
        )

    # Inject 10,000 candles into bounded deque
    for i in range(10000):
        c = Candle(
            open_time_ms=i * 900000,
            close_time_ms=(i + 1) * 900000,
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50050.0,
            volume=5.0,
        )
        client.kline_5m_buffers["BTCUSDT"].append(c)

    # Assert deque sizes are strictly capped
    assert len(client.trade_buffers["BTCUSDT"]) == 20000
    assert len(client.kline_5m_buffers["BTCUSDT"]) == 500

    # Memory RSS verification
    gc.collect()
    health = SystemHealthMonitor()
    rss_mb = health.get_rss_mb()
    # Must remain far below target 220 MB
    assert rss_mb < TARGET_CEILING_RSS_MB
    assert rss_mb < 220.0


def test_end_to_end_replay_determinism():
    """Feed identical candle sequence repeatedly, verifying 100% bit-for-bit determinism."""
    # Generate synthetic 100 bars
    rng = np.random.default_rng(12345)
    highs = 50000.0 + np.cumsum(rng.standard_normal(100) * 50)
    lows = highs - rng.uniform(20, 80, 100)
    closes = (highs + lows) / 2.0
    opens = (highs + lows) / 2.0
    volumes = rng.uniform(10, 100, 100)

    candles = [
        Candle(
            open_time_ms=i * 900000,
            close_time_ms=(i + 1) * 900000,
            open=float(opens[i]),
            high=float(highs[i]),
            low=float(lows[i]),
            close=float(closes[i]),
            volume=float(volumes[i]),
        )
        for i in range(100)
    ]

    registry = EdgeRegistry(Path("config/edge_registry.yaml"))

    def run_pipeline():
        atr_res = ATREngine.compute(candles, period=14)
        assert atr_res is not None
        atr_val = atr_res.atr
        atr_bps = atr_res.atr_bps
        classifier = RegimeClassifier()
        regime_out = classifier.evaluate(candles, atr_bps=atr_bps)

        results = {
            "E01": EdgeResult(
                edge_id="E01",
                passed=True,
                confidence=1.0,
                direction=Direction.LONG,
                score_contribution=8,
            ),
            "E04": EdgeResult(
                edge_id="E04",
                passed=True,
                confidence=1.0,
                direction=Direction.LONG,
                score_contribution=8,
            ),
            "E15": EdgeResult(
                edge_id="E15",
                passed=True,
                confidence=1.0,
                direction=Direction.LONG,
                score_contribution=8,
            ),
        }

        candidate = Candidate(
            symbol="BTCUSDT",
            direction=Direction.LONG,
            strategy_id="S1_SWEEP_RECLAIM",
            setup_edge_id="E01",
            reference_price=closes[-1],
            entry_zone_low=closes[-1] - 50.0,
            entry_zone_high=closes[-1] + 50.0,
            stop_loss=closes[-1] - 400.0,
            tp1=closes[-1] + 800.0,
            tp2=None,
            gross_rr=2.0,
            net_rr=1.85,
            active_edge_ids=["E01", "E04", "E15"],
            confirming_edge_ids=[],
            expiry_bars=12,
            regime=regime_out.state,
            created_at_utc="2026-11-06T12:00:00Z",
        )

        scorer = CompositeScorer(registry)
        score_breakdown = scorer.score(candidate, results)

        return (
            float(atr_val),
            regime_out.state.value,
            score_breakdown.total_score,
            float(candidate.tp1),
        )

    run1 = run_pipeline()
    run2 = run_pipeline()
    run3 = run_pipeline()

    assert run1 == run2 == run3
