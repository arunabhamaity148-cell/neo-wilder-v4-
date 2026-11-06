"""Unit tests for Phase 5: Strategy and Regime Engine."""

from neo_wilder.domain.enums import Direction, RegimeState
from neo_wilder.domain.models import Candle, EdgeResult, LiquidityPool, SwingPivot
from neo_wilder.edges.base import FeatureContext
from neo_wilder.features.atr import ATRResult
from neo_wilder.features.regime import RegimeOutput
from neo_wilder.strategies.s1_sweep_reclaim import S1SweepReclaimStrategy


def _build_test_context(regime_state: RegimeState = RegimeState.NEUTRAL) -> FeatureContext:
    atr = 100.0
    atr_res = ATRResult(atr=atr, atr_bps=20.0, vol_tier=1, trailing_100_atr=[atr] * 50)
    reg_out = RegimeOutput(state=regime_state, variance_ratio=1.0, atr_bps=20.0, is_stress=False)

    # Reclaim bar: open=50010, low=49900, close=50020
    curr_bar = Candle(
        open_time_ms=3000,
        close_time_ms=3899,
        open=50010.0,
        high=50050.0,
        low=49900.0,
        close=50020.0,
        volume=250.0,
    )

    # Opposing swing high at 51000 (gives reward = 980, risk = 370 -> R:R ~ 2.65)
    swings = [
        SwingPivot(index=5, timestamp_ms=1000, price=51000.0, pivot_type="HIGH"),
    ]

    pool = LiquidityPool(
        pool_type="EQL",
        level=50000.0,
        swings=[],
        touch_count=2,
        width_atr=0.10,
    )

    return FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=4000,
        candles=[curr_bar],
        atr_result=atr_res,
        regime_output=reg_out,
        swings=swings,
        pools=[pool],
    )


def test_s1_long_candidate_emission():
    strategy = S1SweepReclaimStrategy()
    ctx = _build_test_context()

    edge_results = {
        "E01": EdgeResult(
            edge_id="E01",
            passed=True,
            confidence=0.85,
            direction=Direction.LONG,
            score_contribution=10,
            metadata={"sweep_depth": 100.0, "pool_level": 50000.0, "sweep_low": 49900.0},
        ),
        "E05": EdgeResult(edge_id="E05", passed=True, confidence=0.8, direction=Direction.LONG),
        "E12": EdgeResult(
            edge_id="E12",
            passed=True,
            confidence=1.0,
            direction=Direction.BOTH,
            metadata={"buffer_multiplier": 2.5},
        ),
    }

    candidate = strategy.generate_candidate(ctx, edge_results)
    assert candidate is not None
    assert candidate.strategy_id == "S1_SWEEP_RECLAIM"
    assert candidate.direction == Direction.LONG
    assert candidate.reference_price == 50020.0
    assert candidate.tp1 == 51000.0
    assert candidate.tp2 is None  # Unresolved anchor per KNOWN_LIMITATIONS.md
    assert candidate.net_rr >= 1.50
    assert candidate.entry_zone_high == 50020.0
    assert candidate.entry_zone_low < candidate.entry_zone_high


def test_s1_short_disabled_fail_closed():
    """Verify KNOWN_LIMITATIONS.md: SHORT candidate generation must return None."""
    strategy = S1SweepReclaimStrategy()
    ctx = _build_test_context()

    edge_results = {
        "E01": EdgeResult(
            edge_id="E01",
            passed=True,
            confidence=0.85,
            direction=Direction.SHORT,  # Bearish sweep
            score_contribution=10,
            metadata={"sweep_depth": 50.0, "pool_level": 50000.0, "sweep_low": 50050.0},
        ),
        "E05": EdgeResult(edge_id="E05", passed=True, confidence=0.8, direction=Direction.SHORT),
    }

    candidate = strategy.generate_candidate(ctx, edge_results)
    assert candidate is None


def test_s1_regime_gating_noise_chop():
    """Verify S1 does not trade in NOISE_CHOP."""
    strategy = S1SweepReclaimStrategy()
    ctx = _build_test_context(regime_state=RegimeState.NOISE_CHOP)

    edge_results = {
        "E01": EdgeResult(
            edge_id="E01",
            passed=True,
            confidence=0.85,
            direction=Direction.LONG,
            metadata={"sweep_depth": 50.0, "pool_level": 50000.0, "sweep_low": 49950.0},
        ),
        "E05": EdgeResult(edge_id="E05", passed=True, confidence=0.8, direction=Direction.LONG),
    }

    candidate = strategy.generate_candidate(ctx, edge_results)
    assert candidate is None


def test_s1_tautology_elimination_rejects_without_structural_target():
    """If no opposing swing high provides Net R:R >= 1.50, trade must be rejected."""
    strategy = S1SweepReclaimStrategy()
    ctx = _build_test_context()
    # Replace opposing swing with one that gives tiny R:R (e.g. 50050 vs entry 50020)
    ctx_tiny_tp = FeatureContext(
        symbol=ctx.symbol,
        timeframe=ctx.timeframe,
        now_ms=ctx.now_ms,
        candles=ctx.candles,
        atr_result=ctx.atr_result,
        regime_output=ctx.regime_output,
        swings=[SwingPivot(index=5, timestamp_ms=1000, price=50040.0, pivot_type="HIGH")],
        pools=ctx.pools,
    )

    edge_results = {
        "E01": EdgeResult(
            edge_id="E01",
            passed=True,
            confidence=0.85,
            direction=Direction.LONG,
            metadata={"sweep_depth": 100.0, "pool_level": 50000.0, "sweep_low": 49900.0},
        ),
        "E05": EdgeResult(edge_id="E05", passed=True, confidence=0.8, direction=Direction.LONG),
        "E12": EdgeResult(
            edge_id="E12",
            passed=True,
            confidence=1.0,
            direction=Direction.BOTH,
            metadata={"buffer_multiplier": 2.5},
        ),
    }

    candidate = strategy.generate_candidate(ctx_tiny_tp, edge_results)
    assert candidate is None
