"""Unit tests for Phase 6: Hard/Soft Veto Framework."""

from neo_wilder.clock import SystemClock
from neo_wilder.domain.enums import Direction, RegimeState
from neo_wilder.domain.models import Candidate, Candle, CoinDCXQuote, OISnapshot
from neo_wilder.edges.base import FeatureContext
from neo_wilder.features.atr import ATRResult
from neo_wilder.features.funding import FundingContextResult
from neo_wilder.vetoes.governor import PortfolioGovernor
from neo_wilder.vetoes.pipeline import VetoPipeline


def _build_valid_candidate_and_context():
    ref_price = 70000.0
    stop_loss = 69300.0  # Stop dist = 700 (1.0% > 0.65%, 2.33 ATR)
    tp1 = 71500.0  # Reward = 1500, R:R ~ 2.14

    candidate = Candidate(
        symbol="BTCUSDT",
        direction=Direction.LONG,
        strategy_id="S1_SWEEP_RECLAIM",
        setup_edge_id="E01",
        reference_price=ref_price,
        entry_zone_low=69900.0,
        entry_zone_high=ref_price,
        stop_loss=stop_loss,
        tp1=tp1,
        tp2=None,
        gross_rr=2.14,
        net_rr=2.00,
        active_edge_ids=["E01", "E04", "E11", "E12"],
        confirming_edge_ids=["E05"],
        expiry_bars=16,
        regime=RegimeState.MEAN_REVERSION_ROTATIONAL,
        created_at_utc="2026-11-06T12:00:00Z",
    )

    now_ms = 1700000000000
    candles = [
        Candle(
            open_time_ms=now_ms - (20 - i) * 900000,
            close_time_ms=now_ms - (19 - i) * 900000 - 1,
            open=70000.0,
            high=70100.0,
            low=69900.0,
            close=70000.0,
            volume=500.0,
        )
        for i in range(20)
    ]

    atr_res = ATRResult(atr=300.0, atr_bps=42.0, vol_tier=1, trailing_100_atr=[300.0] * 20)
    funding_res = FundingContextResult(
        funding_rate_pct=0.01,
        mark_index_divergence_pct=0.08,
        minutes_to_settlement=180.0,
        is_funding_window_active=False,
        is_toxic_funding=False,
    )

    oi_snaps = [
        OISnapshot("BTCUSDT", candles[-2].close_time_ms, 10000.0, 700_000_000.0),
        OISnapshot("BTCUSDT", candles[-1].close_time_ms, 10005.0, 700_350_000.0),
    ]

    ctx = FeatureContext(
        symbol="BTCUSDT",
        timeframe="15m",
        now_ms=candles[-1].close_time_ms + 60000,
        candles=candles,
        atr_result=atr_res,
        funding_context=funding_res,
        oi_snapshot=oi_snaps[-1],
        oi_history=oi_snaps,
    )

    quote = CoinDCXQuote(
        pair="B-BTC_USDT",
        timestamp_ms=ctx.now_ms,
        price=70050.0,  # 50 / 70000 = 0.07% drift (<= 0.35%)
        mark_price=70050.0,
        funding_rate=0.0001,
        spread_bps=3.5,  # <= 12 bps
        top10_depth_usd=250000.0,  # >= $10,000
    )

    return candidate, ctx, quote


def test_veto_pipeline_clean_candidate_passes():
    candidate, ctx, quote = _build_valid_candidate_and_context()
    pipeline = VetoPipeline()
    clock = SystemClock()

    passed, hard_res, soft_res = pipeline.evaluate_candidate(
        candidate=candidate,
        ctx=ctx,
        quote=quote,
        clock=clock,
    )
    assert passed is True
    assert hard_res.passed is True
    assert len(soft_res.active_soft_vetoes) == 0


def test_veto_score_100_with_veto_must_block():
    """Verify that a candidate that would score 100/100 is strictly blocked if a veto fires."""
    candidate, ctx, quote = _build_valid_candidate_and_context()
    pipeline = VetoPipeline()
    clock = SystemClock()

    # Inject V-H05: WebSocket disconnected > 5s
    passed, hard_res, _ = pipeline.evaluate_candidate(
        candidate=candidate,
        ctx=ctx,
        quote=quote,
        clock=clock,
        is_ws_disconnected=True,
    )
    assert passed is False
    assert hard_res.blocking_id == "V-H05"
    assert hard_res.reason_code == "WS_DISCONNECTED"


def test_veto_execution_drift_block():
    """Verify V-H32 blocks when price drift > 0.35%."""
    candidate, ctx, quote = _build_valid_candidate_and_context()
    pipeline = VetoPipeline()
    clock = SystemClock()

    # CoinDCX price drifts by $350 (0.50% > 0.35%)
    drifted_quote = CoinDCXQuote(
        pair="B-BTC_USDT",
        timestamp_ms=ctx.now_ms,
        price=70350.0,
        mark_price=70350.0,
        funding_rate=0.0001,
        spread_bps=3.5,
        top10_depth_usd=250000.0,
    )

    passed, hard_res, _ = pipeline.evaluate_candidate(
        candidate=candidate,
        ctx=ctx,
        quote=drifted_quote,
        clock=clock,
    )
    assert passed is False
    assert hard_res.blocking_id == "V-H32"
    assert hard_res.reason_code == "ENTRY_DRIFT_EXCEEDED"


def test_veto_coindcx_feed_missing_block():
    """Verify V-H31 blocks fail-closed when CoinDCX validation quote is None."""
    candidate, ctx, _ = _build_valid_candidate_and_context()
    pipeline = VetoPipeline()
    clock = SystemClock()

    passed, hard_res, _ = pipeline.evaluate_candidate(
        candidate=candidate,
        ctx=ctx,
        quote=None,
        clock=clock,
    )
    assert passed is False
    assert hard_res.blocking_id == "V-H31"
    assert hard_res.reason_code == "COINDCX_FEED_UNAVAILABLE"


def test_veto_governor_concurrency_and_loss_caps():
    candidate, ctx, quote = _build_valid_candidate_and_context()
    gov = PortfolioGovernor(max_concurrent=2, max_daily_loss_pct=3.0)
    pipeline = VetoPipeline(governor=gov)
    clock = SystemClock()

    # Simulate 2 active positions (V-H26)
    gov.state.open_positions = [{"id": 1}, {"id": 2}]
    passed_heat, hard_heat, _ = pipeline.evaluate_candidate(
        candidate=candidate,
        ctx=ctx,
        quote=quote,
        clock=clock,
    )
    assert passed_heat is False
    assert hard_heat.blocking_id == "V-H26"

    # Reset positions and simulate daily drawdown 3.5% >= 3.0% (V-H28)
    gov.state.open_positions.clear()
    gov.state.current_equity = 9650.0  # -3.5%
    passed_loss, hard_loss, _ = pipeline.evaluate_candidate(
        candidate=candidate,
        ctx=ctx,
        quote=quote,
        clock=clock,
    )
    assert passed_loss is False
    assert hard_loss.blocking_id == "V-H28"


def test_soft_veto_escalation_btc_crash():
    """Verify V-S01 escalates to Hard Veto when BTC 5m return < -1.0%."""
    candidate, ctx, quote = _build_valid_candidate_and_context()
    pipeline = VetoPipeline()
    clock = SystemClock()

    # Inject sharp BTC crash: -1.2%
    ctx_crash = FeatureContext(
        symbol=ctx.symbol,
        timeframe=ctx.timeframe,
        now_ms=ctx.now_ms,
        candles=ctx.candles,
        atr_result=ctx.atr_result,
        funding_context=ctx.funding_context,
        oi_snapshot=ctx.oi_snapshot,
        oi_history=ctx.oi_history,
        btc_5m_return=-0.012,
    )

    passed, hard_res, _ = pipeline.evaluate_candidate(
        candidate=candidate,
        ctx=ctx_crash,
        quote=quote,
        clock=clock,
    )
    assert passed is False
    assert hard_res.blocking_id == "V-S01"


def test_v_h06_orderbook_stale_blocks():
    """Verify V-H06 blocks fail-closed when orderbook depth is stale > 3s."""
    candidate, ctx, quote = _build_valid_candidate_and_context()
    pipeline = VetoPipeline()
    clock = SystemClock()

    passed, hard_res, _ = pipeline.evaluate_candidate(
        candidate=candidate,
        ctx=ctx,
        quote=quote,
        clock=clock,
        is_orderbook_stale=True,
    )
    assert passed is False
    assert hard_res.blocking_id == "V-H06"
    assert hard_res.reason_code == "ORDERBOOK_STALE"


def test_v_s11_weak_orderflow_confidence_penalty():
    """Verify V-S11 applies confidence penalty when CVD opposes trade direction."""
    from neo_wilder.features.cvd import CVDResult

    candidate, ctx, quote = _build_valid_candidate_and_context()
    pipeline = VetoPipeline()
    clock = SystemClock()

    # LONG candidate with negative CVD slope (selling into rally)
    ctx_opposing_cvd = FeatureContext(
        symbol=ctx.symbol,
        timeframe=ctx.timeframe,
        now_ms=ctx.now_ms,
        candles=ctx.candles,
        atr_result=ctx.atr_result,
        funding_context=ctx.funding_context,
        oi_snapshot=ctx.oi_snapshot,
        oi_history=ctx.oi_history,
        cvd_result=CVDResult(
            total_delta=-50000.0,
            slope=-12.5,
            has_turned_bullish=False,
            has_turned_bearish=True,
        ),
    )

    passed, _, soft_res = pipeline.evaluate_candidate(
        candidate=candidate,
        ctx=ctx_opposing_cvd,
        quote=quote,
        clock=clock,
    )
    assert passed is True
    assert "V-S11" in soft_res.active_soft_vetoes
    assert soft_res.confidence_penalty >= 10.0


def test_fresh_governor_unlocked_and_cooldown():
    """Verify PortfolioGovernor fresh startup unlock and symbol cooldown (DEF-07/P0-07)."""
    gov = PortfolioGovernor(cooldown_sec=1800.0)

    # 1. Fresh startup must NEVER lock symbols
    assert gov.is_symbol_locked("BTCUSDT") is False
    assert gov.is_symbol_locked("ETHUSDT") is False

    # 2. Record signal for BTCUSDT
    gov.record_signal_published("BTCUSDT", direction="LONG", strategy="S1_SWEEP_RECLAIM")
    assert gov.is_symbol_locked("BTCUSDT") is True

    # 3. Different symbol must remain unlocked
    assert gov.is_symbol_locked("ETHUSDT") is False

    # 4. Advance simulated time past cooldown (1801s)
    gov.state.symbol_last_signal_time["BTCUSDT"] -= 1801.0
    assert gov.is_symbol_locked("BTCUSDT") is False


def test_v_h27_cluster_heat_limit():
    """Verify V-H27 blocks when cluster open risk exceeds 2.0R."""
    candidate, ctx, quote = _build_valid_candidate_and_context()
    pipeline = VetoPipeline()
    clock = SystemClock()

    # Pass cluster_risk_r = 2.5R (> 2.0R cap)
    passed, hard_res, _ = pipeline.evaluate_candidate(
        candidate=candidate,
        ctx=ctx,
        quote=quote,
        clock=clock,
        cluster_risk_r=2.5,
    )
    assert passed is False
    assert hard_res.blocking_id == "V-H27"
    assert hard_res.reason_code == "CLUSTER_HEAT"
