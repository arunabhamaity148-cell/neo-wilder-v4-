"""Purged Walk-Forward Cross-Validation Engine for NEO-WILDER V4.

Conforms strictly to BACKTEST_PROTOCOL.md §4:
- 12 months train / 3 months test / 3 months roll.
- Purge 24 bars at each boundary to eliminate look-ahead leakage.
- Calculates Out-of-Sample (OOS) degradation percentage.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

from research.backtest.engine import BacktestEngine, BacktestReport


@dataclass
class WalkForwardFoldResult:
    fold_idx: int
    train_bars: Tuple[int, int]
    test_bars: Tuple[int, int]
    train_trades_count: int
    test_trades_count: int
    is_expectancy: float
    oos_expectancy: float
    degradation_pct: float


class PurgedWalkForwardValidator:
    """Walk-forward splits with purge window between in-sample and out-of-sample segments."""

    def __init__(
        self,
        train_bars: int = 35040,  # 12 months of 15m bars (~35,040)
        test_bars: int = 8760,  # 3 months of 15m bars (~8,760)
        roll_bars: int = 8760,  # 3 months roll (~8,760)
        purge_bars: int = 24,  # 24 bars purge boundary (6 hours)
    ):
        self.train_bars = train_bars
        self.test_bars = test_bars
        self.roll_bars = roll_bars
        self.purge_bars = purge_bars
        self.engine = BacktestEngine(bootstrap_iterations=1000)

    def generate_folds(self, total_bars: int) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """Generate list of ((train_start, train_end), (test_start, test_end)) intervals."""
        folds = []
        train_start = 0

        while True:
            train_end = train_start + self.train_bars
            test_start = train_end + self.purge_bars
            test_end = test_start + self.test_bars

            if test_end > total_bars:
                break

            folds.append(((train_start, train_end), (test_start, test_end)))
            train_start += self.roll_bars

        return folds

    def evaluate_walk_forward(
        self,
        signals: List[Dict],
        highs: np.ndarray,
        lows: np.ndarray,
        opens: np.ndarray,
        closes: np.ndarray,
        atrs: np.ndarray,
    ) -> Dict:
        """Run walk-forward validation across all available folds."""
        total_bars = len(closes)
        folds = self.generate_folds(total_bars)
        fold_results: List[WalkForwardFoldResult] = []

        all_trades = self.engine.simulate_trades(signals, highs, lows, opens, closes, atrs)

        for idx, (train_range, test_range) in enumerate(folds):
            train_start, train_end = train_range
            test_start, test_end = test_range

            train_trades = [
                t
                for t in all_trades
                if train_start <= t.entry_bar_idx < train_end and t.exit_reason != "MISSED"
            ]
            test_trades = [
                t
                for t in all_trades
                if test_start <= t.entry_bar_idx < test_end and t.exit_reason != "MISSED"
            ]

            is_rep: BacktestReport = self.engine.evaluate(train_trades)
            oos_rep: BacktestReport = self.engine.evaluate(test_trades)

            is_exp = is_rep.expectancy_r
            oos_exp = oos_rep.expectancy_r

            degradation = ((is_exp - oos_exp) / max(abs(is_exp), 1e-4)) * 100.0

            fold_results.append(
                WalkForwardFoldResult(
                    fold_idx=idx,
                    train_bars=(train_start, train_end),
                    test_bars=(test_start, test_end),
                    train_trades_count=len(train_trades),
                    test_trades_count=len(test_trades),
                    is_expectancy=is_exp,
                    oos_expectancy=oos_exp,
                    degradation_pct=degradation,
                )
            )

        avg_oos_exp = (
            float(np.mean([f.oos_expectancy for f in fold_results])) if fold_results else 0.0
        )
        avg_deg = float(np.mean([f.degradation_pct for f in fold_results])) if fold_results else 0.0

        return {
            "total_folds": len(fold_results),
            "fold_results": fold_results,
            "mean_oos_expectancy": avg_oos_exp,
            "mean_degradation_pct": avg_deg,
        }
