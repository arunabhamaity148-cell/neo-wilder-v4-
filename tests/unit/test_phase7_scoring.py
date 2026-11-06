"""Unit tests for Phase 7: Scoring and Calibration Engine."""

import json
from datetime import datetime, timezone
from pathlib import Path

from neo_wilder.domain.enums import Direction, RegimeState
from neo_wilder.domain.models import Candidate, EdgeResult
from neo_wilder.edges.registry import EdgeRegistry
from neo_wilder.scoring.calibrate import IsotonicCalibrator
from neo_wilder.scoring.groups import CompositeScorer


def _build_test_candidate(net_rr: float = 2.00) -> Candidate:
    return Candidate(
        symbol="BTCUSDT",
        direction=Direction.LONG,
        strategy_id="S1_SWEEP_RECLAIM",
        setup_edge_id="E01",
        reference_price=70000.0,
        entry_zone_low=69900.0,
        entry_zone_high=70000.0,
        stop_loss=69500.0,
        tp1=71000.0,
        tp2=None,
        gross_rr=2.00,
        net_rr=net_rr,
        active_edge_ids=["E01"],
        confirming_edge_ids=[],
        expiry_bars=16,
        regime=RegimeState.NEUTRAL,
        created_at_utc="2026-11-06T12:00:00Z",
    )


def test_scoring_cluster_caps_and_c1_c2_limit():
    registry = EdgeRegistry(Path("config/edge_registry.yaml"))
    scorer = CompositeScorer(registry)
    candidate = _build_test_candidate(net_rr=1.50)  # rr_bonus = 0

    # Inject multiple edges with high raw score contributions
    edge_results = {
        "E01": EdgeResult(
            edge_id="E01",
            passed=True,
            confidence=1.0,
            direction=Direction.LONG,
            score_contribution=10,
        ),
        "E07": EdgeResult(
            edge_id="E07",
            passed=True,
            confidence=1.0,
            direction=Direction.LONG,
            score_contribution=15,
        ),  # C5 cap is 10
        "E05": EdgeResult(
            edge_id="E05",
            passed=True,
            confidence=1.0,
            direction=Direction.LONG,
            score_contribution=10,
        ),  # SHADOW!
        "E17": EdgeResult(
            edge_id="E17",
            passed=True,
            confidence=1.0,
            direction=Direction.LONG,
            score_contribution=10,
        ),  # SHADOW!
    }

    breakdown = scorer.score(candidate, edge_results)

    # C5 is capped at 10 (despite E07 having 15)
    assert breakdown.cluster_scores["C5"] == 10

    # Shadow edges E05 and E17 contribute 0
    assert breakdown.cluster_scores["C2"] == 0  # E17 is shadow

    # Base setup is 60 + C3 (E01: 10) + C5 (10) = 80
    assert breakdown.total_score == 80


def test_rr_bonus_scaling():
    registry = EdgeRegistry(Path("config/edge_registry.yaml"))
    scorer = CompositeScorer(registry)

    # net_rr = 2.50 (+1.00 above 1.50 -> 4 steps of 0.25 -> rr_bonus = 4)
    cand_high_rr = _build_test_candidate(net_rr=2.50)
    res_high = scorer.score(cand_high_rr, {})
    assert res_high.rr_bonus == 4

    # net_rr = 1.75 (+0.25 above 1.50 -> rr_bonus = 1)
    cand_mid_rr = _build_test_candidate(net_rr=1.75)
    res_mid = scorer.score(cand_mid_rr, {})
    assert res_mid.rr_bonus == 1


def test_isotonic_calibrator_not_calibrated_by_default():
    calibrator = IsotonicCalibrator(artefact_path=None)
    prob_str, prob_val = calibrator.get_calibrated_probability(88)
    assert prob_str == "NOT CALIBRATED"
    assert prob_val is None


def test_isotonic_calibrator_with_valid_artefact(tmp_path: Path):
    artefact_file = tmp_path / "score_v4_test.json"
    now_iso = datetime.now(timezone.utc).isoformat()

    valid_data = {
        "resolved_trades_count": 350,
        "created_date": now_iso,
        "score_probability_map": {
            "75": 0.52,
            "85": 0.64,
            "90": 0.75,
        },
    }
    with open(artefact_file, "w", encoding="utf-8") as f:
        json.dump(valid_data, f)

    calibrator = IsotonicCalibrator(artefact_path=artefact_file)
    assert calibrator.is_calibrated is True

    prob_str, prob_val = calibrator.get_calibrated_probability(85)
    assert prob_str == "0.640"
    assert prob_val == 0.64


def test_isotonic_calibrator_rejects_under_300_trades(tmp_path: Path):
    artefact_file = tmp_path / "score_v4_insufficient.json"
    now_iso = datetime.now(timezone.utc).isoformat()

    invalid_data = {
        "resolved_trades_count": 150,  # Under 300
        "created_date": now_iso,
        "score_probability_map": {"85": 0.64},
    }
    with open(artefact_file, "w", encoding="utf-8") as f:
        json.dump(invalid_data, f)

    calibrator = IsotonicCalibrator(artefact_path=artefact_file)
    assert calibrator.is_calibrated is False
    prob_str, _ = calibrator.get_calibrated_probability(85)
    assert prob_str == "NOT CALIBRATED"
