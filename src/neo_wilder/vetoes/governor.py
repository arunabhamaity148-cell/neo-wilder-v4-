"""Portfolio risk, loss cap, and concurrency governor for NEO-WILDER V4.

Tracks account exposure, cooldowns, and daily/weekly drawdown limits.
"""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Set


@dataclass
class AccountGovernorState:
    """Live state of portfolio exposure and locks."""

    open_positions: List[Dict] = field(default_factory=list)
    active_symbols: Set[str] = field(default_factory=set)
    symbol_last_signal_time: Dict[str, float] = field(default_factory=dict)
    day_start_equity: float = 10000.0
    current_equity: float = 10000.0
    week_start_equity: float = 10000.0
    operator_kill_switch: bool = False
    watchdog_healthy: bool = True
    watchdog_missed_beats: int = 0
    trading_halted_symbols: Set[str] = field(default_factory=set)


class PortfolioGovernor:
    """Enforces concurrency limits, symbol locks, and drawdown caps."""

    def __init__(
        self,
        max_concurrent: int = 2,
        max_open_risk_pct: float = 3.0,
        cooldown_sec: float = 1800.0,
        max_daily_loss_pct: float = 3.0,
        max_weekly_loss_pct: float = 6.0,
    ):
        self.max_concurrent = max_concurrent
        self.max_open_risk_pct = max_open_risk_pct
        self.cooldown_sec = cooldown_sec
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_weekly_loss_pct = max_weekly_loss_pct
        self.state = AccountGovernorState()

    def is_symbol_locked(self, symbol: str) -> bool:
        """Check V-H25: symbol cooldown lock."""
        last_time = self.state.symbol_last_signal_time.get(symbol, 0.0)
        return (time.monotonic() - last_time) < self.cooldown_sec

    def is_duplicate_signal(self, symbol: str, direction: str, strategy: str) -> bool:
        """Check V-H24: duplicate signal within 30 min."""
        # Symbol lock covers identical symbol within 30 min
        return self.is_symbol_locked(symbol)

    def record_signal_published(self, symbol: str):
        """Update cooldown timestamp."""
        self.state.symbol_last_signal_time[symbol] = time.monotonic()

    @property
    def concurrent_count(self) -> int:
        return len(self.state.open_positions)

    @property
    def daily_drawdown_pct(self) -> float:
        if self.state.day_start_equity <= 0:
            return 0.0
        return (
            (self.state.day_start_equity - self.state.current_equity) / self.state.day_start_equity
        ) * 100.0

    @property
    def weekly_drawdown_pct(self) -> float:
        if self.state.week_start_equity <= 0:
            return 0.0
        return (
            (self.state.week_start_equity - self.state.current_equity)
            / self.state.week_start_equity
        ) * 100.0

    def is_daily_loss_breached(self) -> bool:
        """Check V-H28: daily loss cap."""
        return self.daily_drawdown_pct >= self.max_daily_loss_pct

    def is_weekly_loss_breached(self) -> bool:
        """Check V-H29: weekly loss cap."""
        return self.weekly_drawdown_pct >= self.max_weekly_loss_pct
