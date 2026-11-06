"""Orthogonal correlation-aware scoring engine for NEO-WILDER V4.

Enforces cluster caps, C1+C2 <= 24 limit, and zero contribution from shadow edges.
Score is an integer in [0, 100].
"""

from typing import Dict

from neo_wilder.domain.enums import EdgeStatus, ScoringCluster
from neo_wilder.domain.models import Candidate, EdgeResult, ScoreBreakdown
from neo_wilder.edges.registry import EdgeRegistry


class CompositeScorer:
    """Computes correlation-aware composite quality score."""

    CLUSTER_CAPS = {
        ScoringCluster.C1.value: 12,
        ScoringCluster.C2.value: 12,
        ScoringCluster.C3.value: 20,
        ScoringCluster.C4.value: 12,
        ScoringCluster.C5.value: 10,
        ScoringCluster.C6.value: 0,
    }

    C1_C2_COMBINED_CAP = 24
    MAX_RR_BONUS = 4

    def __init__(self, registry: EdgeRegistry):
        self.registry = registry

    def score(
        self,
        candidate: Candidate,
        edge_results: Dict[str, EdgeResult],
        confidence_penalty: float = 0.0,
    ) -> ScoreBreakdown:
        cluster_accumulators: Dict[str, int] = {k: 0 for k in self.CLUSTER_CAPS}

        # 1. Accumulate active edge contributions strictly by cluster
        for edge_id, res in edge_results.items():
            if not res.passed or res.score_contribution <= 0:
                continue

            meta = self.registry.get(edge_id)

            # Invariant: Shadow and experimental edges NEVER contribute to score
            if meta.status != EdgeStatus.ACTIVE:
                continue

            cluster_key = meta.cluster.value
            if cluster_key in cluster_accumulators:
                cluster_accumulators[cluster_key] += res.score_contribution

        # 2. Enforce individual cluster caps
        capped_clusters: Dict[str, int] = {}
        for c_key, raw_pts in cluster_accumulators.items():
            cap = self.CLUSTER_CAPS.get(c_key, 0)
            capped_clusters[c_key] = min(cap, raw_pts)

        # 3. Enforce C1 + C2 combined cap (max 24)
        c1_pts = capped_clusters.get("C1", 0)
        c2_pts = capped_clusters.get("C2", 0)
        if (c1_pts + c2_pts) > self.C1_C2_COMBINED_CAP:
            excess = (c1_pts + c2_pts) - self.C1_C2_COMBINED_CAP
            # Scale down proportionally
            c2_pts = max(0, c2_pts - excess)
            capped_clusters["C2"] = c2_pts

        # 4. R:R bonus: +1 point per 0.25 R above 1.50, up to +4 pts
        rr_bonus = 0
        if candidate.net_rr > 1.50:
            rr_bonus = min(self.MAX_RR_BONUS, int((candidate.net_rr - 1.50) / 0.25))

        # Base active spine points (S1 active setup earns baseline 60 pts if all S1 criteria pass)
        base_setup_points = 60

        subtotal = base_setup_points + sum(capped_clusters.values()) + rr_bonus

        # Apply soft veto confidence penalties
        final_score = max(0, min(100, int(subtotal - confidence_penalty)))

        return ScoreBreakdown(
            total_score=final_score,
            cluster_scores=capped_clusters,
            rr_bonus=rr_bonus,
            calibrated_probability=None,
            is_calibrated=False,
        )
