"""Unit tests for Phase 4: Pure Edge Modules."""

from pathlib import Path

from neo_wilder.domain.enums import Direction, EdgeStatus, ScoringCluster
from neo_wilder.domain.models import Candle, LiquidityPool, SwingPivot
from neo_wilder.edges.base import FeatureContext
from neo_wilder.edges.e01_sweep_reclaim import E01SweepReclaim
from neo_wilder.edges.e05_structure import E05Structure
from neo_wilder.edges.e12_dynamic_sl_buffer import E12DynamicSLBuffer
from neo_wilder.edges.e17_absorption import E17Absorption
from neo_wilder.edges.registry import EdgeRegistry
from neo_wilder.edges.runner import EdgeRunner
from neo_wilder.features.atr import ATRResult
from neo_wilder.features.funding import FundingContextResult
from neo_wilder.features.structure import StructureState


def test_e01_sweep_reclaim_fixtures():
    edge = E01SweepReclaim()
    atr = 100.0  # ATR = $100

    pool = LiquidityPool(
        pool_type="EQL",
        level=50000.0,
        swings=[
            SwingPivot(index=10, timestamp_ms=1000, price=50005.0, pivot_type="LOW"),
            SwingPivot(index=20, timestamp_ms=2000, price=49995.0, pivot_type="LOW"),
        ],
        touch_count=2,
        width_atr=0.10,
    )

    atr_res = ATRResult(atr=atr, atr_bps=20.0, vol_tier=1, trailing_100_atr=[atr] * 50)

    # 1. Positive fixture: low = 49950 (d = 50 = 0.5 ATR, within 0.05-1.2 ATR), close = 50020 (> pool)
    candle_pos = Candle(
        open_time_ms=3000,
        close_time_ms=3899,
        open=50010.0,
        high=50050.0,
        low=49950.0,
        close=50020.0,
        volume=150.0,
    )
    ctx_pos = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=3900,
        candles=[candle_pos],
        atr_result=atr_res,
        pools=[pool],
    )
    res_pos = edge.evaluate(ctx_pos)
    assert res_pos.passed is True
    assert res_pos.direction == Direction.LONG
    assert res_pos.metadata["sweep_depth"] == 50.0

    # 2. Negative fixture: sweep too shallow (d = 2 < 0.05 * 100 = 5)
    candle_shallow = Candle(
        open_time_ms=3000,
        close_time_ms=3899,
        open=50010.0,
        high=50050.0,
        low=49998.0,
        close=50020.0,
        volume=150.0,
    )
    ctx_shallow = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=3900,
        candles=[candle_shallow],
        atr_result=atr_res,
        pools=[pool],
    )
    res_shallow = edge.evaluate(ctx_shallow)
    assert res_shallow.passed is False

    # 3. Negative fixture: sweep too deep (d = 150 > 1.2 * 100 = 120)
    candle_deep = Candle(
        open_time_ms=3000,
        close_time_ms=3899,
        open=50010.0,
        high=50050.0,
        low=49850.0,
        close=50020.0,
        volume=150.0,
    )
    ctx_deep = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=3900,
        candles=[candle_deep],
        atr_result=atr_res,
        pools=[pool],
    )
    res_deep = edge.evaluate(ctx_deep)
    assert res_deep.passed is False


def test_e05_structure_shadow_isolation():
    edge = E05Structure()
    struct = StructureState(
        has_bullish_bos=True,
        has_bearish_bos=False,
        has_bullish_choch=False,
        has_bearish_choch=False,
    )
    ctx = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=1000,
        candles=[],
        structure=struct,
    )
    res = edge.evaluate(ctx)
    assert res.passed is True
    # Invariant: Shadow edge MUST have score_contribution == 0
    assert res.score_contribution == 0


def test_e12_dynamic_sl_buffer():
    edge = E12DynamicSLBuffer()
    # vol_tier = 1 -> alpha = 2.2
    atr_res = ATRResult(atr=100.0, atr_bps=20.0, vol_tier=1, trailing_100_atr=[100.0])

    # Normal funding (< 0.03%)
    fc_normal = FundingContextResult(
        funding_rate_pct=0.01,
        mark_index_divergence_pct=0.05,
        minutes_to_settlement=120.0,
        is_funding_window_active=False,
        is_toxic_funding=False,
    )
    ctx_normal = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=1000,
        candles=[],
        atr_result=atr_res,
        funding_context=fc_normal,
    )
    res_normal = edge.evaluate(ctx_normal)
    assert res_normal.metadata["buffer_multiplier"] == 2.2

    # High funding (0.04% >= 0.03%) -> +0.60 penalty
    fc_high = FundingContextResult(
        funding_rate_pct=0.04,
        mark_index_divergence_pct=0.05,
        minutes_to_settlement=120.0,
        is_funding_window_active=False,
        is_toxic_funding=False,
    )
    ctx_high = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=1000,
        candles=[],
        atr_result=atr_res,
        funding_context=fc_high,
    )
    res_high = edge.evaluate(ctx_high)
    assert round(res_high.metadata["buffer_multiplier"], 2) == 2.80


def test_e17_reconciled_c2_cluster_and_shadow():
    registry = EdgeRegistry(Path("config/edge_registry.yaml"))
    meta_e17 = registry.get("E17")
    assert meta_e17.status == EdgeStatus.SHADOW
    assert meta_e17.cluster == ScoringCluster.C2

    edge = E17Absorption()
    ctx = FeatureContext(symbol="BTCUSDT", timeframe="15m", now_ms=1000, candles=[])
    res = edge.evaluate(ctx)
    assert res.score_contribution == 0


def test_edge_runner_execution_and_ablation():
    registry = EdgeRegistry(Path("config/edge_registry.yaml"))
    runner = EdgeRunner(registry=registry)

    ctx = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=1000,
        candles=[],
    )
    results = runner.evaluate_all(ctx)
    assert isinstance(results, dict)
    assert "E01" in results
    assert "E12" in results
    assert "X01" in results
