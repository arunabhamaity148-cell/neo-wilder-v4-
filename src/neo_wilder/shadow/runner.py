"""Shadow Mode Runner and Readiness Auditor for NEO-WILDER V4.

Operates under ExecutionMode.SHADOW:
- Collects candidate signals from active (S1) and shadow (S2) strategies and shadow edges (E02, E06, E10, E14, E17, E18, E20, E21, E22, E26, E27).
- STRICT INVARIANT: ZERO alerts transmitted to Telegram (silent execution).
- Records all shadow signals to SQLite WAL shadow_signals table.
- Emits explicit 'RUNTIME VALIDATION PENDING' status until 8-week soak requirement is met.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional

from neo_wilder.data.store import DatabaseStore
from neo_wilder.domain.enums import EdgeStatus, ExecutionMode
from neo_wilder.domain.models import Candidate, EdgeResult
from neo_wilder.edges.registry import EdgeRegistry
from neo_wilder.scoring.groups import CompositeScorer

logger = logging.getLogger(__name__)

# Mandatory soak requirements per ROADMAP
MIN_SHADOW_SOAK_DAYS = 56  # 8 weeks
MIN_SHADOW_SETUPS = 50


@dataclass
class ShadowTelemetry:
    total_evaluations: int = 0
    total_shadow_candidates: int = 0
    s1_candidates_count: int = 0
    s2_shadow_candidates_count: int = 0
    edge_hit_counts: Dict[str, int] = field(default_factory=dict)
    veto_block_counts: Dict[str, int] = field(default_factory=dict)


class ShadowRunner:
    """Executes signal pipeline in isolated SHADOW mode with zero Telegram egress."""

    def __init__(
        self,
        store: DatabaseStore,
        registry: EdgeRegistry,
        scorer: CompositeScorer,
        mode: ExecutionMode = ExecutionMode.SHADOW,
    ):
        if mode != ExecutionMode.SHADOW:
            raise ValueError(f"ShadowRunner must operate in ExecutionMode.SHADOW, got {mode}")
        self.store = store
        self.registry = registry
        self.scorer = scorer
        self.mode = mode
        self.telemetry = ShadowTelemetry()

    async def handle_shadow_candidate(
        self,
        candidate: Candidate,
        edge_results: Dict[str, EdgeResult],
        veto_passed: bool,
        veto_blocking_id: Optional[str] = None,
    ) -> Dict:
        """Process candidate in shadow mode, guaranteeing ZERO Telegram transmission."""
        self.telemetry.total_evaluations += 1
        self.telemetry.total_shadow_candidates += 1

        if candidate.strategy_id == "S1_SWEEP_RECLAIM":
            self.telemetry.s1_candidates_count += 1
        elif candidate.strategy_id == "S2_OI_EXHAUSTION":
            self.telemetry.s2_shadow_candidates_count += 1

        # Track edge hits
        shadow_edges_hit = []
        active_edges_hit = []
        for eid, res in edge_results.items():
            if res.passed:
                self.telemetry.edge_hit_counts[eid] = self.telemetry.edge_hit_counts.get(eid, 0) + 1
                meta = self.registry.get(eid)
                if meta.status == EdgeStatus.SHADOW:
                    shadow_edges_hit.append(eid)
                elif meta.status == EdgeStatus.ACTIVE:
                    active_edges_hit.append(eid)

        # Track vetoes
        veto_status = "CLEARED" if veto_passed else f"BLOCKED_{veto_blocking_id}"
        if not veto_passed and veto_blocking_id:
            self.telemetry.veto_block_counts[veto_blocking_id] = (
                self.telemetry.veto_block_counts.get(veto_blocking_id, 0) + 1
            )

        # Score computation (invariant: shadow edges contribute 0)
        score_breakdown = self.scorer.score(candidate, edge_results)

        shadow_id = (
            f"SHADOW-{candidate.symbol}-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        )
        now_str = datetime.now(timezone.utc).isoformat()

        payload = {
            "shadow_id": shadow_id,
            "created_at_utc": now_str,
            "symbol": candidate.symbol,
            "direction": candidate.direction.value,
            "strategy_id": candidate.strategy_id,
            "score_0_100": score_breakdown.total_score,
            "veto_status": veto_status,
            "active_edges": active_edges_hit,
            "shadow_edges": shadow_edges_hit,
            "entry_zone": [candidate.entry_zone_low, candidate.entry_zone_high],
            "stop_loss": candidate.stop_loss,
            "tp1": candidate.tp1,
        }

        # Persist to SQLite WAL shadow table
        await self.store.record_shadow_signal(
            shadow_id=shadow_id,
            created_at_utc=now_str,
            symbol=candidate.symbol,
            direction=candidate.direction.value,
            strategy_id=candidate.strategy_id,
            score_0_100=score_breakdown.total_score,
            veto_status=veto_status,
            active_edge_ids=",".join(active_edges_hit),
            shadow_edge_ids=",".join(shadow_edges_hit),
            payload_json=json.dumps(payload),
        )

        logger.info(
            f"[SHADOW MODE] Recorded shadow signal {shadow_id} for {candidate.symbol} (Score: {score_breakdown.total_score}, Veto: {veto_status}). Zero alert egress."
        )
        return payload


class ShadowReadinessAuditor:
    """Evaluates empirical criteria for shadow-mode progression."""

    @staticmethod
    def audit_readiness(
        elapsed_days: float,
        resolved_shadow_setups: int,
        unhandled_crashes: int,
    ) -> Dict:
        """Evaluate readiness status conforming strictly to evidence requirements."""
        is_soak_complete = elapsed_days >= MIN_SHADOW_SOAK_DAYS
        is_setup_count_met = resolved_shadow_setups >= MIN_SHADOW_SETUPS
        is_crash_free = unhandled_crashes == 0

        is_ready = is_soak_complete and is_setup_count_met and is_crash_free
        status_str = "PROMOTION_READY" if is_ready else "RUNTIME VALIDATION PENDING / NOT PROVEN"

        return {
            "status": status_str,
            "is_ready_for_promotion": is_ready,
            "soak_days_elapsed": elapsed_days,
            "soak_days_required": MIN_SHADOW_SOAK_DAYS,
            "resolved_setups": resolved_shadow_setups,
            "required_setups": MIN_SHADOW_SETUPS,
            "unhandled_crashes": unhandled_crashes,
        }
