"""Liquidity pool identification (EQH/EQL) for NEO-WILDER V4 (E04).

Clusters swing pivots within 0.15 * ATR.
"""

from typing import List

from neo_wilder.domain.models import LiquidityPool, SwingPivot


class LiquidityPoolDetector:
    """Detects Equal Highs and Equal Lows liquidity pools."""

    @staticmethod
    def detect_pools(
        swings: List[SwingPivot],
        atr: float,
        cluster_tolerance_atr: float = 0.15,
        min_touches: int = 2,
    ) -> List[LiquidityPool]:
        pools: List[LiquidityPool] = []
        if not swings or atr <= 0:
            return pools

        tolerance = cluster_tolerance_atr * atr

        high_swings = [s for s in swings if s.pivot_type == "HIGH"]
        low_swings = [s for s in swings if s.pivot_type == "LOW"]

        # Cluster Equal Highs (EQH)
        for pool in LiquidityPoolDetector._cluster_pivots(
            high_swings, tolerance, min_touches, "EQH", atr
        ):
            pools.append(pool)

        # Cluster Equal Lows (EQL)
        for pool in LiquidityPoolDetector._cluster_pivots(
            low_swings, tolerance, min_touches, "EQL", atr
        ):
            pools.append(pool)

        return pools

    @staticmethod
    def _cluster_pivots(
        pivots: List[SwingPivot],
        tolerance: float,
        min_touches: int,
        pool_type: str,
        atr: float,
    ) -> List[LiquidityPool]:
        clusters: List[LiquidityPool] = []
        if len(pivots) < min_touches:
            return clusters

        used_indices = set()
        # Iterate backwards from most recent pivots
        for i in range(len(pivots) - 1, -1, -1):
            if pivots[i].index in used_indices:
                continue

            anchor = pivots[i]
            matched = [anchor]

            for j in range(i - 1, -1, -1):
                if pivots[j].index in used_indices:
                    continue
                cand = pivots[j]
                if abs(cand.price - anchor.price) <= tolerance:
                    matched.append(cand)

            if len(matched) >= min_touches:
                prices = [p.price for p in matched]
                mean_level = sum(prices) / len(matched)
                width_atr = (max(prices) - min(prices)) / atr if atr > 0 else 0.0

                for m in matched:
                    used_indices.add(m.index)

                clusters.append(
                    LiquidityPool(
                        pool_type=pool_type,
                        level=mean_level,
                        swings=matched,
                        touch_count=len(matched),
                        width_atr=width_atr,
                    )
                )

        return clusters
