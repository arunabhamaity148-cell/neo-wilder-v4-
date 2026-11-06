"""Unit tests for Phase 8: Publish, Journal & Observability."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from neo_wilder.data.store import DatabaseStore
from neo_wilder.domain.enums import Direction, RegimeState
from neo_wilder.domain.models import Candle
from neo_wilder.journal.fills import FillJournal, parse_fill_command
from neo_wilder.journal.outcomes import OutcomeResolver
from neo_wilder.journal.signals import SignalJournal
from neo_wilder.observability.health import SystemHealthMonitor
from neo_wilder.observability.watchdog import DegradationLevel, ProcessWatchdog
from neo_wilder.publish.schema import Signal
from neo_wilder.publish.telegram import TelegramAlertPublisher


def create_sample_signal(sig_id: str = "SIG-TEST-001") -> Signal:
    return Signal(
        signal_id=sig_id,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        expires_at_utc=datetime.now(timezone.utc).isoformat(),
        symbol_binance="BTCUSDT",
        symbol_coindcx="B-BTC_USDT",
        direction=Direction.LONG,
        strategy_id="S1_SWEEP_RECLAIM",
        active_edge_ids=["E01", "E03", "E04"],
        confirming_edge_ids=["E15"],
        reference_price=50000.0,
        coindcx_price=50020.0,
        coindcx_spread_bps=4.5,
        coindcx_top10_depth_usd=150000.0,
        entry_zone_low=49950.0,
        entry_zone_high=50050.0,
        stop_loss=49500.0,
        tp1=51000.0,
        tp2=None,
        gross_rr=2.0,
        fee_pct=0.118,
        slippage_pct=0.0174,
        funding_pct_est=0.0,
        net_rr=1.85,
        score_0_100=88,
        calibrated_probability="NOT CALIBRATED",
        regime=RegimeState.MEAN_REVERSION_ROTATIONAL,
        btc_context="NEUTRAL",
        veto_status="CLEARED",
        soft_veto_list=[],
        max_entry_drift_pct=0.35,
        invalidation_conditions=["Bar closes below 49500.0"],
        one_paragraph_thesis="BTC রেঞ্জ সাপোর্ট টেস্ট করেছে এবং ভলিউম শোষণ দেখা গেছে।",
    )


def test_telegram_alert_formatting():
    """Verify Telegram alert formatting matches spec: /100 score, Bengali thesis, /fill note."""
    sig = create_sample_signal()
    text = TelegramAlertPublisher.format_signal(sig)

    assert "NEO-WILDER V4 SIGNAL ALERT" in text
    assert "BTCUSDT" in text
    assert "88/100" in text  # Must be /100, NEVER /200
    assert "NOT CALIBRATED" in text
    assert "BTC রেঞ্জ সাপোর্ট টেস্ট করেছে" in text
    assert "/fill SIG-TEST-001 <price> <size>" in text
    assert "Net R:R: 1.85" in text
    assert "Permanent SIGNAL_ONLY" in text


@pytest.mark.asyncio
async def test_signal_and_fill_journal(tmp_path: Path):
    """Verify SignalJournal records signals and FillJournal parses & stores manual fills."""
    db_file = tmp_path / "test_journal.db"
    store = DatabaseStore(db_file)
    await store.start()

    try:
        # 1. Log Signal
        sig_journal = SignalJournal(store)
        sig = create_sample_signal("SIG-20261106-001")
        await sig_journal.log_signal(sig)

        # 2. Parse Valid Fill Command
        valid_cmd = "/fill SIG-20261106-001 50010.5 0.25"
        parsed = parse_fill_command(valid_cmd)
        assert parsed == ("SIG-20261106-001", 50010.5, 0.25)

        # 3. Process Fill Command
        fill_journal = FillJournal(store)
        success, msg = await fill_journal.process_fill_command(valid_cmd)
        assert success is True
        assert "Fill recorded" in msg

        # 4. Invalid Fill Commands
        bad_cmd_1 = "/fill SIG-20261106-001 -100 0.5"  # negative price
        assert parse_fill_command(bad_cmd_1) is None
        success_bad, _ = await fill_journal.process_fill_command(bad_cmd_1)
        assert success_bad is False

        bad_cmd_2 = "/buy BTC 100"  # forbidden order command
        assert parse_fill_command(bad_cmd_2) is None

    finally:
        await store.stop()


@pytest.mark.asyncio
async def test_outcome_resolver_intrabar_ambiguity(tmp_path: Path):
    """Verify conservative intrabar ambiguity: bar hitting both SL and TP1 resolves SL_HIT."""
    db_file = tmp_path / "test_outcomes.db"
    store = DatabaseStore(db_file)
    await store.start()

    try:
        resolver = OutcomeResolver(store, max_entry_window_bars=4)
        sig = create_sample_signal("SIG-AMBIGUOUS-01")
        # Entry 50000, SL 49500, TP1 51000
        resolver.track_signal(sig, is_filled=True, fill_price=50000.0)

        # Candle that touches BOTH TP1 (51200) and SL (49400)
        ambiguous_bar = Candle(
            open_time_ms=1000,
            close_time_ms=2000,
            open=50000.0,
            high=51200.0,
            low=49400.0,
            close=50200.0,
            volume=50.0,
        )

        outcomes = await resolver.on_candle("BTCUSDT", ambiguous_bar)
        assert len(outcomes) == 1
        # Conservative rule: MUST BE SL_HIT
        assert outcomes[0]["status"] == "SL_HIT"
        assert outcomes[0]["r"] == "-1.00"

    finally:
        await store.stop()


@pytest.mark.asyncio
async def test_outcome_resolver_tp1_and_missed(tmp_path: Path):
    """Verify normal TP1 hit and missed fill expiry."""
    db_file = tmp_path / "test_outcomes2.db"
    store = DatabaseStore(db_file)
    await store.start()

    try:
        resolver = OutcomeResolver(store, max_entry_window_bars=2)
        sig1 = create_sample_signal("SIG-TP1-01")
        resolver.track_signal(sig1, is_filled=True, fill_price=50000.0)

        sig2 = create_sample_signal("SIG-UNFILLED-02")
        resolver.track_signal(sig2, is_filled=False)

        # Bar 1: Neutral
        neutral_bar = Candle(
            open_time_ms=1000,
            close_time_ms=2000,
            open=50000.0,
            high=50200.0,
            low=49800.0,
            close=50100.0,
            volume=10.0,
        )
        res1 = await resolver.on_candle("BTCUSDT", neutral_bar)
        assert len(res1) == 0

        # Bar 2: Neutral
        res2 = await resolver.on_candle("BTCUSDT", neutral_bar)
        assert len(res2) == 0

        # Bar 3: Hits TP1 for sig1; sig2 exceeds max_entry_window_bars (2) -> MISSED
        tp_bar = Candle(
            open_time_ms=3000,
            close_time_ms=4000,
            open=50100.0,
            high=51050.0,
            low=49900.0,
            close=51020.0,
            volume=20.0,
        )
        res3 = await resolver.on_candle("BTCUSDT", tp_bar)
        statuses = {r["signal_id"]: r["status"] for r in res3}
        assert statuses["SIG-TP1-01"] == "TP1_HIT"
        assert statuses["SIG-UNFILLED-02"] == "MISSED"

    finally:
        await store.stop()


@pytest.mark.asyncio
async def test_health_monitor_and_watchdog():
    """Verify resource monitor RSS checks and watchdog degradation ladder."""
    # 1. Health monitor
    health = SystemHealthMonitor()
    metrics, veto_flags = await health.check_health(clock_skew_ms=150.0)
    assert "rss_mb" in metrics
    assert metrics["rss_mb"] > 0.0
    assert veto_flags["V_H08"] is False  # Normal process < 300 MB
    assert veto_flags["V_H07"] is False  # Skew 150 < 1000 ms

    # Simulated skew breach
    _, veto_skew = await health.check_health(clock_skew_ms=1500.0)
    assert veto_skew["V_H07"] is True

    # 2. Watchdog
    dog = ProcessWatchdog(interval_seconds=10.0, max_misses=3)
    t0 = 1000.0
    dog.last_heartbeat = t0

    # Normal tick at 5s
    lvl = dog.evaluate_liveness(current_time=t0 + 5.0)
    assert lvl == DegradationLevel.NORMAL
    assert not dog.is_halted

    # Miss 1 interval at 15s
    lvl = dog.evaluate_liveness(current_time=t0 + 15.0)
    assert lvl == DegradationLevel.DEGRADED_WARNING
    assert not dog.is_halted

    # Miss 2 intervals at 25s
    lvl = dog.evaluate_liveness(current_time=t0 + 25.0)
    assert lvl == DegradationLevel.DEGRADED_SEVERE
    assert not dog.is_halted

    # Miss 3 intervals at 35s -> EMERGENCY HALT
    lvl = dog.evaluate_liveness(current_time=t0 + 35.0)
    assert lvl == DegradationLevel.EMERGENCY_HALT
    assert dog.is_halted
    assert dog.get_veto_flags()["V_H09"] is True
    assert dog.get_veto_flags()["V_H10"] is True

    # Beat restores to normal
    dog.beat()
    assert dog.evaluate_liveness() == DegradationLevel.NORMAL
    assert not dog.is_halted
