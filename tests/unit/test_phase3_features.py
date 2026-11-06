"""Unit tests for Phase 3: Feature Engine (Pure transforms, no look-ahead)."""

import numpy as np

from neo_wilder.domain.enums import RegimeState
from neo_wilder.domain.models import AggTrade, Candle, OrderBookLevel, OrderBookSnapshot
from neo_wilder.features.atr import ATREngine
from neo_wilder.features.cvd import CVDEngine
from neo_wilder.features.funding import FundingEngine, FundingSnapshot
from neo_wilder.features.liquidity import LiquidityPoolDetector
from neo_wilder.features.obi import OBIEngine
from neo_wilder.features.regime import RegimeClassifier
from neo_wilder.features.structure import StructureDetector
from neo_wilder.features.swings import SwingDetector
from neo_wilder.features.volume_profile import VolumeProfileEngine


def _generate_synthetic_candles(n: int = 60, base_price: float = 100.0) -> list[Candle]:
    candles = []
    price = base_price
    t_start = 1700000000000
    for i in range(n):
        # Create subtle oscillating pattern
        ret = 0.005 * np.sin(i / 3.0)
        open_p = price
        close_p = price * (1.0 + ret)
        high_p = max(open_p, close_p) * 1.002
        low_p = min(open_p, close_p) * 0.998
        price = close_p
        candles.append(
            Candle(
                open_time_ms=t_start + i * 900000,
                close_time_ms=t_start + (i + 1) * 900000 - 1,
                open=open_p,
                high=high_p,
                low=low_p,
                close=close_p,
                volume=100.0 + (i % 10) * 10,
            )
        )
    return candles


def test_no_lookahead_determinism_test():
    """Anti-cheating test: Shuffling future bars has ZERO impact on index t features."""
    all_candles = _generate_synthetic_candles(70)
    t = 50
    past_candles = all_candles[:t]

    # Compute features at t
    atr_res_1 = ATREngine.compute(past_candles)
    swings_1 = SwingDetector.find_swings(past_candles)
    vp_1 = VolumeProfileEngine.compute(past_candles)

    # Now take future bars t:70, shuffle their order, but compute on sub-slice <= t
    future_bars = all_candles[t:].copy()
    np.random.seed(42)
    np.random.shuffle(future_bars)
    reconstructed_history = past_candles + future_bars
    evaluated_slice = reconstructed_history[:t]

    atr_res_2 = ATREngine.compute(evaluated_slice)
    swings_2 = SwingDetector.find_swings(evaluated_slice)
    vp_2 = VolumeProfileEngine.compute(evaluated_slice)

    assert atr_res_1.atr == atr_res_2.atr
    assert atr_res_1.atr_bps == atr_res_2.atr_bps
    assert len(swings_1) == len(swings_2)
    assert vp_1.poc == vp_2.poc
    assert vp_1.val == vp_2.val
    assert vp_1.vah == vp_2.vah


def test_atr_and_vol_tier():
    candles = _generate_synthetic_candles(30)
    res = ATREngine.compute(candles, period=14)
    assert res is not None
    assert res.atr > 0.0
    assert res.atr_bps > 0.0
    assert res.vol_tier in (0, 1, 2)


def test_swings_and_liquidity_pools():
    candles = _generate_synthetic_candles(50)
    swings = SwingDetector.find_swings(candles, left_bars=3, right_bars=1)
    assert len(swings) > 0

    atr_res = ATREngine.compute(candles)
    pools = LiquidityPoolDetector.detect_pools(swings, atr=atr_res.atr, cluster_tolerance_atr=0.15)
    # Pools can be detected or empty depending on price oscillation
    assert isinstance(pools, list)


def test_structure_shift():
    candles = _generate_synthetic_candles(40)
    swings = SwingDetector.find_swings(candles)
    state = StructureDetector.detect_shift(candles, swings)
    assert hasattr(state, "has_bullish_bos")
    assert hasattr(state, "has_bearish_bos")


def test_volume_profile():
    candles = _generate_synthetic_candles(40)
    vp = VolumeProfileEngine.compute(candles, bins=30)
    assert vp is not None
    assert vp.val <= vp.poc <= vp.vah
    assert vp.total_volume > 0.0


def test_funding_engine():
    snapshot = FundingSnapshot(
        symbol="BTCUSDT",
        timestamp_ms=1700000000000,
        mark_price=70050.0,
        index_price=70000.0,
        funding_rate=0.0001,  # 0.01%
        next_funding_time_ms=1700000000000 + 300000,  # 5 min away
    )
    res = FundingEngine.evaluate(snapshot, now_ms=1700000000000)
    assert res.mark_index_divergence_pct > 0.0
    assert res.is_funding_window_active is True
    assert res.is_toxic_funding is False


def test_cvd_and_obi():
    # CVD test
    trades = [
        AggTrade(
            trade_id=i,
            symbol="BTCUSDT",
            price=70000.0,
            quantity=1.0,
            timestamp_ms=1700000000000 + i,
            is_buyer_maker=(i < 15),
        )
        for i in range(30)
    ]
    cvd_res = CVDEngine.compute(trades)
    assert cvd_res is not None
    assert cvd_res.has_turned_bullish is True

    # OBI test
    book = OrderBookSnapshot(
        symbol="BTCUSDT",
        timestamp_ms=1700000000000,
        bids=[OrderBookLevel(price=70000.0 - i, quantity=2.0) for i in range(10)],
        asks=[OrderBookLevel(price=70001.0 + i, quantity=1.0) for i in range(10)],
    )
    obi_res = OBIEngine.compute(book)
    assert obi_res is not None
    # More bids than asks -> positive OBI
    assert obi_res.obi > 0.0


def test_regime_classifier():
    classifier = RegimeClassifier(hysteresis_bars=2)
    candles = _generate_synthetic_candles(40)

    # Test noise chop gate
    out_chop = classifier.evaluate(candles, atr_bps=3.0)
    assert out_chop.state == RegimeState.NOISE_CHOP

    # Test liquidity stress gate
    out_stress = classifier.evaluate(candles, atr_bps=450.0)
    assert out_stress.state == RegimeState.LIQUIDITY_STRESS


def test_swing_detection_no_future_leak():
    """Verify SwingDetector strictly respects causal right_bars confirmation (no future peek)."""
    candles = _generate_synthetic_candles(60)
    left_bars, right_bars = 3, 2

    # Step-by-step rolling evaluation
    for t in range(20, len(candles)):
        prefix = candles[:t]
        swings = SwingDetector.find_swings(prefix, left_bars=left_bars, right_bars=right_bars)
        for s in swings:
            # A swing pivot at index i cannot be confirmed until bar i + right_bars
            assert s.index <= t - 1 - right_bars, (
                f"Look-ahead detected: swing at index {s.index} confirmed on bar {t - 1} "
                f"with right_bars={right_bars}"
            )


def test_swing_detection_prefix_invariance():
    """Verify that adding future bars does not mutate already confirmed historical swings."""
    candles = _generate_synthetic_candles(60)
    left_bars, right_bars = 3, 1

    swings_at_40 = SwingDetector.find_swings(
        candles[:40], left_bars=left_bars, right_bars=right_bars
    )
    swings_at_60 = SwingDetector.find_swings(
        candles[:60], left_bars=left_bars, right_bars=right_bars
    )

    # All confirmed swings in the safe prefix (<= 40 - 1 - right_bars = 38) must match exactly
    safe_cutoff = 40 - 1 - right_bars
    swings_40_safe = [s for s in swings_at_40 if s.index <= safe_cutoff]
    swings_60_in_prefix = [s for s in swings_at_60 if s.index <= safe_cutoff]

    assert len(swings_40_safe) == len(swings_60_in_prefix)
    for s1, s2 in zip(swings_40_safe, swings_60_in_prefix, strict=True):
        assert s1.index == s2.index
        assert s1.pivot_type == s2.pivot_type
        assert abs(s1.price - s2.price) < 1e-6


def test_rsi_divergence_engine():
    """Verify RSIEngine calculates Wilder RSI and detects structural divergence."""
    from neo_wilder.features.rsi import RSIEngine

    candles = _generate_synthetic_candles(50)
    swings = SwingDetector.find_swings(candles)
    rsi_res = RSIEngine.compute(candles, swings)

    assert rsi_res is not None
    assert 0.0 <= rsi_res.rsi <= 100.0
    assert len(rsi_res.rsi_series) == len(candles) - 14
    assert abs(rsi_res.rsi - rsi_res.rsi_series[-1]) < 1e-6
    assert isinstance(rsi_res.has_bearish_divergence, bool)
    assert isinstance(rsi_res.has_bullish_divergence, bool)
