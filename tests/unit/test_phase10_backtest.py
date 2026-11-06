"""Unit tests for Phase 10: Backtest and Ablation Framework."""

import numpy as np
import pytest

from research.ablation.harness import EdgeAblationHarness
from research.backtest.engine import (
    EFFECTIVE_RT_FEE,
    BacktestCostModel,
    BacktestEngine,
)
from research.walkforward.validator import PurgedWalkForwardValidator


def test_backtest_cost_model():
    """Verify 4-component cost model values: 0.1180% fee, slippage floor 1.0 bp, funding."""
    assert EFFECTIVE_RT_FEE == pytest.approx(0.001180, rel=1e-4)

    # Slippage: spread 4 bps, ATR 50 bps -> 0.5 * 4 + 0.3 * 0.5 = 2.0 + 0.15 = 2.15 bps
    slip = BacktestCostModel.calculate_slippage(spread_bps=4.0, atr_bps=50.0)
    assert slip == pytest.approx(2.15 / 10000.0, rel=1e-4)

    # Slippage floor: zero spread, zero ATR -> must floor at 1.0 bp (0.0001)
    slip_floor = BacktestCostModel.calculate_slippage(spread_bps=0.0, atr_bps=0.0)
    assert slip_floor == pytest.approx(1.0 / 10000.0, rel=1e-4)

    # Funding: 8h rate 0.0001 (0.01%), held 32 bars (8 hours) -> exactly 1 period = 0.0001
    funding = BacktestCostModel.calculate_funding(rate_8h=0.0001, holding_bars_15m=32)
    assert funding == pytest.approx(0.0001, rel=1e-4)


def test_backtest_next_bar_fill_and_intrabar_ambiguity():
    """Verify next-bar open fill, missed fills, and conservative intrabar ambiguity."""
    engine = BacktestEngine(bootstrap_iterations=500, random_seed=42)

    # Create synthetic 10-bar series
    opens = np.array([100.0, 100.2, 100.5, 101.0, 101.5, 102.0, 102.5, 103.0, 103.5, 104.0])
    highs = np.array([101.0, 100.8, 102.0, 102.5, 103.0, 103.5, 104.0, 104.5, 105.0, 105.5])
    lows = np.array([99.0, 99.8, 98.5, 100.0, 100.5, 101.0, 101.5, 102.0, 102.5, 103.0])
    closes = np.array([100.2, 100.5, 101.0, 101.5, 102.0, 102.5, 103.0, 103.5, 104.0, 104.5])
    atrs = np.full(10, 1.0)

    # Signal 1: Generated at bar 0. Entry zone [100.0 - 100.4]. Next open (bar 1) is 100.2 -> FILLED!
    # TP1 = 101.5, SL = 99.0.
    # At bar 2: high=102.0 (>= TP1 101.5), low=98.5 (<= SL 99.0).
    # BOTH HIT AT BAR 2! INTRABAR AMBIGUITY MUST RESOLVE SL FIRST!
    sig1 = {
        "signal_id": "SIG-01",
        "bar_idx": 0,
        "entry_zone_low": 100.0,
        "entry_zone_high": 100.4,
        "stop_loss": 99.0,
        "tp1": 101.5,
        "direction": "LONG",
        "regime": "ROTATIONAL",
    }

    # Signal 2: Generated at bar 4. Entry zone [95.0 - 96.0].
    # Next bar (bar 5): high 103.5, low 101.0 -> Does not touch [95-96] -> MISSED!
    sig2 = {
        "signal_id": "SIG-02",
        "bar_idx": 4,
        "entry_zone_low": 95.0,
        "entry_zone_high": 96.0,
        "stop_loss": 94.0,
        "tp1": 98.0,
        "direction": "LONG",
        "regime": "ROTATIONAL",
    }

    trades = engine.simulate_trades([sig1, sig2], highs, lows, opens, closes, atrs)
    assert len(trades) == 2

    # Verify Trade 1 resolved as SL_HIT due to conservative intrabar ambiguity
    assert trades[0].trade_id == "SIG-01"
    assert trades[0].exit_reason == "SL_HIT"
    assert trades[0].realized_r < 0  # Loss

    # Verify Trade 2 resolved as MISSED
    assert trades[1].trade_id == "SIG-02"
    assert trades[1].exit_reason == "MISSED"

    report = engine.evaluate(trades)
    assert report.total_signals == 2
    assert report.filled_trades == 1
    assert report.missed_trades == 1
    assert report.missed_fill_rate == 0.50
    assert report.losses == 1
    assert report.win_rate == 0.0


def test_purged_walk_forward_folds():
    """Verify walk-forward fold generation with 24-bar purge boundary."""
    validator = PurgedWalkForwardValidator(
        train_bars=1000,
        test_bars=200,
        roll_bars=200,
        purge_bars=24,
    )
    # Total bars: 2000
    folds = validator.generate_folds(2000)
    assert len(folds) >= 1

    fold0_train, fold0_test = folds[0]
    assert fold0_train == (0, 1000)
    # Test start must be train_end + purge_bars = 1000 + 24 = 1024
    assert fold0_test == (1024, 1224)


def test_ablation_harness():
    """Verify leave-one-out ablation logic evaluates delta expectancy and active justification."""
    engine = BacktestEngine(bootstrap_iterations=200, random_seed=42)
    harness = EdgeAblationHarness(engine)

    n_bars = 20
    opens = np.linspace(100, 110, n_bars)
    highs = opens + 1.5
    lows = opens - 0.5
    closes = opens + 0.8
    atrs = np.full(n_bars, 1.0)

    # Create signals with edges
    signals = [
        {
            "signal_id": f"SIG-{i}",
            "bar_idx": i,
            "entry_zone_low": float(opens[i + 1] - 0.5),
            "entry_zone_high": float(opens[i + 1] + 0.5),
            "stop_loss": float(opens[i + 1] - 2.0),
            "tp1": float(opens[i + 1] + 2.0),
            "active_edges": ["E01", "E03", "E04"],
            "direction": "LONG",
        }
        for i in range(15)
    ]

    rows = harness.run_ablation(
        signals_pool=signals,
        active_edge_ids=["E01", "E03"],
        highs=highs,
        lows=lows,
        opens=opens,
        closes=closes,
        atrs=atrs,
    )
    assert len(rows) == 2
    assert rows[0].edge_id == "E01"
    assert rows[1].edge_id == "E03"
    assert rows[0].recommendation in ("RETAIN_ACTIVE", "DEMOTE_TO_SHADOW")
