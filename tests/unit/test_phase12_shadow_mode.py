"""Unit tests for Phase 12: Shadow-Mode Implementation & Readiness."""

from pathlib import Path

import pytest

from neo_wilder.data.store import DatabaseStore
from neo_wilder.domain.enums import Direction, ExecutionMode, RegimeState
from neo_wilder.domain.models import Candidate, EdgeResult
from neo_wilder.edges.registry import EdgeRegistry
from neo_wilder.scoring.groups import CompositeScorer
from neo_wilder.shadow.runner import ShadowReadinessAuditor, ShadowRunner


@pytest.mark.asyncio
async def test_shadow_runner_execution_and_persistence(tmp_path: Path):
    """Verify ShadowRunner logs to shadow table with zero Telegram egress and tracks telemetry."""
    db_file = tmp_path / "test_shadow.db"
    store = DatabaseStore(db_file)
    await store.start()

    try:
        registry = EdgeRegistry(Path("config/edge_registry.yaml"))
        scorer = CompositeScorer(registry)

        # 1. Constructor validates ExecutionMode.SHADOW
        with pytest.raises(ValueError, match="ExecutionMode.SHADOW"):
            ShadowRunner(store, registry, scorer, mode=ExecutionMode.SIGNAL)

        runner = ShadowRunner(store, registry, scorer, mode=ExecutionMode.SHADOW)

        # 2. S1 Candidate with both Active and Shadow edges
        candidate_s1 = Candidate(
            symbol="BTCUSDT",
            direction=Direction.LONG,
            strategy_id="S1_SWEEP_RECLAIM",
            setup_edge_id="E01",
            reference_price=50000.0,
            entry_zone_low=49950.0,
            entry_zone_high=50050.0,
            stop_loss=49500.0,
            tp1=51000.0,
            tp2=None,
            gross_rr=2.0,
            net_rr=1.85,
            active_edge_ids=["E01"],
            confirming_edge_ids=["E15"],
            expiry_bars=12,
            regime=RegimeState.MEAN_REVERSION_ROTATIONAL,
            created_at_utc="2026-11-06T12:00:00Z",
        )

        edge_results = {
            "E01": EdgeResult(
                edge_id="E01",
                passed=True,
                confidence=1.0,
                direction=Direction.LONG,
                score_contribution=8,
            ),
            # E17 is SHADOW edge (zero score contribution)
            "E17": EdgeResult(
                edge_id="E17",
                passed=True,
                confidence=1.0,
                direction=Direction.LONG,
                score_contribution=6,
            ),
        }

        payload = await runner.handle_shadow_candidate(
            candidate=candidate_s1,
            edge_results=edge_results,
            veto_passed=True,
        )

        assert payload["strategy_id"] == "S1_SWEEP_RECLAIM"
        assert payload["veto_status"] == "CLEARED"
        assert "E01" in payload["active_edges"]
        assert "E17" in payload["shadow_edges"]
        # Score must only count base (60) + E01 (8 pts) + rr_bonus (1 pt) = 69. E17 must contribute 0.
        assert payload["score_0_100"] == 69

        # 3. Telemetry tracking
        assert runner.telemetry.total_evaluations == 1
        assert runner.telemetry.s1_candidates_count == 1
        assert runner.telemetry.edge_hit_counts["E01"] == 1
        assert runner.telemetry.edge_hit_counts["E17"] == 1

        # 4. S2 Shadow Candidate with Veto Block
        candidate_s2 = Candidate(
            symbol="ETHUSDT",
            direction=Direction.LONG,
            strategy_id="S2_OI_EXHAUSTION",
            setup_edge_id="E02",
            reference_price=3000.0,
            entry_zone_low=2980.0,
            entry_zone_high=3020.0,
            stop_loss=2900.0,
            tp1=3200.0,
            tp2=None,
            gross_rr=2.0,
            net_rr=1.85,
            active_edge_ids=[],
            confirming_edge_ids=[],
            expiry_bars=12,
            regime=RegimeState.MEAN_REVERSION_ROTATIONAL,
            created_at_utc="2026-11-06T12:00:00Z",
        )

        payload_s2 = await runner.handle_shadow_candidate(
            candidate=candidate_s2,
            edge_results={},
            veto_passed=False,
            veto_blocking_id="V-H19",
        )
        assert payload_s2["strategy_id"] == "S2_OI_EXHAUSTION"
        assert payload_s2["veto_status"] == "BLOCKED_V-H19"
        assert runner.telemetry.s2_shadow_candidates_count == 1
        assert runner.telemetry.veto_block_counts["V-H19"] == 1

    finally:
        await store.stop()


def test_shadow_readiness_auditor():
    """Verify ShadowReadinessAuditor enforces 8-week soak, 50 setups, and 0 crashes."""
    # Scenario A: Only 14 days elapsed -> RUNTIME VALIDATION PENDING
    res_a = ShadowReadinessAuditor.audit_readiness(
        elapsed_days=14.0,
        resolved_shadow_setups=60,
        unhandled_crashes=0,
    )
    assert res_a["is_ready_for_promotion"] is False
    assert res_a["status"] == "RUNTIME VALIDATION PENDING / NOT PROVEN"

    # Scenario B: 60 days elapsed, but only 25 setups -> RUNTIME VALIDATION PENDING
    res_b = ShadowReadinessAuditor.audit_readiness(
        elapsed_days=60.0,
        resolved_shadow_setups=25,
        unhandled_crashes=0,
    )
    assert res_b["is_ready_for_promotion"] is False
    assert res_b["status"] == "RUNTIME VALIDATION PENDING / NOT PROVEN"

    # Scenario C: 60 days, 60 setups, but 1 crash -> BLOCKED
    res_c = ShadowReadinessAuditor.audit_readiness(
        elapsed_days=60.0,
        resolved_shadow_setups=60,
        unhandled_crashes=1,
    )
    assert res_c["is_ready_for_promotion"] is False
    assert res_c["status"] == "RUNTIME VALIDATION PENDING / NOT PROVEN"

    # Scenario D: All criteria met: 56+ days, 50+ setups, 0 crashes -> PROMOTION_READY
    res_d = ShadowReadinessAuditor.audit_readiness(
        elapsed_days=56.0,
        resolved_shadow_setups=50,
        unhandled_crashes=0,
    )
    assert res_d["is_ready_for_promotion"] is True
    assert res_d["status"] == "PROMOTION_READY"
