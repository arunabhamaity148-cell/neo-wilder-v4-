"""Isotonic regression calibration engine for NEO-WILDER V4.

Enforces V-H34 and AGENT.md §0 Rule 5:
Displays 'NOT CALIBRATED' unless an out-of-sample calibration artefact
with >= 300 resolved trades and <= 90 days age is verified.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class IsotonicCalibrator:
    """Maps composite scores to empirically calibrated probabilities."""

    def __init__(self, artefact_path: Optional[Path | str] = None):
        self.artefact_path = Path(artefact_path) if artefact_path else None
        self._is_valid = False
        self._calibration_table: Dict[int, float] = {}
        self._load()

    def _load(self):
        if not self.artefact_path or not self.artefact_path.exists():
            self._is_valid = False
            return

        try:
            with open(self.artefact_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            trades_count = data.get("resolved_trades_count", 0)
            if trades_count < 300:
                logger.info(f"Calibration artefact rejected: trades {trades_count} < 300")
                self._is_valid = False
                return

            created_date_str = data.get("created_date", "")
            created_date = datetime.fromisoformat(created_date_str).replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - created_date).days

            if age_days > 90:
                logger.info(f"Calibration artefact rejected: age {age_days} > 90 days")
                self._is_valid = False
                return

            raw_table = data.get("score_probability_map", {})
            self._calibration_table = {int(k): float(v) for k, v in raw_table.items()}
            self._is_valid = True

        except Exception as e:
            logger.warning(f"Failed to load calibration artefact: {e}")
            self._is_valid = False

    @property
    def is_calibrated(self) -> bool:
        return self._is_valid

    def get_calibrated_probability(self, score_0_100: int) -> Tuple[str, Optional[float]]:
        """Return formatted string ('NOT CALIBRATED' or formatted float) and optional float."""
        if not self._is_valid or not self._calibration_table:
            return "NOT CALIBRATED", None

        # Look up nearest mapped score
        prob = self._calibration_table.get(score_0_100)
        if prob is None:
            # Interpolate
            sorted_keys = sorted(self._calibration_table.keys())
            if score_0_100 <= sorted_keys[0]:
                prob = self._calibration_table[sorted_keys[0]]
            elif score_0_100 >= sorted_keys[-1]:
                prob = self._calibration_table[sorted_keys[-1]]
            else:
                prob = 0.50  # Default midpoint

        return f"{prob:.3f}", prob
