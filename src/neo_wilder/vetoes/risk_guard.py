"""Extreme Market Risk Guard (Bidirectional) for NEO-WILDER V4.

A dedicated multi-condition safety layer protecting both LONG and SHORT candidates.
Strictly a protective filter, NOT a trading strategy.

Audits and evaluates 6 structural market risk conditions:
1. OI and price divergence (E21 SHADOW)
2. Funding overheating (E23 ACTIVE, V-H17, V-S04 escalation)
3. Spot/Futures CVD divergence (E15 SHADOW, E22 EXPERIMENTAL)
4. Liquidation cascade (E13 SHADOW, E14 EXPERIMENTAL)
5. Orderbook liquidity void (X03 ACTIVE, E16 SHADOW, E17 SHADOW, V-H06, V-H12, V-H13)
6. Structural exhaustion (E01 ACTIVE, E05 SHADOW, tested Wilder RSI divergence)

Symmetric bidirectional risk evaluation:
- Evaluates LONG-side danger (positive funding crowding, perp-led rally without spot, bid void, bearish exhaustion).
- Evaluates SHORT-side danger (negative funding crowding, perp-led dump without spot, ask void, bullish exhaustion).
- Fail-closed: missing critical data causes ABSTAIN / block. Hard vetoes cannot be overridden.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from neo_wilder.domain.enums import Direction, HardVetoReason, SymbolTier
from neo_wilder.domain.models import Candidate, CoinDCXQuote
from neo_wilder.edges.base import FeatureContext
from neo_wilder.features.rsi import RSIEngine, RSIResult

logger = logging.getLogger(__name__)

# Frozen thresholds per SPEC
FUNDING_EXTREME_THRESHOLD = 0.0005  # |funding| > 0.05%
FUNDING_SETTLEMENT_WINDOW_PRE_MIN = 15.0  # -15 min
FUNDING_SETTLEMENT_WINDOW_POST_MIN = 5.0  # +5 min
MAX_SPREAD_BPS_MAJOR = 12.0
MAX_SPREAD_BPS_ALT = 25.0
MIN_DEPTH_CLIP_MULT = 20.0
MAX_ORDERBOOK_AGE_SEC = 3.0
MAX_OI_AGE_MS = 600_000  # 10 minutes


@dataclass
class RiskGuardEvaluation:
    """Full outcome of Extreme Market Risk Guard evaluation."""

    is_safe: bool
    direction: Direction
    hard_veto_triggered: bool = False
    blocking_veto_id: Optional[str] = None
    blocking_reason: Optional[str] = None
    danger_flags: Dict[str, bool] = field(default_factory=dict)
    soft_penalties: int = 0
    abstained: bool = False
    details: List[str] = field(default_factory=list)


class ExtremeMarketRiskGuard:
    """Bidirectional extreme market risk guard."""

    def __init__(self, default_clip_usd: float = 1000.0):
        self.default_clip_usd = default_clip_usd

    def evaluate_candidate(
        self,
        candidate: Candidate,
        ctx: FeatureContext,
        quote: Optional[CoinDCXQuote] = None,
        symbol_tier: SymbolTier = SymbolTier.MAJOR,
        orderbook_age_sec: float = 0.0,
    ) -> RiskGuardEvaluation:
        """Run bidirectional risk audit across all 6 risk dimensions.

        Fail-closed: missing critical data causes ABSTAIN/block.
        """
        direction = candidate.direction
        details = []
        danger_flags: Dict[str, bool] = {
            "oi_price_divergence": False,
            "funding_overheating": False,
            "cvd_perp_spot_divergence": False,
            "liquidation_cascade": False,
            "orderbook_liquidity_void": False,
            "structural_exhaustion": False,
        }
        soft_penalties = 0

        # =====================================================================
        # 1. OI and Price Divergence (E21 SHADOW)
        # =====================================================================
        # Detect abnormal expansion relative to price, rapid contraction
        if ctx.oi_snapshot is None and not ctx.oi_history:
            # If OI feed is completely missing or down > 10m
            logger.warning(f"OI data unavailable for {candidate.symbol} (V-H11 fail-closed)")
            return RiskGuardEvaluation(
                is_safe=False,
                direction=direction,
                hard_veto_triggered=True,
                blocking_veto_id="V-H11",
                blocking_reason=HardVetoReason.CRITICAL_SOURCE_DOWN.value,
                abstained=True,
                details=["OI data completely missing or down > 10 min"],
            )

        if ctx.oi_history and len(ctx.oi_history) >= 2:
            oi_prev = ctx.oi_history[-2].open_interest
            oi_curr = ctx.oi_history[-1].open_interest
            if oi_prev > 0:
                delta_oi_pct = (oi_curr - oi_prev) / oi_prev * 100.0

                # Check price delta over same interval
                if len(ctx.candles) >= 2:
                    p_prev = ctx.candles[-2].close
                    p_curr = ctx.candles[-1].close
                    delta_p_pct = (p_curr - p_prev) / p_prev * 100.0
                else:
                    delta_p_pct = 0.0

                # Rapid OI contraction (> 5% drop) indicates violent unwinding
                if delta_oi_pct < -5.0:
                    danger_flags["oi_price_divergence"] = True
                    soft_penalties += 8  # V-S05 OI instability
                    details.append(f"Rapid OI contraction detected ({delta_oi_pct:.2f}%)")

                # Directional crowding:
                # LONG risk: OI expanding heavily into a price dump (short aggressive buildup or trapped longs)
                if direction == Direction.LONG and delta_oi_pct > 3.0 and delta_p_pct < -1.0:
                    danger_flags["oi_price_divergence"] = True
                    soft_penalties += 8
                    details.append(
                        f"Crowded short buildup / trapped longs (OI +{delta_oi_pct:.1f}%, Price {delta_p_pct:.1f}%)"
                    )

                # SHORT risk: OI expanding heavily into a price pump (aggressive long buildup / short squeeze trap)
                elif direction == Direction.SHORT and delta_oi_pct > 3.0 and delta_p_pct > 1.0:
                    danger_flags["oi_price_divergence"] = True
                    soft_penalties += 8
                    details.append(
                        f"Crowded long buildup / short squeeze trap (OI +{delta_oi_pct:.1f}%, Price +{delta_p_pct:.1f}%)"
                    )

        # =====================================================================
        # 2. Funding Overheating (E23 ACTIVE)
        # =====================================================================
        if ctx.funding_context is None:
            logger.warning(f"Funding context missing for {candidate.symbol} (V-H11 fail-closed)")
            return RiskGuardEvaluation(
                is_safe=False,
                direction=direction,
                hard_veto_triggered=True,
                blocking_veto_id="V-H11",
                blocking_reason=HardVetoReason.CRITICAL_SOURCE_DOWN.value,
                abstained=True,
                details=["Funding context data missing"],
            )

        funding_res = ctx.funding_context

        # Gate 2A: Settlement window check (-15 min to +5 min of 8h settlement -> V-H17)
        if funding_res.is_funding_window_active:
            return RiskGuardEvaluation(
                is_safe=False,
                direction=direction,
                hard_veto_triggered=True,
                blocking_veto_id="V-H17",
                blocking_reason=HardVetoReason.FUNDING_WINDOW_ACTIVE.value,
                details=[
                    f"Within 8h funding settlement window ({funding_res.minutes_to_settlement:.1f} min to settlement)"
                ],
            )

        # Gate 2B: Directional funding crowding (V-S04 escalation to hard veto)
        raw_funding_rate = funding_res.funding_rate_pct / 100.0  # decimal fraction

        # Positive funding crowding (> +0.05%): longs pay heavy fee -> LONG danger!
        if direction == Direction.LONG and raw_funding_rate > FUNDING_EXTREME_THRESHOLD:
            danger_flags["funding_overheating"] = True
            details.append(
                f"Extreme positive funding crowding ({raw_funding_rate * 100:.3f}% > +0.05%): LONG blocked"
            )
            return RiskGuardEvaluation(
                is_safe=False,
                direction=direction,
                hard_veto_triggered=True,
                blocking_veto_id="V-S04_ESCALATED",
                blocking_reason="FUNDING_CROWDED_LONG",
                danger_flags=danger_flags,
                details=details,
            )

        # Negative funding crowding (< -0.05%): shorts pay heavy fee -> SHORT danger!
        elif direction == Direction.SHORT and raw_funding_rate < -FUNDING_EXTREME_THRESHOLD:
            danger_flags["funding_overheating"] = True
            details.append(
                f"Extreme negative funding crowding ({raw_funding_rate * 100:.3f}% < -0.05%): SHORT blocked"
            )
            return RiskGuardEvaluation(
                is_safe=False,
                direction=direction,
                hard_veto_triggered=True,
                blocking_veto_id="V-S04_ESCALATED",
                blocking_reason="FUNDING_CROWDED_SHORT",
                danger_flags=danger_flags,
                details=details,
            )

        # Mark-Index divergence check (> 0.5% -> V-H18)
        if funding_res.mark_index_divergence_pct > 0.5:
            return RiskGuardEvaluation(
                is_safe=False,
                direction=direction,
                hard_veto_triggered=True,
                blocking_veto_id="V-H18",
                blocking_reason=HardVetoReason.MARK_INDEX_DIVERGENCE.value,
                details=[
                    f"Mark-index divergence ({funding_res.mark_index_divergence_pct:.2f}%) exceeds 0.5%"
                ],
            )

        # =====================================================================
        # 3. Spot/Futures CVD Divergence (E15 SHADOW, E22 EXPERIMENTAL)
        # =====================================================================
        perp_cvd = ctx.cvd_result
        spot_cvd = ctx.spot_cvd_result

        if perp_cvd is not None and spot_cvd is not None:
            # Perp-led rally without spot confirmation (LONG danger)
            # Perp buying aggressively (slope > 0) while spot selling/flat (slope <= 0)
            if direction == Direction.LONG and perp_cvd.slope > 0 and spot_cvd.slope <= 0:
                danger_flags["cvd_perp_spot_divergence"] = True
                soft_penalties += 10  # V-S11 Weak orderflow
                details.append("Perp-led rally lacking spot confirmation (Spot CVD non-bullish)")

            # Perp-led dump without spot selling (SHORT danger / squeeze risk)
            # Perp dumping aggressively (slope < 0) while spot accumulating/flat (slope >= 0)
            elif direction == Direction.SHORT and perp_cvd.slope < 0 and spot_cvd.slope >= 0:
                danger_flags["cvd_perp_spot_divergence"] = True
                soft_penalties += 10
                details.append(
                    "Perp-led dump lacking spot selling (Spot CVD absorbing / non-bearish)"
                )

        # =====================================================================
        # 4. Liquidation Cascade (E13 SHADOW, E14 EXPERIMENTAL)
        # =====================================================================
        # Treat forceOrder sampling as incomplete; never assume missing events = 0
        if ctx.liquidation_events:
            total_long_liq = sum(
                float(e.get("qty", 0.0)) * float(e.get("price", 0.0))
                for e in ctx.liquidation_events
                if e.get("side") == "SELL" or e.get("S") == "SELL"
            )
            total_short_liq = sum(
                float(e.get("qty", 0.0)) * float(e.get("price", 0.0))
                for e in ctx.liquidation_events
                if e.get("side") == "BUY" or e.get("S") == "BUY"
            )

            # Cascade thresholds (e.g. > $500,000 recent burst in 15m)
            if direction == Direction.LONG and total_long_liq > 500_000.0:
                danger_flags["liquidation_cascade"] = True
                soft_penalties += 8
                details.append(f"Active long liquidation cascade (${total_long_liq:,.0f} burst)")

            elif direction == Direction.SHORT and total_short_liq > 500_000.0:
                danger_flags["liquidation_cascade"] = True
                soft_penalties += 8
                details.append(f"Active short liquidation cascade (${total_short_liq:,.0f} burst)")

        # =====================================================================
        # 5. Orderbook Liquidity Void (X03 ACTIVE, E16/E17 SHADOW)
        # =====================================================================
        # Book staleness check (V-H06)
        if orderbook_age_sec > MAX_ORDERBOOK_AGE_SEC:
            return RiskGuardEvaluation(
                is_safe=False,
                direction=direction,
                hard_veto_triggered=True,
                blocking_veto_id="V-H06",
                blocking_reason=HardVetoReason.ORDERBOOK_STALE.value,
                details=[
                    f"Orderbook depth is stale ({orderbook_age_sec:.1f}s > {MAX_ORDERBOOK_AGE_SEC}s)"
                ],
            )

        # Spread & Depth checks via CoinDCX quote
        if quote is not None:
            max_spread = (
                MAX_SPREAD_BPS_MAJOR if symbol_tier == SymbolTier.MAJOR else MAX_SPREAD_BPS_ALT
            )
            if quote.spread_bps > max_spread:
                return RiskGuardEvaluation(
                    is_safe=False,
                    direction=direction,
                    hard_veto_triggered=True,
                    blocking_veto_id="V-H12",
                    blocking_reason=HardVetoReason.ABNORMAL_SPREAD.value,
                    details=[f"Spread ({quote.spread_bps:.1f} bps) exceeds {max_spread:.1f} bps"],
                )

            req_depth = self.default_clip_usd * MIN_DEPTH_CLIP_MULT
            if quote.top10_depth_usd < req_depth:
                return RiskGuardEvaluation(
                    is_safe=False,
                    direction=direction,
                    hard_veto_triggered=True,
                    blocking_veto_id="V-H13",
                    blocking_reason=HardVetoReason.INSUFFICIENT_LIQUIDITY.value,
                    details=[
                        f"Top-10 depth (${quote.top10_depth_usd:,.0f}) < required ${req_depth:,.0f}"
                    ],
                )

        # Orderbook Imbalance (E16) liquidity void detection
        if ctx.obi_result is not None:
            obi = ctx.obi_result.obi
            # For LONG: severe bid void (OBI < -0.60)
            if direction == Direction.LONG and obi < -0.60:
                danger_flags["orderbook_liquidity_void"] = True
                soft_penalties += 6
                details.append(f"Bid-side liquidity void detected (OBI: {obi:.2f})")

            # For SHORT: severe ask void (OBI > +0.60)
            elif direction == Direction.SHORT and obi > 0.60:
                danger_flags["orderbook_liquidity_void"] = True
                soft_penalties += 6
                details.append(f"Ask-side liquidity void detected (OBI: {obi:.2f})")

        # =====================================================================
        # 6. Structural Exhaustion (E01 ACTIVE, E05 SHADOW, Tested Wilder RSI)
        # =====================================================================
        # Compute Wilder RSI divergence if not already present in ctx
        rsi_res: Optional[RSIResult] = None
        if hasattr(ctx, "rsi_result") and isinstance(ctx.rsi_result, RSIResult):
            rsi_res = ctx.rsi_result
        else:
            rsi_res = RSIEngine.evaluate(ctx.candles, ctx.swings)

        if rsi_res is not None:
            # Bearish Divergence (Price HH, RSI LH at overbought) -> LONG danger!
            if direction == Direction.LONG and (
                rsi_res.has_bearish_divergence or rsi_res.is_overbought
            ):
                danger_flags["structural_exhaustion"] = True
                soft_penalties += 10
                details.append(
                    f"Bearish structural exhaustion (RSI: {rsi_res.rsi:.1f}, BearishDiv: {rsi_res.has_bearish_divergence})"
                )

            # Bullish Divergence (Price LL, RSI HL at oversold) -> SHORT danger!
            elif direction == Direction.SHORT and (
                rsi_res.has_bullish_divergence or rsi_res.is_oversold
            ):
                danger_flags["structural_exhaustion"] = True
                soft_penalties += 10
                details.append(
                    f"Bullish structural exhaustion (RSI: {rsi_res.rsi:.1f}, BullishDiv: {rsi_res.has_bullish_divergence})"
                )

        # =====================================================================
        # Composite Decision
        # =====================================================================
        # If multiple danger flags are active simultaneously (e.g. >= 2 severe dangers),
        # escalate to a hard block to prevent walking into a structural trap
        active_danger_count = sum(1 for v in danger_flags.values() if v)
        if active_danger_count >= 2:
            return RiskGuardEvaluation(
                is_safe=False,
                direction=direction,
                hard_veto_triggered=True,
                blocking_veto_id="V-H33_RISK_GUARD",
                blocking_reason="COMPOSITE_EXTREME_MARKET_RISK",
                danger_flags=danger_flags,
                soft_penalties=soft_penalties,
                details=details
                + [f"Blocked: {active_danger_count} concurrent extreme risk conditions detected"],
            )

        return RiskGuardEvaluation(
            is_safe=True,
            direction=direction,
            hard_veto_triggered=False,
            danger_flags=danger_flags,
            soft_penalties=soft_penalties,
            details=details,
        )
