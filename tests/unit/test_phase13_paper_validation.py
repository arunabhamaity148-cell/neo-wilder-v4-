"""Unit tests for Phase 13: Manual Paper-Validation Implementation & Readiness."""

from pathlib import Path

import pytest

from neo_wilder.data.store import DatabaseStore
from neo_wilder.paper.auditor import (
    PaperValidationAuditor,
)


def test_paper_auditor_empty_and_insufficient_sample():
    """Verify auditor reports PENDING when trades are empty or < 100."""
    # 1. Empty trades
    rep_empty = PaperValidationAuditor.evaluate_trades([])
    assert rep_empty.total_trades == 0
    assert rep_empty.is_promotion_ready is False
    assert rep_empty.status == "MANUAL PAPER VALIDATION PENDING / NOT PROVEN"

    # 2. Only 50 trades (< 100 minimum required)
    synthetic_50 = [{"realized_r": 1.5 if i % 2 == 0 else -1.0} for i in range(50)]
    rep_50 = PaperValidationAuditor.evaluate_trades(synthetic_50)
    assert rep_50.total_trades == 50
    assert rep_50.is_sample_size_met is False
    assert rep_50.is_promotion_ready is False
    assert rep_50.status == "MANUAL PAPER VALIDATION PENDING / NOT PROVEN"


def test_paper_auditor_failing_metrics():
    """Verify auditor blocks promotion if win rate, profit factor, or drawdown fail."""
    # 100 trades with poor win rate: 30 wins (+1.0 R) and 70 losses (-1.0 R)
    poor_trades = [{"realized_r": 1.0} for _ in range(30)] + [
        {"realized_r": -1.0} for _ in range(70)
    ]
    rep_poor = PaperValidationAuditor.evaluate_trades(poor_trades)
    assert rep_poor.total_trades == 100
    assert rep_poor.is_sample_size_met is True
    assert rep_poor.is_win_rate_met is False  # 30% < 45%
    assert rep_poor.is_profit_factor_met is False
    assert rep_poor.is_expectancy_met is False
    assert rep_poor.is_promotion_ready is False
    assert rep_poor.status == "MANUAL PAPER VALIDATION PENDING / NOT PROVEN"

    # 100 trades with severe drawdown > 6.0 R (e.g. losing streak of 8 consecutive -1.0 R losses)
    dd_trades = [{"realized_r": -1.0} for _ in range(8)] + [{"realized_r": 1.5} for _ in range(92)]
    rep_dd = PaperValidationAuditor.evaluate_trades(dd_trades)
    assert rep_dd.max_drawdown_r >= 8.0
    assert rep_dd.is_drawdown_met is False  # 8.0 > 6.0 R
    assert rep_dd.is_promotion_ready is False


def test_paper_auditor_successful_promotion_gate():
    """Verify auditor approves promotion when all 5 empirical gates are met."""
    # 100 trades: 55 wins (+1.8 R) and 45 losses (-1.0 R)
    # Win rate = 55% (>= 45%)
    # Profit = 55 * 1.8 = 99.0 R; Loss = 45 * 1.0 = 45.0 R -> PF = 99.0 / 45.0 = 2.20 (>= 1.40)
    # Expectancy = (0.55 * 1.8) - (0.45 * 1.0) = 0.99 - 0.45 = +0.54 R (>= +0.35 R)
    # Alternating sequence keeps drawdown low (~2.0 R <= 6.0 R)
    good_trades = []
    for i in range(100):
        if i < 55:
            good_trades.append({"realized_r": 1.8})
        else:
            good_trades.append({"realized_r": -1.0})

    # Interleave to ensure drawdown is well controlled
    interleaved = []
    w_idx = 0
    l_idx = 55
    while w_idx < 55 or l_idx < 100:
        if w_idx < 55:
            interleaved.append(good_trades[w_idx])
            w_idx += 1
        if l_idx < 100:
            interleaved.append(good_trades[l_idx])
            l_idx += 1

    rep_good = PaperValidationAuditor.evaluate_trades(interleaved)
    assert rep_good.total_trades == 100
    assert rep_good.is_sample_size_met is True
    assert rep_good.is_win_rate_met is True
    assert rep_good.is_profit_factor_met is True
    assert rep_good.is_expectancy_met is True
    assert rep_good.is_drawdown_met is True
    assert rep_good.is_promotion_ready is True
    assert rep_good.status == "PROMOTION_READY"


@pytest.mark.asyncio
async def test_paper_auditor_store_integration(tmp_path: Path):
    """Verify PaperValidationAuditor queries real database fills and outcomes."""
    db_file = tmp_path / "test_paper_store.db"
    store = DatabaseStore(db_file)
    await store.start()

    try:
        # Initially empty
        rep0 = PaperValidationAuditor.audit_store(store)
        assert rep0.total_trades == 0
        assert rep0.status == "MANUAL PAPER VALIDATION PENDING / NOT PROVEN"

        # Record 2 manual fills and their outcomes
        await store.record_fill("SIG-001", 50000.0, 0.1, "2026-11-06T12:00:00Z")
        await store.record_outcome("SIG-001", "TP1_HIT", 51000.0, 1.85, "2026-11-06T13:00:00Z")

        await store.record_fill("SIG-002", 50000.0, 0.1, "2026-11-06T12:00:00Z")
        await store.record_outcome("SIG-002", "SL_HIT", 49500.0, -1.0, "2026-11-06T13:00:00Z")

        # Give async writer loop a moment to flush batch
        import asyncio

        await asyncio.sleep(0.2)

        rep = PaperValidationAuditor.audit_store(store)
        assert rep.total_trades == 2
        assert rep.wins == 1
        assert rep.losses == 1
        assert rep.is_sample_size_met is False  # 2 < 100
        assert rep.status == "MANUAL PAPER VALIDATION PENDING / NOT PROVEN"

    finally:
        await store.stop()
