"""Lo-MacKinlay Variance Ratio composite regime classification for NEO-WILDER V4 (E25).

Causal, 3 continuous state variables mapped to canonical RegimeState.
"""

from dataclasses import dataclass
from typing import List

import numpy as np

from neo_wilder.domain.enums import RegimeState
from neo_wilder.domain.models import Candle


@dataclass(frozen=True)
class RegimeOutput:
    """Composite regime evaluation."""

    state: RegimeState
    variance_ratio: float
    atr_bps: float
    is_stress: bool


class RegimeClassifier:
    """Lo-MacKinlay Variance Ratio and volatility composite tracker."""

    def __init__(self, hysteresis_bars: int = 3, vr_deadband: float = 0.03):
        self.hysteresis_bars = hysteresis_bars
        self.vr_deadband = vr_deadband
        self._current_state = RegimeState.NEUTRAL
        self._consecutive_bars = 0
        self._candidate_state = RegimeState.NEUTRAL

    def evaluate(
        self, candles: List[Candle], atr_bps: float, spread_bps: float = 5.0
    ) -> RegimeOutput:
        # Check hard stress and chop conditions first
        if atr_bps < 4.0:
            return RegimeOutput(
                state=RegimeState.NOISE_CHOP,
                variance_ratio=1.0,
                atr_bps=atr_bps,
                is_stress=False,
            )

        if atr_bps > 400.0 or spread_bps > 25.0:
            return RegimeOutput(
                state=RegimeState.LIQUIDITY_STRESS,
                variance_ratio=1.0,
                atr_bps=atr_bps,
                is_stress=True,
            )

        if len(candles) < 30:
            return RegimeOutput(
                state=self._current_state,
                variance_ratio=1.0,
                atr_bps=atr_bps,
                is_stress=False,
            )

        closes = np.array([c.close for c in candles], dtype=np.float64)
        vr = self._compute_variance_ratio(closes, q=4)

        # Raw state determination
        if vr < (0.96 - self.vr_deadband):
            raw_state = RegimeState.MEAN_REVERSION_ROTATIONAL
        elif vr > (1.05 + self.vr_deadband):
            raw_state = RegimeState.MOMENTUM_TREND
        else:
            raw_state = RegimeState.NEUTRAL

        # Apply hysteresis filter (must persist for hysteresis_bars)
        if raw_state == self._candidate_state:
            self._consecutive_bars += 1
            if self._consecutive_bars >= self.hysteresis_bars:
                self._current_state = raw_state
        else:
            self._candidate_state = raw_state
            self._consecutive_bars = 1

        return RegimeOutput(
            state=self._current_state,
            variance_ratio=vr,
            atr_bps=atr_bps,
            is_stress=False,
        )

    @staticmethod
    def _compute_variance_ratio(closes: np.ndarray, q: int = 4) -> float:
        """Compute Lo-MacKinlay multi-period variance ratio."""
        log_prices = np.log(closes)
        r1 = log_prices[1:] - log_prices[:-1]
        rq = log_prices[q:] - log_prices[:-q]

        var1 = np.var(r1, ddof=1)
        varq = np.var(rq, ddof=1)

        if var1 <= 1e-12:
            return 1.0

        vr = varq / (q * var1)
        return float(vr)
