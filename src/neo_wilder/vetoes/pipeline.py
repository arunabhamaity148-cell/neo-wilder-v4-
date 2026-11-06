"""Master Veto Pipeline runner for NEO-WILDER V4.

Coordinates Hard Vetoes, Soft Vetoes, and Portfolio Governors.
Guarantees fail-closed execution.
"""

import logging
from typing import Optional, Tuple

from neo_wilder.clock import SystemClock
from neo_wilder.domain.enums import VetoSeverity
from neo_wilder.domain.models import Candidate, CoinDCXQuote, VetoResult
from neo_wilder.edges.base import FeatureContext
from neo_wilder.vetoes.governor import PortfolioGovernor
from neo_wilder.vetoes.hard import HardVetoEvaluator
from neo_wilder.vetoes.risk_guard import ExtremeMarketRiskGuard
from neo_wilder.vetoes.soft import SoftVetoEvaluator, SoftVetoResult

logger = logging.getLogger(__name__)


class VetoPipeline:
    """Master pipeline executing hard and soft vetoes in strict sequence."""

    def __init__(
        self,
        governor: Optional[PortfolioGovernor] = None,
        risk_guard: Optional[ExtremeMarketRiskGuard] = None,
    ):
        self.governor = governor or PortfolioGovernor()
        self.risk_guard = risk_guard or ExtremeMarketRiskGuard()

    def evaluate_candidate(
        self,
        candidate: Candidate,
        ctx: FeatureContext,
        quote: Optional[CoinDCXQuote],
        clock: SystemClock,
        is_ws_disconnected: bool = False,
        is_orderbook_stale: bool = False,
        is_news_window: bool = False,
        is_news_outage: bool = False,
        calibration_valid: bool = False,
        cluster_risk_r: float = 0.0,
        publish_threshold: float = 85.0,
    ) -> Tuple[bool, VetoResult, SoftVetoResult]:
        """Execute full veto evaluation.

        Returns:
            (passed: bool, hard_result: VetoResult, soft_result: SoftVetoResult)
        """
        # 1. Evaluate Hard Vetoes
        hard_res = HardVetoEvaluator.evaluate(
            candidate=candidate,
            ctx=ctx,
            quote=quote,
            clock=clock,
            governor=self.governor,
            is_ws_disconnected=is_ws_disconnected,
            is_orderbook_stale=is_orderbook_stale,
            is_news_window=is_news_window,
            is_news_outage=is_news_outage,
            calibration_valid=calibration_valid,
        )

        if not hard_res.passed:
            return False, hard_res, SoftVetoResult()

        # 2. Evaluate Dedicated Extreme Market Risk Guard
        risk_eval = self.risk_guard.evaluate_candidate(
            candidate=candidate,
            ctx=ctx,
            quote=quote,
        )

        if not risk_eval.is_safe or risk_eval.hard_veto_triggered:
            risk_hard = VetoResult(
                passed=False,
                blocking_id=risk_eval.blocking_veto_id or "V-H33_RISK_GUARD",
                reason_code=risk_eval.blocking_reason or "EXTREME_MARKET_RISK_TRIGGERED",
                severity=VetoSeverity.HIGH.value,
                details="; ".join(risk_eval.details),
            )
            return False, risk_hard, SoftVetoResult()

        # 3. Evaluate Soft Vetoes
        soft_res = SoftVetoEvaluator.evaluate(
            candidate=candidate,
            ctx=ctx,
            quote=quote,
            cluster_risk_r=cluster_risk_r,
            publish_threshold=publish_threshold,
        )

        # 4. Check for Soft Veto escalation to Hard Veto
        if soft_res.escalated_to_hard:
            escalated_hard = VetoResult(
                passed=False,
                blocking_id=soft_res.escalation_blocking_id,
                reason_code=soft_res.escalation_reason,
                severity=VetoSeverity.HIGH.value,
                details=f"Soft veto {soft_res.escalation_blocking_id} escalated to Hard Veto",
            )
            return False, escalated_hard, soft_res

        return True, hard_res, soft_res
