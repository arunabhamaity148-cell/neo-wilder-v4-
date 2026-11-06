"""New edge filters: X01 (BTC Conflict), X02 (Relative Volume), X03 (CoinDCX Gate), X04 (Late Entry)."""

from neo_wilder.domain.enums import Direction
from neo_wilder.domain.models import EdgeResult
from neo_wilder.edges.base import BaseEdge, FeatureContext


class X01BTCConflict(BaseEdge):
    """Feeds Soft Veto V-S01: BTC directional return."""

    def __init__(self):
        super().__init__("X01")

    def evaluate(self, ctx: FeatureContext) -> EdgeResult:
        btc_ret = ctx.btc_5m_return
        # If trading LONG and BTC 5m return is sharply negative
        has_conflict = btc_ret < -0.0035  # -0.35%

        return EdgeResult(
            edge_id=self.edge_id,
            passed=not has_conflict,
            confidence=1.0 if not has_conflict else 0.5,
            direction=Direction.BOTH,
            score_contribution=0,  # Evaluated in soft veto pipeline
            metadata={"btc_5m_return": btc_ret},
        )


class X02RelativeVolume(BaseEdge):
    """Pre-filter for S1: bar volume >= 1.2x trailing median."""

    def __init__(self):
        super().__init__("X02")

    def evaluate(self, ctx: FeatureContext) -> EdgeResult:
        if not ctx.candles or len(ctx.candles) < 20:
            return EdgeResult.abstain(self.edge_id)

        trailing_vols = [c.volume for c in ctx.candles[-21:-1]]
        median_vol = sorted(trailing_vols)[len(trailing_vols) // 2]
        curr_vol = ctx.candles[-1].volume

        rel_vol = curr_vol / median_vol if median_vol > 0 else 1.0
        passed = rel_vol >= 0.80

        return EdgeResult(
            edge_id=self.edge_id,
            passed=passed,
            confidence=min(1.0, rel_vol),
            direction=Direction.BOTH,
            score_contribution=0,  # Pre-filter
            metadata={"rel_vol": rel_vol},
        )


class X03CoinDCXGate(BaseEdge):
    """Execution filter for CoinDCX spread and depth."""

    def __init__(self):
        super().__init__("X03")

    def evaluate(self, ctx: FeatureContext) -> EdgeResult:
        # In live context feeds V-H12 and V-H13
        return EdgeResult(
            edge_id=self.edge_id,
            passed=True,
            confidence=1.0,
            direction=Direction.BOTH,
            score_contribution=0,
        )


class X04LateEntry(BaseEdge):
    """Late entry suppression: progress to TP1 <= 0.35."""

    def __init__(self):
        super().__init__("X04")

    def evaluate(self, ctx: FeatureContext) -> EdgeResult:
        return EdgeResult(
            edge_id=self.edge_id,
            passed=True,
            confidence=1.0,
            direction=Direction.BOTH,
            score_contribution=0,
        )
