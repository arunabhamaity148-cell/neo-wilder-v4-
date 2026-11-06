"""Unit tests for Phase 1: Repository Foundation & Frozen Contracts."""

from pathlib import Path

import pytest
import yaml

from neo_wilder.clock import SystemClock
from neo_wilder.domain.enums import Direction, EdgeStatus, RegimeState, ScoringCluster
from neo_wilder.domain.models import Candle
from neo_wilder.edges.registry import EdgeRegistry
from neo_wilder.publish.schema import Signal


def test_edge_registry_completeness():
    registry_path = Path("config/edge_registry.yaml")
    registry = EdgeRegistry(registry_path)

    all_edges = registry.all_edges()
    assert len(all_edges) == 32, f"Expected 32 edges, found {len(all_edges)}"

    # Reconciled E17 behavior
    e17 = registry.get("E17")
    assert e17.status == EdgeStatus.SHADOW
    assert e17.cluster == ScoringCluster.C2

    # E01 Spine behavior
    e01 = registry.get("E01")
    assert e01.status == EdgeStatus.ACTIVE
    assert e01.cluster == ScoringCluster.C3


def test_veto_registry_completeness():
    veto_path = Path("config/veto_registry.yaml")
    assert veto_path.exists()

    with open(veto_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    hard_vetoes = data.get("hard_vetoes", [])
    soft_vetoes = data.get("soft_vetoes", [])

    assert len(hard_vetoes) == 34, f"Expected 34 hard vetoes, got {len(hard_vetoes)}"
    assert len(soft_vetoes) == 15, f"Expected 15 soft vetoes, got {len(soft_vetoes)}"
    assert len(hard_vetoes) + len(soft_vetoes) == 49

    # Test corrected V-H03 condition
    vh03 = next(v for v in hard_vetoes if v["id"] == "V-H03")
    assert "close_time <= open_time" in vh03["cond"]


def test_candle_timestamp_and_geometry_validation():
    # Valid candle
    c = Candle(
        open_time_ms=1000,
        close_time_ms=1999,
        open=100.0,
        high=105.0,
        low=95.0,
        close=102.0,
        volume=50.0,
    )
    assert c.open == 100.0

    # Invalid timestamp (close <= open)
    with pytest.raises(ValueError, match="Invalid candle timestamps"):
        Candle(
            open_time_ms=2000,
            close_time_ms=1000,
            open=100.0,
            high=105.0,
            low=95.0,
            close=102.0,
            volume=50.0,
        )

    # Invalid negative price
    with pytest.raises(ValueError, match="prices must be strictly positive"):
        Candle(
            open_time_ms=1000,
            close_time_ms=1999,
            open=-100.0,
            high=105.0,
            low=-105.0,
            close=102.0,
            volume=50.0,
        )


def test_signal_schema_invariants():
    sig = Signal(
        signal_id="SIG-20261106-001",
        created_at_utc="2026-11-06T12:00:00Z",
        expires_at_utc="2026-11-06T16:00:00Z",
        symbol_binance="BTCUSDT",
        symbol_coindcx="B-BTC_USDT",
        direction=Direction.LONG,
        strategy_id="S1_SWEEP_RECLAIM",
        active_edge_ids=["E01", "E04", "E11", "E12"],
        confirming_edge_ids=[],
        reference_price=70000.0,
        coindcx_price=70050.0,
        coindcx_spread_bps=2.5,
        coindcx_top10_depth_usd=250000.0,
        entry_zone_low=69900.0,
        entry_zone_high=70000.0,
        stop_loss=69500.0,
        tp1=71000.0,
        tp2=None,
        gross_rr=2.0,
        fee_pct=0.118,
        slippage_pct=0.017,
        funding_pct_est=0.0,
        net_rr=1.85,
        score_0_100=88,
        calibrated_probability="NOT CALIBRATED",
        regime=RegimeState.MEAN_REVERSION_ROTATIONAL,
        btc_context="NEUTRAL",
        veto_status="PASSED",
        soft_veto_list=[],
        max_entry_drift_pct=0.35,
        invalidation_conditions=["CHoCH on 15m"],
        one_paragraph_thesis="Test thesis for S1 long signal.",
    )
    assert sig.score_0_100 == 88
    assert sig.direction == Direction.LONG

    # Test net R:R < 1.50 throws
    with pytest.raises(ValueError, match="Net R:R must be >= 1.50"):
        Signal(
            signal_id="SIG-002",
            created_at_utc="2026-11-06T12:00:00Z",
            expires_at_utc="2026-11-06T16:00:00Z",
            symbol_binance="BTCUSDT",
            symbol_coindcx="B-BTC_USDT",
            direction=Direction.LONG,
            strategy_id="S1",
            active_edge_ids=[],
            confirming_edge_ids=[],
            reference_price=70000.0,
            coindcx_price=70000.0,
            coindcx_spread_bps=2.0,
            coindcx_top10_depth_usd=100000.0,
            entry_zone_low=69900.0,
            entry_zone_high=70000.0,
            stop_loss=69500.0,
            tp1=70500.0,
            tp2=None,
            gross_rr=1.0,
            fee_pct=0.118,
            slippage_pct=0.017,
            funding_pct_est=0.0,
            net_rr=1.20,  # Below 1.50
            score_0_100=90,
            calibrated_probability="NOT CALIBRATED",
            regime=RegimeState.NEUTRAL,
            btc_context="NEUTRAL",
            veto_status="PASSED",
            soft_veto_list=[],
            max_entry_drift_pct=0.35,
            invalidation_conditions=[],
            one_paragraph_thesis="Under threshold net R:R",
        )


def test_system_clock_sync():
    clock = SystemClock(max_skew_ms=1000.0)
    now_ms = clock.now_ms()
    # Mock server time within 200 ms
    clock.update_server_time(now_ms + 150)
    assert not clock.is_desynced()

    # Mock server time skewed by 1200 ms
    clock.update_server_time(now_ms + 1200)
    assert clock.is_desynced()
