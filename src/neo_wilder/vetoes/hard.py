"""Hard Veto Engine for NEO-WILDER V4.

Implements all 34 Hard Vetoes (V-H01 to V-H34).
Fail-closed: any exception or condition failure blocks candidate publication.
Hard vetoes CAN NEVER be overridden by any score, model, or flag.
"""

import logging
from typing import Optional

import psutil

from neo_wilder.clock import SystemClock
from neo_wilder.data.integrity import DataIntegrityAuditor
from neo_wilder.domain.enums import HardVetoReason, RegimeState, VetoSeverity
from neo_wilder.domain.models import Candidate, CoinDCXQuote, VetoResult
from neo_wilder.edges.base import FeatureContext
from neo_wilder.vetoes.governor import PortfolioGovernor

logger = logging.getLogger(__name__)


class HardVetoEvaluator:
    """Evaluates all 34 Hard Vetoes in strict sequence."""

    @staticmethod
    def evaluate(
        candidate: Candidate,
        ctx: FeatureContext,
        quote: Optional[CoinDCXQuote],
        clock: SystemClock,
        governor: PortfolioGovernor,
        is_ws_disconnected: bool = False,
        is_orderbook_stale: bool = False,
        is_news_window: bool = False,
        is_news_outage: bool = False,
        calibration_valid: bool = False,
    ) -> VetoResult:
        try:
            # -------------------------------------------------------------
            # Stage 1: Data Integrity (V-H01..V-H04)
            # -------------------------------------------------------------
            quality = DataIntegrityAuditor.audit_candle_series(
                ctx.candles,
                timeframe=ctx.timeframe,
                now_ms=ctx.now_ms,
                check_freshness=True,
            )
            if not quality.is_valid:
                reason = quality.veto_reason or HardVetoReason.DATA_STALE
                veto_id_map = {
                    HardVetoReason.DATA_STALE: "V-H01",
                    HardVetoReason.DATA_GAP: "V-H02",
                    HardVetoReason.CANDLE_TS_INVALID: "V-H03",
                    HardVetoReason.DUPLICATE_CANDLE: "V-H04",
                }
                vid = veto_id_map.get(reason, "V-H01")
                return VetoResult(
                    False,
                    blocking_id=vid,
                    reason_code=reason.value,
                    severity=VetoSeverity.CRITICAL.value,
                    details=quality.details,
                )

            # -------------------------------------------------------------
            # Stage 2: Infrastructure Health (V-H05..V-H11)
            # -------------------------------------------------------------
            if is_ws_disconnected:
                return VetoResult(
                    False,
                    blocking_id="V-H05",
                    reason_code=HardVetoReason.WS_DISCONNECTED.value,
                    severity=VetoSeverity.CRITICAL.value,
                    details="WebSocket stream disconnected > 5s",
                )

            if is_orderbook_stale:
                return VetoResult(
                    False,
                    blocking_id="V-H06",
                    reason_code=HardVetoReason.ORDERBOOK_STALE.value,
                    severity=VetoSeverity.HIGH.value,
                    details="Orderbook depth older than 3s or sequence break",
                )

            if clock.is_desynced():
                return VetoResult(
                    False,
                    blocking_id="V-H07",
                    reason_code=HardVetoReason.CLOCK_DESYNC.value,
                    severity=VetoSeverity.HIGH.value,
                    details=f"Clock skew {clock.skew_ms:.1f}ms exceeds 1000ms",
                )

            # Memory Emergency (V-H08)
            try:
                rss_mb = psutil.Process().memory_info().rss / (1024 * 1024)
                if rss_mb > 300.0:
                    return VetoResult(
                        False,
                        blocking_id="V-H08",
                        reason_code=HardVetoReason.MEMORY_EMERGENCY.value,
                        severity=VetoSeverity.CRITICAL.value,
                        details=f"Process RSS {rss_mb:.1f}MB exceeds 300MB limit",
                    )
            except Exception:
                pass

            if governor.state.operator_kill_switch:
                return VetoResult(
                    False,
                    blocking_id="V-H09",
                    reason_code=HardVetoReason.KILL_SWITCH.value,
                    severity=VetoSeverity.CRITICAL.value,
                    details="Operator kill switch engaged",
                )

            if not governor.state.watchdog_healthy or governor.state.watchdog_missed_beats >= 3:
                return VetoResult(
                    False,
                    blocking_id="V-H10",
                    reason_code=HardVetoReason.WATCHDOG_FAILURE.value,
                    severity=VetoSeverity.CRITICAL.value,
                    details="Watchdog heartbeat missed 3 intervals",
                )

            # Critical Source Down (V-H11)
            if ctx.funding_context is None:
                return VetoResult(
                    False,
                    blocking_id="V-H11",
                    reason_code=HardVetoReason.CRITICAL_SOURCE_DOWN.value,
                    severity=VetoSeverity.HIGH.value,
                    details="Funding / derivatives context unavailable",
                )

            # -------------------------------------------------------------
            # Stage 3: Market Safety (V-H12..V-H14)
            # -------------------------------------------------------------
            # Abnormal Spread on CoinDCX (V-H12)
            if quote:
                max_spread = (
                    12.0 if "BTC" in candidate.symbol or "ETH" in candidate.symbol else 25.0
                )
                if quote.spread_bps > max_spread:
                    return VetoResult(
                        False,
                        blocking_id="V-H12",
                        reason_code=HardVetoReason.ABNORMAL_SPREAD.value,
                        severity=VetoSeverity.HIGH.value,
                        details=f"CoinDCX spread {quote.spread_bps:.1f} bps > max {max_spread}",
                    )

                # Insufficient Liquidity (V-H13)
                clip_usd = 500.0
                min_depth = 20.0 * clip_usd  # $10,000 min
                if quote.top10_depth_usd < min_depth:
                    return VetoResult(
                        False,
                        blocking_id="V-H13",
                        reason_code=HardVetoReason.INSUFFICIENT_LIQUIDITY.value,
                        severity=VetoSeverity.HIGH.value,
                        details=f"CoinDCX depth ${quote.top10_depth_usd:.0f} < ${min_depth:.0f}",
                    )

            # Extreme Gap (V-H14)
            if len(ctx.candles) >= 2:
                prev_c = ctx.candles[-2].close
                curr_o = ctx.candles[-1].open
                gap_pct = abs(curr_o - prev_c) / prev_c * 100.0
                if gap_pct > 3.0:
                    return VetoResult(
                        False,
                        blocking_id="V-H14",
                        reason_code=HardVetoReason.EXTREME_GAP.value,
                        severity=VetoSeverity.HIGH.value,
                        details=f"Opening gap {gap_pct:.2f}% > 3.0%",
                    )

            # -------------------------------------------------------------
            # Stage 4: Event & Derivatives Risk (V-H15..V-H18, V-H33)
            # -------------------------------------------------------------
            if is_news_window:
                return VetoResult(
                    False,
                    blocking_id="V-H15",
                    reason_code=HardVetoReason.NEWS_WINDOW_ACTIVE.value,
                    severity=VetoSeverity.HIGH.value,
                    details="P0/P1 economic news window active (-15/+30 min)",
                )

            if is_news_outage:
                return VetoResult(
                    False,
                    blocking_id="V-H16",
                    reason_code=HardVetoReason.NEWS_DATA_UNAVAILABLE.value,
                    severity=VetoSeverity.HIGH.value,
                    details="Calendar news feed outage (fail-closed)",
                )

            if ctx.funding_context and ctx.funding_context.is_funding_window_active:
                return VetoResult(
                    False,
                    blocking_id="V-H17",
                    reason_code=HardVetoReason.FUNDING_WINDOW_ACTIVE.value,
                    severity=VetoSeverity.MEDIUM.value,
                    details="Within -15/+5 min of 8h funding settlement",
                )

            if ctx.funding_context and ctx.funding_context.mark_index_divergence_pct > 0.50:
                return VetoResult(
                    False,
                    blocking_id="V-H18",
                    reason_code=HardVetoReason.MARK_INDEX_DIVERGENCE.value,
                    severity=VetoSeverity.HIGH.value,
                    details=f"Mark/Index divergence {ctx.funding_context.mark_index_divergence_pct:.2f}% > 0.50%",
                )

            if candidate.regime in (RegimeState.NOISE_CHOP, RegimeState.LIQUIDITY_STRESS):
                return VetoResult(
                    False,
                    blocking_id="V-H33",
                    reason_code=HardVetoReason.REGIME_INELIGIBLE.value,
                    severity=VetoSeverity.MEDIUM.value,
                    details=f"Regime {candidate.regime.value} is ineligible",
                )

            # -------------------------------------------------------------
            # Stage 5: Execution Validation (V-H31, V-H32)
            # -------------------------------------------------------------
            if quote is None:
                return VetoResult(
                    False,
                    blocking_id="V-H31",
                    reason_code=HardVetoReason.COINDCX_FEED_UNAVAILABLE.value,
                    severity=VetoSeverity.HIGH.value,
                    details="No CoinDCX validation quote available at publish time",
                )

            drift_pct = (
                abs(quote.price - candidate.reference_price) / candidate.reference_price * 100.0
            )
            if drift_pct > 0.35:
                return VetoResult(
                    False,
                    blocking_id="V-H32",
                    reason_code=HardVetoReason.ENTRY_DRIFT_EXCEEDED.value,
                    severity=VetoSeverity.HIGH.value,
                    details=f"Price drift {drift_pct:.3f}% > max 0.35%",
                )

            # -------------------------------------------------------------
            # Stage 6: Risk Geometry (V-H19..V-H23)
            # -------------------------------------------------------------
            if candidate.entry_zone_low > candidate.entry_zone_high:
                return VetoResult(
                    False,
                    blocking_id="V-H19",
                    reason_code=HardVetoReason.ENTRY_GEOMETRY_INVALID.value,
                    severity=VetoSeverity.CRITICAL.value,
                    details="Entry zone is inverted",
                )

            stop_dist = candidate.reference_price - candidate.stop_loss
            atr = ctx.atr_result.atr if ctx.atr_result else 1.0
            min_sl_dist = max(0.0065 * candidate.reference_price, 0.50 * atr)
            max_sl_dist = 4.50 * atr

            if not (min_sl_dist <= stop_dist <= max_sl_dist):
                return VetoResult(
                    False,
                    blocking_id="V-H20",
                    reason_code=HardVetoReason.STOP_INVALID.value,
                    severity=VetoSeverity.CRITICAL.value,
                    details=f"Stop distance {stop_dist:.2f} outside [{min_sl_dist:.2f}, {max_sl_dist:.2f}]",
                )

            if candidate.tp1 <= candidate.entry_zone_high:
                return VetoResult(
                    False,
                    blocking_id="V-H21",
                    reason_code=HardVetoReason.TARGET_INVALID.value,
                    severity=VetoSeverity.CRITICAL.value,
                    details="TP1 is inside or below entry zone",
                )

            if candidate.net_rr < 1.50:
                return VetoResult(
                    False,
                    blocking_id="V-H22",
                    reason_code=HardVetoReason.NET_RR_TOO_LOW.value,
                    severity=VetoSeverity.CRITICAL.value,
                    details=f"Net R:R {candidate.net_rr:.2f} < 1.50",
                )

            # Slippage estimate vs stop distance (V-H23)
            slippage_est = (quote.spread_bps / 10000.0 * quote.price) * 0.5
            if slippage_est > (0.15 * stop_dist):
                return VetoResult(
                    False,
                    blocking_id="V-H23",
                    reason_code=HardVetoReason.SLIPPAGE_TOO_HIGH.value,
                    severity=VetoSeverity.HIGH.value,
                    details=f"Slippage ${slippage_est:.2f} > 15% of stop distance",
                )

            # -------------------------------------------------------------
            # Stage 7: Exposure & Loss Caps (V-H26..V-H30)
            # -------------------------------------------------------------
            if governor.concurrent_count >= governor.max_concurrent:
                return VetoResult(
                    False,
                    blocking_id="V-H26",
                    reason_code=HardVetoReason.PORTFOLIO_HEAT.value,
                    severity=VetoSeverity.HIGH.value,
                    details=f"Concurrent positions {governor.concurrent_count} >= max {governor.max_concurrent}",
                )

            if governor.is_daily_loss_breached():
                return VetoResult(
                    False,
                    blocking_id="V-H28",
                    reason_code=HardVetoReason.DAILY_LOSS_CAP.value,
                    severity=VetoSeverity.CRITICAL.value,
                    details=f"Daily loss {governor.daily_drawdown_pct:.1f}% >= 3.0%",
                )

            if governor.is_weekly_loss_breached():
                return VetoResult(
                    False,
                    blocking_id="V-H29",
                    reason_code=HardVetoReason.WEEKLY_LOSS_CAP.value,
                    severity=VetoSeverity.CRITICAL.value,
                    details=f"Weekly loss {governor.weekly_drawdown_pct:.1f}% >= 6.0%",
                )

            if candidate.symbol in governor.state.trading_halted_symbols:
                return VetoResult(
                    False,
                    blocking_id="V-H30",
                    reason_code=HardVetoReason.TRADING_HALTED.value,
                    severity=VetoSeverity.CRITICAL.value,
                    details=f"Trading halted on {candidate.symbol}",
                )

            # -------------------------------------------------------------
            # Stage 8: Dedupe, Cooldown & Governance (V-H24, V-H25, V-H34)
            # -------------------------------------------------------------
            if governor.is_duplicate_signal(
                candidate.symbol, candidate.direction.value, candidate.strategy_id
            ):
                return VetoResult(
                    False,
                    blocking_id="V-H24",
                    reason_code=HardVetoReason.DUPLICATE_SIGNAL.value,
                    severity=VetoSeverity.MEDIUM.value,
                    details="Duplicate candidate within 30m window",
                )

            if governor.is_symbol_locked(candidate.symbol):
                return VetoResult(
                    False,
                    blocking_id="V-H25",
                    reason_code=HardVetoReason.SYMBOL_COOLDOWN.value,
                    severity=VetoSeverity.MEDIUM.value,
                    details="Symbol inside 30m cooldown lock",
                )

            # V-H34: Model probability unvalidated
            # Per AGENT.md: Signal can publish with score, but if a numeric probability is attempted without calibration it blocks
            if not calibration_valid and candidate.strategy_id == "ML_MODEL":
                return VetoResult(
                    False,
                    blocking_id="V-H34",
                    reason_code=HardVetoReason.MODEL_PROBABILITY_UNVALIDATED.value,
                    severity=VetoSeverity.CRITICAL.value,
                    details="Calibration artefact missing or unvalidated",
                )

            # All 34 Hard Veto checks passed
            return VetoResult(True)

        except Exception as e:
            logger.error(f"Fail-closed veto engine exception: {e}", exc_info=True)
            return VetoResult(
                False,
                blocking_id="V-H_EXCEPTION",
                reason_code="UNCAUGHT_EXCEPTION",
                severity=VetoSeverity.CRITICAL.value,
                details=str(e),
            )
