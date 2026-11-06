"""Unit tests for EXTREME_MARKET_RISK_GUARD (Bidirectional).

Tests all 6 risk conditions, explicit LONG/SHORT scenarios, missing-data, and stale-data fail-closed rules.
"""

from neo_wilder.domain.enums import Direction, RegimeState, SymbolTier
from neo_wilder.domain.models import (
    Candidate,
    Candle,
    CoinDCXQuote,
    OISnapshot,
)
from neo_wilder.edges.base import FeatureContext
from neo_wilder.features.cvd import CVDResult
from neo_wilder.features.funding import FundingContextResult
from neo_wilder.features.obi import OBIResult
from neo_wilder.features.rsi import RSIResult
from neo_wilder.vetoes.risk_guard import ExtremeMarketRiskGuard


def create_base_candidate(direction: Direction = Direction.LONG) -> Candidate:
    return Candidate(
        symbol="BTCUSDT",
        direction=direction,
        strategy_id="S1_SWEEP_RECLAIM",
        setup_edge_id="E01",
        reference_price=50000.0,
        entry_zone_low=49950.0,
        entry_zone_high=50050.0,
        stop_loss=49500.0 if direction == Direction.LONG else 50500.0,
        tp1=51000.0 if direction == Direction.LONG else 49000.0,
        tp2=None,
        gross_rr=2.0,
        net_rr=1.85,
        active_edge_ids=["E01", "E03"],
        confirming_edge_ids=[],
        expiry_bars=12,
        regime=RegimeState.MEAN_REVERSION_ROTATIONAL,
        created_at_utc="2026-11-06T12:00:00Z",
    )


def create_base_context(direction: Direction = Direction.LONG) -> FeatureContext:
    candles = [
        Candle(
            open_time_ms=i * 900000,
            close_time_ms=(i + 1) * 900000,
            open=50000.0,
            high=50100.0,
            low=49900.0,
            close=50000.0,
            volume=10.0,
        )
        for i in range(30)
    ]

    funding_ctx = FundingContextResult(
        funding_rate_pct=0.01,  # 0.01% (normal, non-extreme)
        mark_index_divergence_pct=0.05,
        minutes_to_settlement=120.0,  # 2 hours away (safe)
        is_funding_window_active=False,
        is_toxic_funding=False,
    )

    oi_snaps = [
        OISnapshot(
            symbol="BTCUSDT",
            timestamp_ms=0,
            open_interest=10000.0,
            open_interest_value=500_000_000.0,
        ),
        OISnapshot(
            symbol="BTCUSDT",
            timestamp_ms=900000,
            open_interest=10050.0,
            open_interest_value=502_500_000.0,
        ),
    ]

    return FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=900000 * 30,
        candles=candles,
        funding_context=funding_ctx,
        oi_snapshot=oi_snaps[-1],
        oi_history=oi_snaps,
    )


def test_missing_data_causes_abstain():
    """Verify that completely missing OI or funding data triggers fail-closed block/abstain."""
    guard = ExtremeMarketRiskGuard()
    candidate = create_base_candidate(Direction.LONG)

    # 1. Missing OI data entirely
    ctx_no_oi = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=1000,
        candles=create_base_context().candles,
        funding_context=create_base_context().funding_context,
        oi_snapshot=None,
        oi_history=[],
    )
    res_no_oi = guard.evaluate_candidate(candidate, ctx_no_oi)
    assert res_no_oi.is_safe is False
    assert res_no_oi.hard_veto_triggered is True
    assert res_no_oi.blocking_veto_id == "V-H11"
    assert res_no_oi.abstained is True

    # 2. Missing Funding data entirely
    ctx_no_fund = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=1000,
        candles=create_base_context().candles,
        funding_context=None,
        oi_snapshot=create_base_context().oi_snapshot,
        oi_history=create_base_context().oi_history,
    )
    res_no_fund = guard.evaluate_candidate(candidate, ctx_no_fund)
    assert res_no_fund.is_safe is False
    assert res_no_fund.hard_veto_triggered is True
    assert res_no_fund.blocking_veto_id == "V-H11"
    assert res_no_fund.abstained is True


def test_funding_overheating_bidirectional():
    """Verify funding crowding blocks LONG on positive extreme and SHORT on negative extreme."""
    guard = ExtremeMarketRiskGuard()

    # Case A: Positive funding extreme (> +0.05%) evaluated for LONG candidate -> BLOCKED
    cand_long = create_base_candidate(Direction.LONG)
    fund_extreme_pos = FundingContextResult(
        funding_rate_pct=0.08,  # +0.08% > +0.05%
        mark_index_divergence_pct=0.1,
        minutes_to_settlement=120.0,
        is_funding_window_active=False,
        is_toxic_funding=True,
    )
    ctx_long = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=1000,
        candles=create_base_context().candles,
        funding_context=fund_extreme_pos,
        oi_snapshot=create_base_context().oi_snapshot,
        oi_history=create_base_context().oi_history,
    )
    res_pos = guard.evaluate_candidate(cand_long, ctx_long)
    assert res_pos.is_safe is False
    assert res_pos.hard_veto_triggered is True
    assert res_pos.blocking_veto_id == "V-S04_ESCALATED"
    assert res_pos.blocking_reason == "FUNDING_CROWDED_LONG"
    assert res_pos.danger_flags["funding_overheating"] is True

    # Case B: Negative funding extreme (< -0.05%) evaluated for SHORT candidate -> BLOCKED
    cand_short = create_base_candidate(Direction.SHORT)
    fund_extreme_neg = FundingContextResult(
        funding_rate_pct=-0.07,  # -0.07% < -0.05%
        mark_index_divergence_pct=0.1,
        minutes_to_settlement=120.0,
        is_funding_window_active=False,
        is_toxic_funding=True,
    )
    ctx_short = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=1000,
        candles=create_base_context().candles,
        funding_context=fund_extreme_neg,
        oi_snapshot=create_base_context().oi_snapshot,
        oi_history=create_base_context().oi_history,
    )
    res_neg = guard.evaluate_candidate(cand_short, ctx_short)
    assert res_neg.is_safe is False
    assert res_neg.hard_veto_triggered is True
    assert res_neg.blocking_veto_id == "V-S04_ESCALATED"
    assert res_neg.blocking_reason == "FUNDING_CROWDED_SHORT"
    assert res_neg.danger_flags["funding_overheating"] is True

    # Case C: Settlement window active (-5m to +15m) -> blocks BOTH by V-H17
    fund_window = FundingContextResult(
        funding_rate_pct=0.01,
        mark_index_divergence_pct=0.05,
        minutes_to_settlement=8.0,  # 8 mins to settlement
        is_funding_window_active=True,
        is_toxic_funding=False,
    )
    ctx_win = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=1000,
        candles=create_base_context().candles,
        funding_context=fund_window,
        oi_snapshot=create_base_context().oi_snapshot,
        oi_history=create_base_context().oi_history,
    )
    res_win = guard.evaluate_candidate(cand_long, ctx_win)
    assert res_win.is_safe is False
    assert res_win.blocking_veto_id == "V-H17"


def test_oi_and_price_divergence():
    """Verify detection of rapid contraction and trapped position crowding."""
    guard = ExtremeMarketRiskGuard()
    candidate = create_base_candidate(Direction.LONG)

    # Rapid OI contraction (> 5% drop)
    snaps_contraction = [
        OISnapshot("BTCUSDT", 0, 10000.0, 500_000_000.0),
        OISnapshot("BTCUSDT", 900000, 9300.0, 465_000_000.0),  # -7.0% drop
    ]
    ctx_contract = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=1000,
        candles=create_base_context().candles,
        funding_context=create_base_context().funding_context,
        oi_snapshot=snaps_contraction[-1],
        oi_history=snaps_contraction,
    )
    res = guard.evaluate_candidate(candidate, ctx_contract)
    assert res.danger_flags["oi_price_divergence"] is True
    assert res.soft_penalties >= 8

    # Trapped Longs / Aggressive Short Buildup (OI +5% while price dropped -2%)
    candles_dump = [
        Candle(0, 900000, 50000.0, 50100.0, 49800.0, 50000.0, 10.0),
        Candle(900000, 1800000, 50000.0, 50000.0, 48900.0, 49000.0, 20.0),  # -2.0% drop
    ]
    snaps_crowd = [
        OISnapshot("BTCUSDT", 0, 10000.0, 500_000_000.0),
        OISnapshot("BTCUSDT", 900000, 10500.0, 514_500_000.0),  # +5.0% expand
    ]
    ctx_crowd = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=1800000,
        candles=candles_dump,
        funding_context=create_base_context().funding_context,
        oi_snapshot=snaps_crowd[-1],
        oi_history=snaps_crowd,
    )
    res_crowd = guard.evaluate_candidate(candidate, ctx_crowd)
    assert res_crowd.danger_flags["oi_price_divergence"] is True


def test_spot_futures_cvd_divergence():
    """Verify perp-led rally without spot demand is flagged for LONG; perp-led dump for SHORT."""
    guard = ExtremeMarketRiskGuard()

    # LONG scenario: Perp CVD surging (+150), but Spot CVD falling (-50)
    perp_cvd_bull = CVDResult(
        total_delta=500.0, slope=150.0, has_turned_bullish=True, has_turned_bearish=False
    )
    spot_cvd_bear = CVDResult(
        total_delta=-200.0, slope=-50.0, has_turned_bullish=False, has_turned_bearish=True
    )

    ctx_long = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=1000,
        candles=create_base_context().candles,
        funding_context=create_base_context().funding_context,
        oi_snapshot=create_base_context().oi_snapshot,
        oi_history=create_base_context().oi_history,
        cvd_result=perp_cvd_bull,
        spot_cvd_result=spot_cvd_bear,
    )
    cand_long = create_base_candidate(Direction.LONG)
    res_long = guard.evaluate_candidate(cand_long, ctx_long)
    assert res_long.danger_flags["cvd_perp_spot_divergence"] is True
    assert res_long.soft_penalties >= 10

    # SHORT scenario: Perp CVD dumping (-150), but Spot CVD accumulating (+50)
    perp_cvd_bear = CVDResult(
        total_delta=-500.0, slope=-150.0, has_turned_bullish=False, has_turned_bearish=True
    )
    spot_cvd_bull = CVDResult(
        total_delta=200.0, slope=50.0, has_turned_bullish=True, has_turned_bearish=False
    )

    ctx_short = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=1000,
        candles=create_base_context().candles,
        funding_context=create_base_context().funding_context,
        oi_snapshot=create_base_context().oi_snapshot,
        oi_history=create_base_context().oi_history,
        cvd_result=perp_cvd_bear,
        spot_cvd_result=spot_cvd_bull,
    )
    cand_short = create_base_candidate(Direction.SHORT)
    res_short = guard.evaluate_candidate(cand_short, ctx_short)
    assert res_short.danger_flags["cvd_perp_spot_divergence"] is True
    assert res_short.soft_penalties >= 10


def test_orderbook_liquidity_void_and_staleness():
    """Verify orderbook staleness triggers V-H06, spread triggers V-H12, depth triggers V-H13."""
    guard = ExtremeMarketRiskGuard(default_clip_usd=1000.0)
    candidate = create_base_candidate(Direction.LONG)
    ctx = create_base_context()

    # 1. Stale orderbook (> 3s)
    res_stale = guard.evaluate_candidate(candidate, ctx, orderbook_age_sec=4.5)
    assert res_stale.is_safe is False
    assert res_stale.blocking_veto_id == "V-H06"

    # 2. Abnormal spread on CoinDCX (> 12 bps for MAJOR)
    wide_quote = CoinDCXQuote(
        pair="B-BTC_USDT",
        timestamp_ms=1000,
        price=50000.0,
        mark_price=50000.0,
        funding_rate=0.0,
        spread_bps=16.0,  # 16 > 12 bps limit
        top10_depth_usd=100000.0,
    )
    res_spread = guard.evaluate_candidate(
        candidate, ctx, quote=wide_quote, symbol_tier=SymbolTier.MAJOR
    )
    assert res_spread.is_safe is False
    assert res_spread.blocking_veto_id == "V-H12"

    # 3. Insufficient orderbook depth (< 20x $1000 clip = $20,000)
    shallow_quote = CoinDCXQuote(
        pair="B-BTC_USDT",
        timestamp_ms=1000,
        price=50000.0,
        mark_price=50000.0,
        funding_rate=0.0,
        spread_bps=4.0,
        top10_depth_usd=12000.0,  # $12k < $20k
    )
    res_depth = guard.evaluate_candidate(
        candidate, ctx, quote=shallow_quote, symbol_tier=SymbolTier.MAJOR
    )
    assert res_depth.is_safe is False
    assert res_depth.blocking_veto_id == "V-H13"

    # 4. Bid-side liquidity void via OBI (< -0.60)
    ctx_void = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=1000,
        candles=ctx.candles,
        funding_context=ctx.funding_context,
        oi_snapshot=ctx.oi_snapshot,
        oi_history=ctx.oi_history,
        obi_result=OBIResult(obi=-0.65, total_depth_bids=350.0, total_depth_asks=1000.0),
    )
    res_void = guard.evaluate_candidate(candidate, ctx_void)
    assert res_void.danger_flags["orderbook_liquidity_void"] is True


def test_structural_exhaustion_wilder_rsi_divergence():
    """Verify tested Wilder RSI divergence flags structural exhaustion bidirectionally."""
    guard = ExtremeMarketRiskGuard()

    # Bearish divergence for LONG candidate: price printed Higher High, but RSI printed Lower High
    rsi_bearish = RSIResult(
        rsi=72.0,
        rsi_series=[60.0, 75.0, 72.0],
        has_bearish_divergence=True,
        has_bullish_divergence=False,
        is_overbought=True,
        is_oversold=False,
    )
    ctx_bearish = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=1000,
        candles=create_base_context().candles,
        funding_context=create_base_context().funding_context,
        oi_snapshot=create_base_context().oi_snapshot,
        oi_history=create_base_context().oi_history,
        rsi_result=rsi_bearish,
    )
    cand_long = create_base_candidate(Direction.LONG)
    res_long = guard.evaluate_candidate(cand_long, ctx_bearish)
    assert res_long.danger_flags["structural_exhaustion"] is True

    # Bullish divergence for SHORT candidate: price printed Lower Low, but RSI printed Higher Low
    rsi_bullish = RSIResult(
        rsi=25.0,
        rsi_series=[40.0, 22.0, 25.0],
        has_bearish_divergence=False,
        has_bullish_divergence=True,
        is_overbought=False,
        is_oversold=True,
    )
    ctx_bullish = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=1000,
        candles=create_base_context().candles,
        funding_context=create_base_context().funding_context,
        oi_snapshot=create_base_context().oi_snapshot,
        oi_history=create_base_context().oi_history,
        rsi_result=rsi_bullish,
    )
    cand_short = create_base_candidate(Direction.SHORT)
    res_short = guard.evaluate_candidate(cand_short, ctx_bullish)
    assert res_short.danger_flags["structural_exhaustion"] is True


def test_composite_multi_danger_escalation():
    """Verify that 2 concurrent extreme danger flags escalate to a hard veto block."""
    guard = ExtremeMarketRiskGuard()
    candidate = create_base_candidate(Direction.LONG)

    # Activate Danger 1: Perp CVD without spot
    # Activate Danger 2: Bearish RSI divergence exhaustion
    perp_cvd_bull = CVDResult(
        total_delta=500.0, slope=150.0, has_turned_bullish=True, has_turned_bearish=False
    )
    spot_cvd_bear = CVDResult(
        total_delta=-200.0, slope=-50.0, has_turned_bullish=False, has_turned_bearish=True
    )
    rsi_bearish = RSIResult(
        rsi=74.0,
        rsi_series=[60.0, 78.0, 74.0],
        has_bearish_divergence=True,
        has_bullish_divergence=False,
        is_overbought=True,
        is_oversold=False,
    )

    ctx_dual_danger = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=1000,
        candles=create_base_context().candles,
        funding_context=create_base_context().funding_context,
        oi_snapshot=create_base_context().oi_snapshot,
        oi_history=create_base_context().oi_history,
        cvd_result=perp_cvd_bull,
        spot_cvd_result=spot_cvd_bear,
        rsi_result=rsi_bearish,
    )

    res = guard.evaluate_candidate(candidate, ctx_dual_danger)
    # Both flags active -> must escalate to HARD BLOCK!
    assert res.is_safe is False
    assert res.hard_veto_triggered is True
    assert res.blocking_veto_id == "V-H33_RISK_GUARD"
    assert res.blocking_reason == "COMPOSITE_EXTREME_MARKET_RISK"
