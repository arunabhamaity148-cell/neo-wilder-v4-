"""Watchdog and degradation ladder for NEO-WILDER V4.

Tracks periodic heartbeats from incoming data feeds.
Triggers degradation levels and fail-closed halt if consecutive ticks are missed:
- Level 0: NORMAL
- Level 1: DEGRADED_WARNING (1 missed interval)
- Level 2: DEGRADED_SEVERE (2 missed intervals)
- Level 3: EMERGENCY_HALT (>=3 missed intervals) -> asserts V-H09 / V-H10
"""

import logging
import time
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class DegradationLevel(Enum):
    NORMAL = 0
    DEGRADED_WARNING = 1
    DEGRADED_SEVERE = 2
    EMERGENCY_HALT = 3


class ProcessWatchdog:
    """Monitors heartbeat liveness and escalates degradation."""

    def __init__(self, interval_seconds: float = 15.0, max_misses: int = 3):
        self.interval_seconds = interval_seconds
        self.max_misses = max_misses
        self.last_heartbeat = time.monotonic()
        self.missed_ticks = 0
        self.level = DegradationLevel.NORMAL

    def beat(self):
        """Register a heartbeat from the active data loop."""
        self.last_heartbeat = time.monotonic()
        if self.missed_ticks > 0:
            logger.info("Watchdog heartbeat restored. Resetting degradation ladder to NORMAL.")
        self.missed_ticks = 0
        self.level = DegradationLevel.NORMAL

    def evaluate_liveness(self, current_time: Optional[float] = None) -> DegradationLevel:
        """Evaluate elapsed time since last heartbeat and update degradation level."""
        now = current_time if current_time is not None else time.monotonic()
        elapsed = now - self.last_heartbeat

        # Number of missed intervals
        missed = int(elapsed // self.interval_seconds)
        self.missed_ticks = missed

        if missed == 0:
            self.level = DegradationLevel.NORMAL
        elif missed == 1:
            self.level = DegradationLevel.DEGRADED_WARNING
            logger.warning(f"Watchdog warning: {elapsed:.1f}s since last heartbeat (1 tick missed)")
        elif missed == 2:
            self.level = DegradationLevel.DEGRADED_SEVERE
            logger.error(f"Watchdog severe: {elapsed:.1f}s since last heartbeat (2 ticks missed)")
        else:
            self.level = DegradationLevel.EMERGENCY_HALT
            logger.critical(
                f"[WATCHDOG EMERGENCY HALT] {elapsed:.1f}s since last heartbeat ({missed} ticks missed). V-H09/V-H10 asserted."
            )

        return self.level

    @property
    def is_halted(self) -> bool:
        """Returns True if watchdog is in EMERGENCY_HALT state."""
        return self.level == DegradationLevel.EMERGENCY_HALT

    def get_veto_flags(self) -> dict:
        """Return veto status dictionary for integration with VetoPipeline."""
        return {
            "V_H09": self.is_halted,  # Websocket / feed watchdog trip
            "V_H10": self.is_halted,  # Subprocess / loop stall
        }
