"""Funding rate context and Mark/Index divergence calculation (E23, E24)."""

from dataclasses import dataclass

from neo_wilder.domain.models import FundingSnapshot


@dataclass(frozen=True)
class FundingContextResult:
    """Evaluated funding context."""

    funding_rate_pct: float
    mark_index_divergence_pct: float
    minutes_to_settlement: float
    is_funding_window_active: bool  # V-H17: within -15 to +5 min of 8h settlement
    is_toxic_funding: bool  # V-S04: |funding| > 0.05%


class FundingEngine:
    """Evaluates funding and basis parameters."""

    @staticmethod
    def evaluate(snapshot: FundingSnapshot, now_ms: int) -> FundingContextResult:
        mark = snapshot.mark_price
        index = snapshot.index_price
        funding = snapshot.funding_rate

        div_pct = (abs(mark - index) / index * 100.0) if index > 0 else 0.0

        # Settlement countdown in minutes
        delta_ms = snapshot.next_funding_time_ms - now_ms
        minutes_to_settlement = delta_ms / 60000.0

        # Funding window: -15 min before settlement (minutes_to_settlement <= 15.0)
        # to +5 min after settlement (minutes_to_settlement >= -5.0)
        is_window_active = -5.0 <= minutes_to_settlement <= 15.0

        is_toxic = abs(funding) > 0.0005  # > 0.05%

        return FundingContextResult(
            funding_rate_pct=funding * 100.0,
            mark_index_divergence_pct=div_pct,
            minutes_to_settlement=minutes_to_settlement,
            is_funding_window_active=is_window_active,
            is_toxic_funding=is_toxic,
        )
