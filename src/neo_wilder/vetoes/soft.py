"""Soft Veto Engine for NEO-WILDER V4.

Implements all 15 Soft Vetoes (V-S01 to V-S15).
Applies confidence adjustments, score threshold increments, and risk multipliers.
Handles dynamic escalation to hard veto blocks.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from neo_wilder.domain.enums import Direction, SoftVetoReason
from neo_wilder.domain.models import Candidate, CoinDCXQuote
from neo_wilder.edges.base import FeatureContext


@dataclass
class SoftVetoResult:
    """Consolidated modifications produced by soft vetoes."""

    active_soft_vetoes: List[str] = field(default_factory=list)
    confidence_penalty: float = 0.0
    threshold_increment: float = 0.0
    risk_multiplier: float = 1.0
    escalated_to_hard: bool = False
    escalation_blocking_id: Optional[str] = None
    escalation_reason: Optional[str] = None


class SoftVetoEvaluator:
    """Evaluates all 15 Soft Vetoes."""

    @staticmethod
    def evaluate(
        candidate: Candidate,
        ctx: FeatureContext,
        quote: Optional[CoinDCXQuote],
        cluster_risk_r: float = 0.0,
        publish_threshold: float = 85.0,
    ) -> SoftVetoResult:
        res = SoftVetoResult()

        # V-S01: BTC Directional Conflict (conf -15, threshold +5, escalates if BTC 5m < -1.0%)
        if ctx.btc_5m_return < -0.0035:
            res.active_soft_vetoes.append("V-S01")
            res.confidence_penalty += 15.0
            res.threshold_increment += 5.0
            if ctx.btc_5m_return < -0.010:  # < -1.0%
                res.escalated_to_hard = True
                res.escalation_blocking_id = "V-S01"
                res.escalation_reason = SoftVetoReason.BTC_DIRECTIONAL_CONFLICT.value

        # V-S02: BTC Volatility Instability (conf -10)
        if abs(ctx.btc_5m_return) > 0.0080:  # > 0.80% 5m move on BTC
            res.active_soft_vetoes.append("V-S02")
            res.confidence_penalty += 10.0

        # V-S03: Weak Trend (conf -8)
        if ctx.atr_result and ctx.atr_result.vol_tier == 0:  # Compressed volatility tier
            res.active_soft_vetoes.append("V-S03")
            res.confidence_penalty += 8.0

        # V-S04: Funding Extreme (risk x0.5, escalates if abs(funding) > 0.05%)
        if ctx.funding_context and abs(ctx.funding_context.funding_rate_pct) >= 0.03:
            res.active_soft_vetoes.append("V-S04")
            res.risk_multiplier *= 0.5
            if abs(ctx.funding_context.funding_rate_pct) > 0.05:
                res.escalated_to_hard = True
                res.escalation_blocking_id = "V-S04"
                res.escalation_reason = SoftVetoReason.FUNDING_EXTREME.value

        # V-S05: OI Instability (conf -8)
        if ctx.oi_history and len(ctx.oi_history) >= 2:
            prev_oi = ctx.oi_history[-2].open_interest
            curr_oi = ctx.oi_history[-1].open_interest
            if prev_oi > 0:
                oi_delta_pct = abs(curr_oi - prev_oi) / prev_oi * 100.0
                if oi_delta_pct > 3.0:
                    res.active_soft_vetoes.append("V-S05")
                    res.confidence_penalty += 8.0

        # V-S06: Poor Liquidity (risk x0.6)
        if quote and quote.spread_bps > 8.0:
            res.active_soft_vetoes.append("V-S06")
            res.risk_multiplier *= 0.6

        # V-S07: Correlated Exposure (risk x0.5)
        if cluster_risk_r > 1.0:
            res.active_soft_vetoes.append("V-S07")
            res.risk_multiplier *= 0.5

        # V-S08: Cluster Heat High (threshold +3, escalates if cluster > 2.0R)
        if cluster_risk_r > 1.5:
            res.active_soft_vetoes.append("V-S08")
            res.threshold_increment += 3.0
            if cluster_risk_r > 2.0:
                res.escalated_to_hard = True
                res.escalation_blocking_id = "V-S08"
                res.escalation_reason = SoftVetoReason.CLUSTER_HEAT_HIGH.value

        # V-S09: Weak Session (conf -5)
        # Low volume weekend or illiquid interval modifier
        if hasattr(ctx, "session_tag") and ctx.session_tag == "OFF_HOURS":
            res.active_soft_vetoes.append("V-S09")
            res.confidence_penalty += 5.0

        # V-S10: Late Entry (threshold +5, escalates if progress > 0.35) - Bidirectional
        if quote and candidate.tp1:
            if candidate.direction == Direction.LONG:
                total_dist = candidate.tp1 - candidate.reference_price
                progress = (
                    (quote.price - candidate.reference_price) / total_dist
                    if total_dist > 0
                    else 0.0
                )
            else:
                total_dist = candidate.reference_price - candidate.tp1
                progress = (
                    (candidate.reference_price - quote.price) / total_dist
                    if total_dist > 0
                    else 0.0
                )

            if progress > 0.20:
                res.active_soft_vetoes.append("V-S10")
                res.threshold_increment += 5.0
                if progress > 0.35:
                    res.escalated_to_hard = True
                    res.escalation_blocking_id = "V-S10"
                    res.escalation_reason = SoftVetoReason.LATE_ENTRY.value

        # V-S11: Weak Orderflow (conf -10) - Bidirectional
        if ctx.cvd_result:
            if candidate.direction == Direction.LONG and ctx.cvd_result.slope < 0:
                res.active_soft_vetoes.append("V-S11")
                res.confidence_penalty += 10.0
            elif candidate.direction == Direction.SHORT and ctx.cvd_result.slope > 0:
                res.active_soft_vetoes.append("V-S11")
                res.confidence_penalty += 10.0

        # V-S12: Volatility Mismatch (risk x0.7)
        if ctx.atr_result and ctx.atr_result.vol_tier >= 2:
            res.active_soft_vetoes.append("V-S12")
            res.risk_multiplier *= 0.7

        # V-S13: Low Quality Regime (conf -12)
        if ctx.regime_output and ctx.regime_output.state.value == "MOMENTUM_TREND":
            res.active_soft_vetoes.append("V-S13")
            res.confidence_penalty += 12.0

        # V-S14: Poor Execution Quality (threshold +5)
        if quote and quote.spread_bps > 10.0:
            res.active_soft_vetoes.append("V-S14")
            res.threshold_increment += 5.0

        # V-S15: Score Below Publish Threshold (suppression marker)
        if hasattr(candidate, "quality_score") and candidate.quality_score is not None:
            effective_threshold = publish_threshold + res.threshold_increment
            if candidate.quality_score < effective_threshold:
                res.active_soft_vetoes.append("V-S15")

        return res
