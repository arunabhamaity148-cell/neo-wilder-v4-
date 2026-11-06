"""Leave-one-out Edge Ablation Harness for NEO-WILDER V4 Research.

Conforms strictly to BACKTEST_PROTOCOL.md §5:
Evaluates baseline portfolio performance vs (Baseline minus E_xx).
Verifies statistical justification for each ACTIVE edge status.
"""

from dataclasses import dataclass
from typing import Dict, List

import numpy as np

from research.backtest.engine import BacktestEngine, BacktestReport


@dataclass
class AblationRow:
    edge_id: str
    baseline_expectancy_r: float
    ablated_expectancy_r: float
    delta_expectancy_r: float
    baseline_trades: int
    ablated_trades: int
    trade_count_loss_pct: float
    false_positive_reduction_pct: float
    is_active_justified: bool
    recommendation: str  # "RETAIN_ACTIVE" or "DEMOTE_TO_SHADOW"


class EdgeAblationHarness:
    """Runs leave-one-out ablation experiments on registered edges."""

    def __init__(self, engine: BacktestEngine):
        self.engine = engine

    def run_ablation(
        self,
        signals_pool: List[Dict],
        active_edge_ids: List[str],
        highs: np.ndarray,
        lows: np.ndarray,
        opens: np.ndarray,
        closes: np.ndarray,
        atrs: np.ndarray,
    ) -> List[AblationRow]:
        """Perform leave-one-out ablation for each active edge in the list."""
        # 1. Baseline Run: all active edges present
        baseline_signals = [
            s
            for s in signals_pool
            if all(edge in s.get("active_edges", []) for edge in active_edge_ids)
        ]
        baseline_trades = self.engine.simulate_trades(
            baseline_signals, highs, lows, opens, closes, atrs
        )
        baseline_report: BacktestReport = self.engine.evaluate(baseline_trades)

        base_exp = baseline_report.expectancy_r
        base_count = baseline_report.filled_trades
        base_losses = baseline_report.losses

        rows: List[AblationRow] = []

        # 2. Iterate each edge and ablate (exclude from requirement)
        for target_edge in active_edge_ids:
            # Ablated subset: required edges WITHOUT target_edge
            required_subset = [e for e in active_edge_ids if e != target_edge]

            ablated_signals = [
                s
                for s in signals_pool
                if all(e in s.get("active_edges", []) for e in required_subset)
                and target_edge not in s.get("active_edges", [])
            ]

            ablated_trades = self.engine.simulate_trades(
                ablated_signals, highs, lows, opens, closes, atrs
            )
            ablated_report: BacktestReport = self.engine.evaluate(ablated_trades)

            abl_exp = ablated_report.expectancy_r
            abl_count = ablated_report.filled_trades
            abl_losses = ablated_report.losses

            delta_exp = abl_exp - base_exp
            trade_loss_pct = (
                ((base_count - abl_count) / max(base_count, 1)) * 100.0 if base_count > 0 else 0.0
            )

            fp_reduction_pct = (
                ((base_losses - abl_losses) / max(base_losses, 1)) * 100.0
                if base_losses > 0
                else 0.0
            )

            # Rule §5: Justified ACTIVE if removing it drops expectancy OR
            # provides >= 15% reduction in false positives with <= 10% loss of trade count
            is_justified = (delta_exp < -0.05) or (
                fp_reduction_pct >= 15.0 and trade_loss_pct <= 10.0
            )
            recommendation = "RETAIN_ACTIVE" if is_justified else "DEMOTE_TO_SHADOW"

            rows.append(
                AblationRow(
                    edge_id=target_edge,
                    baseline_expectancy_r=base_exp,
                    ablated_expectancy_r=abl_exp,
                    delta_expectancy_r=delta_exp,
                    baseline_trades=base_count,
                    ablated_trades=abl_count,
                    trade_count_loss_pct=trade_loss_pct,
                    false_positive_reduction_pct=fp_reduction_pct,
                    is_active_justified=is_justified,
                    recommendation=recommendation,
                )
            )

        return rows
