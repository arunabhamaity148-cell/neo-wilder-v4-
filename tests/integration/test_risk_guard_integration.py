"""Integration tests for Extreme Market Risk Guard within the master VetoPipeline.

Proves that candidates triggering extreme risk conditions are blocked from publication,
even with a 100/100 quality score, and that S1 short-side candidates remain ABSTAIN.
"""

from neo_wilder.clock import SystemClock
from neo_wilder.domain.enums import Direction, RegimeState
from neo_wilder.domain.models import Candidate, Candle, CoinDCXQuote, OISnapshot
from neo_wilder.edges.base import FeatureContext
from neo_wilder.features.atr import ATRResult
from neo_wilder.features.cvd import CVDResult
from neo_wilder.features.funding import FundingContextResult
from neo_wilder.features.rsi import RSIResult
from neo_wilder.strategies.s1_sweep_reclaim import S1SweepReclaimStrategy
from neo_wilder.vetoes.pipeline import VetoPipeline


def test_pipeline_blocks_candidate_under_extreme_funding():
    """Verify that VetoPipeline intercepts and blocks candidate with extreme funding crowding."""
    pipeline = VetoPipeline()
    clock = SystemClock()

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

    candle = Candle(
        open_time_ms=0,
        close_time_ms=900000,
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50050.0,
        volume=10.0,
    )
    # Toxic positive funding (+0.07% > +0.05%)
    toxic_fund = FundingContextResult(
        funding_rate_pct=0.07,
        mark_index_divergence_pct=0.05,
        minutes_to_settlement=180.0,
        is_funding_window_active=False,
        is_toxic_funding=True,
    )
    oi_snaps = [
        OISnapshot("BTCUSDT", 0, 10000.0, 500_000_000.0),
        OISnapshot("BTCUSDT", 900000, 10010.0, 500_500_000.0),
    ]

    ctx = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=900000,
        candles=[candle],
        funding_context=toxic_fund,
        oi_snapshot=oi_snaps[-1],
        oi_history=oi_snaps,
        atr_result=ATRResult(atr=300.0, atr_bps=60.0, vol_tier=1, trailing_100_atr=[300.0]),
    )

    quote_valid = CoinDCXQuote(
        pair="B-BTC_USDT",
        timestamp_ms=900000,
        price=50010.0,
        mark_price=50010.0,
        funding_rate=0.0001,
        spread_bps=4.5,
        top10_depth_usd=150000.0,
    )

    passed, hard_res, soft_res = pipeline.evaluate_candidate(
        candidate=candidate,
        ctx=ctx,
        quote=quote_valid,
        clock=clock,
    )

    # Must be FAIL-CLOSED blocked by Risk Guard!
    assert passed is False
    assert hard_res.passed is False
    assert hard_res.blocking_id == "V-S04_ESCALATED"
    assert hard_res.reason_code == "FUNDING_CROWDED_LONG"


def test_pipeline_blocks_composite_risk_even_if_score_100():
    """Verify that even if hypothetical score is 100, concurrent risk guard flags block publication."""
    pipeline = VetoPipeline()
    clock = SystemClock()

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
        active_edge_ids=["E01", "E03", "E04", "E11", "E12", "E15"],
        confirming_edge_ids=[],
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
    # Dual extreme risk flags:
    # 1. Perp CVD up, Spot CVD down
    # 2. Bearish RSI divergence
    ctx_dual = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=900000,
        candles=[candle],
        funding_context=FundingContextResult(
            funding_rate_pct=0.01,
            mark_index_divergence_pct=0.05,
            minutes_to_settlement=120.0,
            is_funding_window_active=False,
            is_toxic_funding=False,
        ),
        oi_snapshot=OISnapshot("BTCUSDT", 900000, 10000.0, 500_000_000.0),
        oi_history=[
            OISnapshot("BTCUSDT", 0, 10000.0, 500_000_000.0),
            OISnapshot("BTCUSDT", 900000, 10000.0, 500_000_000.0),
        ],
        atr_result=ATRResult(atr=300.0, atr_bps=60.0, vol_tier=1, trailing_100_atr=[300.0]),
        cvd_result=CVDResult(
            total_delta=500.0, slope=100.0, has_turned_bullish=True, has_turned_bearish=False
        ),
        spot_cvd_result=CVDResult(
            total_delta=-200.0, slope=-50.0, has_turned_bullish=False, has_turned_bearish=True
        ),
        rsi_result=RSIResult(
            rsi=74.0,
            rsi_series=[60.0, 74.0],
            has_bearish_divergence=True,
            has_bullish_divergence=False,
            is_overbought=True,
            is_oversold=False,
        ),
    )

    quote_valid = CoinDCXQuote(
        pair="B-BTC_USDT",
        timestamp_ms=900000,
        price=50010.0,
        mark_price=50010.0,
        funding_rate=0.0001,
        spread_bps=4.5,
        top10_depth_usd=150000.0,
    )

    passed, hard_res, _ = pipeline.evaluate_candidate(
        candidate=candidate,
        ctx=ctx_dual,
        quote=quote_valid,
        clock=clock,
        publish_threshold=85.0,
    )

    assert passed is False
    assert hard_res.blocking_id == "V-H33_RISK_GUARD"
    assert hard_res.reason_code == "COMPOSITE_EXTREME_MARKET_RISK"


def test_s1_short_strategy_remains_fail_closed_disabled():
    """Verify S1 short candidate generation remains strictly disabled (ABSTAIN)."""
    from neo_wilder.domain.models import EdgeResult

    s1 = S1SweepReclaimStrategy()
    candle = Candle(0, 900000, 50000.0, 50100.0, 49900.0, 50050.0, 10.0)
    ctx = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=900000,
        candles=[candle],
    )

    # Attempt short side setup
    edge_results_short = {
        "E01": EdgeResult(
            edge_id="E01",
            passed=True,
            confidence=1.0,
            direction=Direction.SHORT,
            score_contribution=8,
        )
    }

    short_cand = s1.generate_candidate(ctx, edge_results=edge_results_short)
    assert short_cand is None, (
        "S1 Short setups must remain disabled (ABSTAIN) until formulas are proven"
    )
