"""Manual Paper Validation Auditor for NEO-WILDER V4.

Operates strictly on self-reported operator fills (/fill command) and resolved outcomes.
Permanent SIGNAL_ONLY constraint: NO automated paper execution allowed.
Enforces empirical validation gates before live capital allocation:
- Minimum 100 resolved manual paper trades with verified /fill records.
- Realized win rate >= 45.0%.
- Realized net profit factor >= 1.40.
- Realized net expectancy >= +0.35 R.
- Realized maximum drawdown <= 6.0 R.

States honestly: 'MANUAL PAPER VALIDATION PENDING / NOT PROVEN' if gates are not met.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np

from neo_wilder.data.store import DatabaseStore

logger = logging.getLogger(__name__)

# Mandatory validation thresholds per ROADMAP
MIN_RESOLVED_PAPER_TRADES = 100
MIN_WIN_RATE = 0.45  # 45%
MIN_PROFIT_FACTOR = 1.40
MIN_EXPECTANCY_R = 0.35  # +0.35 R
MAX_DRAWDOWN_R = 6.0  # 6.0 R


@dataclass
class PaperAuditReport:
    total_trades: int
    wins: int
    losses: int
    win_rate: float
    net_profit_factor: float
    net_expectancy_r: float
    max_drawdown_r: float
    is_sample_size_met: bool
    is_win_rate_met: bool
    is_profit_factor_met: bool
    is_expectancy_met: bool
    is_drawdown_met: bool
    is_promotion_ready: bool
    status: str


class PaperValidationAuditor:
    """Audits real operator fills and outcomes from DatabaseStore."""

    @classmethod
    def evaluate_trades(cls, trades: List[Dict[str, Any]]) -> PaperAuditReport:
        """Compute performance statistics on resolved paper trades."""
        total = len(trades)
        if total == 0:
            return PaperAuditReport(
                total_trades=0,
                wins=0,
                losses=0,
                win_rate=0.0,
                net_profit_factor=0.0,
                net_expectancy_r=0.0,
                max_drawdown_r=0.0,
                is_sample_size_met=False,
                is_win_rate_met=False,
                is_profit_factor_met=False,
                is_expectancy_met=False,
                is_drawdown_met=False,
                is_promotion_ready=False,
                status="MANUAL PAPER VALIDATION PENDING / NOT PROVEN",
            )

        realized_rs = np.array([float(t.get("realized_r", 0.0)) for t in trades])
        wins = realized_rs[realized_rs > 0]
        losses = realized_rs[realized_rs <= 0]

        n_wins = len(wins)
        n_losses = len(losses)
        win_rate = n_wins / total

        gross_profit = float(np.sum(wins)) if n_wins > 0 else 0.0
        gross_loss = float(abs(np.sum(losses))) if n_losses > 0 else 0.0
        profit_factor = gross_profit / max(gross_loss, 1e-4)

        avg_win = float(np.mean(wins)) if n_wins > 0 else 0.0
        avg_loss = float(np.mean(losses)) if n_losses > 0 else 0.0
        expectancy_r = (win_rate * avg_win) + ((1.0 - win_rate) * avg_loss)

        # Drawdown in R (peak-to-trough from initial equity 0.0)
        cumulative = np.insert(np.cumsum(realized_rs), 0, 0.0)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = running_max - cumulative
        max_dd_r = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

        # Evaluate Gates
        sample_met = total >= MIN_RESOLVED_PAPER_TRADES
        win_rate_met = win_rate >= MIN_WIN_RATE
        pf_met = profit_factor >= MIN_PROFIT_FACTOR
        exp_met = expectancy_r >= MIN_EXPECTANCY_R
        dd_met = max_dd_r <= MAX_DRAWDOWN_R

        ready = sample_met and win_rate_met and pf_met and exp_met and dd_met
        status = "PROMOTION_READY" if ready else "MANUAL PAPER VALIDATION PENDING / NOT PROVEN"

        return PaperAuditReport(
            total_trades=total,
            wins=n_wins,
            losses=n_losses,
            win_rate=win_rate,
            net_profit_factor=profit_factor,
            net_expectancy_r=expectancy_r,
            max_drawdown_r=max_dd_r,
            is_sample_size_met=sample_met,
            is_win_rate_met=win_rate_met,
            is_profit_factor_met=pf_met,
            is_expectancy_met=exp_met,
            is_drawdown_met=dd_met,
            is_promotion_ready=ready,
            status=status,
        )

    @classmethod
    def audit_store(cls, store: DatabaseStore) -> PaperAuditReport:
        """Query DatabaseStore and run audit on operator paper trades."""
        trades = store.fetch_resolved_paper_trades()
        return cls.evaluate_trades(trades)
