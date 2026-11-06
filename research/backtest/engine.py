"""Institutional Backtest Engine for NEO-WILDER V4 Research.

Conforms strictly to BACKTEST_PROTOCOL.md:
- 4-Component Cost Model: Taker Fee (0.050%) + GST (18%) + Slippage + Funding.
- Next-Bar Open Fill simulation (never close_t).
- Missed-fill tracking if next bar doesn't touch entry zone.
- Intrabar Ambiguity: If both SL and TP are hit in the same bar, resolve SL first.
- Bootstrap 10,000 resamples for 5th percentile expectancy.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Constants per BACKTEST_PROTOCOL.md
COINDCX_TAKER_FEE = 0.00050  # 0.050%
GST_RATE = 0.18  # 18%
EFFECTIVE_RT_FEE = COINDCX_TAKER_FEE * (1.0 + GST_RATE) * 2.0  # 0.1180%


@dataclass
class BacktestTrade:
    trade_id: str
    symbol: str
    direction: str  # "LONG" or "SHORT"
    entry_bar_idx: int
    entry_price: float
    stop_loss: float
    tp1: float
    risk_r: float
    exit_bar_idx: Optional[int] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None  # "TP1_HIT", "SL_HIT", "EXPIRED", "MISSED"
    gross_pnl_pct: float = 0.0
    net_pnl_pct: float = 0.0
    realized_r: float = 0.0
    holding_bars: int = 0
    slippage_pct: float = 0.0
    funding_pct: float = 0.0
    fee_pct: float = EFFECTIVE_RT_FEE
    regime: str = "UNKNOWN"


@dataclass
class BacktestReport:
    total_signals: int
    filled_trades: int
    missed_trades: int
    missed_fill_rate: float
    wins: int
    losses: int
    win_rate: float
    avg_win_r: float
    avg_loss_r: float
    expectancy_r: float
    net_profit_factor: float
    net_avg_r: float
    max_drawdown_r: float
    max_drawdown_pct: float
    max_losing_streak: int
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    signals_per_day: float
    total_cost_contribution_r: float
    bootstrap_5th_pct_expectancy: float
    regime_breakdown: Dict[str, Dict[str, float]] = field(default_factory=dict)


class BacktestCostModel:
    """Computes all 4 mandatory friction components."""

    @staticmethod
    def calculate_slippage(spread_bps: float, atr_bps: float) -> float:
        """Slippage model: 0.5 * spread_bps + 0.3 * ATR_bps/100, floor 1.0 bp."""
        slip_bps = 0.5 * spread_bps + 0.3 * (atr_bps / 100.0)
        slip_bps = max(1.0, slip_bps)
        return slip_bps / 10000.0  # convert bps to decimal fraction

    @staticmethod
    def calculate_funding(rate_8h: float, holding_bars_15m: int) -> float:
        """Funding cost accumulated over 15m holding intervals."""
        # 1 funding period = 8 hours = 32 x 15m bars
        funding_periods = holding_bars_15m / 32.0
        return rate_8h * funding_periods


class BacktestEngine:
    """Executes event-driven backtests over historical 15m candle sequences."""

    def __init__(
        self,
        default_spread_bps: float = 4.0,
        default_funding_8h: float = 0.0001,
        bootstrap_iterations: int = 10000,
        random_seed: int = 42,
    ):
        self.default_spread_bps = default_spread_bps
        self.default_funding_8h = default_funding_8h
        self.bootstrap_iterations = bootstrap_iterations
        self.rng = np.random.default_rng(random_seed)

    def simulate_trades(
        self,
        signals: List[Dict],
        highs: np.ndarray,
        lows: np.ndarray,
        opens: np.ndarray,
        closes: np.ndarray,
        atrs: np.ndarray,
        funding_rates: Optional[np.ndarray] = None,
        max_holding_bars: int = 48,
    ) -> List[BacktestTrade]:
        """Simulate trade execution with next-bar fill and intrabar ambiguity resolution."""
        trades: List[BacktestTrade] = []
        n_bars = len(closes)

        for sig in signals:
            sig_bar = sig["bar_idx"]
            if sig_bar + 1 >= n_bars:
                continue

            trade_id = sig["signal_id"]
            symbol = sig.get("symbol", "BTCUSDT")
            direction = sig.get("direction", "LONG")
            regime = sig.get("regime", "UNKNOWN")
            entry_low = sig["entry_zone_low"]
            entry_high = sig["entry_zone_high"]
            sl = sig["stop_loss"]
            tp1 = sig["tp1"]

            # Next-bar open fill simulation (Rule §3: never close_t)
            next_open = opens[sig_bar + 1]
            next_high = highs[sig_bar + 1]
            next_low = lows[sig_bar + 1]

            # Check if next bar range touches entry zone
            touches_entry = not (next_high < entry_low or next_low > entry_high)
            if not touches_entry:
                # Recorded as MISSED (counted, not deleted)
                trade = BacktestTrade(
                    trade_id=trade_id,
                    symbol=symbol,
                    direction=direction,
                    entry_bar_idx=sig_bar + 1,
                    entry_price=(entry_low + entry_high) / 2.0,
                    stop_loss=sl,
                    tp1=tp1,
                    risk_r=0.0,
                    exit_bar_idx=sig_bar + 1,
                    exit_price=None,
                    exit_reason="MISSED",
                    gross_pnl_pct=0.0,
                    net_pnl_pct=0.0,
                    realized_r=0.0,
                    holding_bars=0,
                    regime=regime,
                )
                trades.append(trade)
                continue

            # Fill at next bar open or entry zone mid
            fill_price = max(entry_low, min(entry_high, next_open))
            risk_dist = abs(fill_price - sl)
            if risk_dist <= 0:
                risk_dist = 1e-4

            # Calculate slippage
            bar_atr = atrs[sig_bar + 1] if sig_bar + 1 < len(atrs) else fill_price * 0.01
            atr_bps = (bar_atr / fill_price) * 10000.0
            slip_pct = BacktestCostModel.calculate_slippage(self.default_spread_bps, atr_bps)

            trade = BacktestTrade(
                trade_id=trade_id,
                symbol=symbol,
                direction=direction,
                entry_bar_idx=sig_bar + 1,
                entry_price=fill_price,
                stop_loss=sl,
                tp1=tp1,
                risk_r=risk_dist / fill_price,
                slippage_pct=slip_pct,
                regime=regime,
            )

            # Evaluate subsequent bars
            exit_bar = None
            exit_price = None
            exit_reason = None

            start_eval_bar = sig_bar + 1
            end_eval_bar = min(n_bars, start_eval_bar + max_holding_bars)

            for b in range(start_eval_bar, end_eval_bar):
                b_high = highs[b]
                b_low = lows[b]

                if direction == "LONG":
                    hit_sl = b_low <= sl
                    hit_tp = b_high >= tp1

                    # INTRABAR AMBIGUITY: if both hit in the same bar, resolve SL first!
                    if hit_sl and hit_tp:
                        exit_bar = b
                        exit_price = sl
                        exit_reason = "SL_HIT"
                        break
                    elif hit_sl:
                        exit_bar = b
                        exit_price = sl
                        exit_reason = "SL_HIT"
                        break
                    elif hit_tp:
                        exit_bar = b
                        exit_price = tp1
                        exit_reason = "TP1_HIT"
                        break

            # Handle expiry if neither hit
            if exit_reason is None:
                exit_bar = end_eval_bar - 1
                exit_price = closes[exit_bar]
                exit_reason = "EXPIRED"

            holding_bars = exit_bar - (sig_bar + 1)
            trade.exit_bar_idx = exit_bar
            trade.exit_price = exit_price
            trade.exit_reason = exit_reason
            trade.holding_bars = holding_bars

            # Funding rate calculation
            funding_rate_8h = (
                funding_rates[exit_bar]
                if funding_rates is not None and exit_bar < len(funding_rates)
                else self.default_funding_8h
            )
            funding_pct = BacktestCostModel.calculate_funding(funding_rate_8h, holding_bars)
            trade.funding_pct = funding_pct

            # PnL & R calculations
            if direction == "LONG":
                gross_pct = (exit_price - fill_price) / fill_price
            else:
                gross_pct = (fill_price - exit_price) / fill_price

            total_friction = trade.fee_pct + trade.slippage_pct + trade.funding_pct
            net_pct = gross_pct - total_friction

            trade.gross_pnl_pct = gross_pct
            trade.net_pnl_pct = net_pct

            # Realized R
            risk_pct = trade.risk_r
            trade.realized_r = net_pct / max(risk_pct, 1e-4)

            trades.append(trade)

        return trades

    def evaluate(
        self, trades: List[BacktestTrade], total_bars: Optional[int] = None
    ) -> BacktestReport:
        """Compute full performance metrics suite conforming to §6."""
        total_signals = len(trades)
        if total_signals == 0:
            return BacktestReport(
                total_signals=0,
                filled_trades=0,
                missed_trades=0,
                missed_fill_rate=0.0,
                wins=0,
                losses=0,
                win_rate=0.0,
                avg_win_r=0.0,
                avg_loss_r=0.0,
                expectancy_r=0.0,
                net_profit_factor=0.0,
                net_avg_r=0.0,
                max_drawdown_r=0.0,
                max_drawdown_pct=0.0,
                max_losing_streak=0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                signals_per_day=0.0,
                total_cost_contribution_r=0.0,
                bootstrap_5th_pct_expectancy=0.0,
            )

        missed = [t for t in trades if t.exit_reason == "MISSED"]
        filled = [t for t in trades if t.exit_reason != "MISSED"]
        missed_fill_rate = len(missed) / total_signals

        if not filled:
            return BacktestReport(
                total_signals=total_signals,
                filled_trades=0,
                missed_trades=len(missed),
                missed_fill_rate=1.0,
                wins=0,
                losses=0,
                win_rate=0.0,
                avg_win_r=0.0,
                avg_loss_r=0.0,
                expectancy_r=0.0,
                net_profit_factor=0.0,
                net_avg_r=0.0,
                max_drawdown_r=0.0,
                max_drawdown_pct=0.0,
                max_losing_streak=0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                signals_per_day=0.0,
                total_cost_contribution_r=0.0,
                bootstrap_5th_pct_expectancy=0.0,
            )

        realized_rs = np.array([t.realized_r for t in filled])
        wins = realized_rs[realized_rs > 0]
        losses = realized_rs[realized_rs <= 0]

        n_wins = len(wins)
        n_losses = len(losses)
        win_rate = n_wins / len(filled)

        avg_win_r = float(np.mean(wins)) if n_wins > 0 else 0.0
        avg_loss_r = float(np.mean(losses)) if n_losses > 0 else 0.0
        expectancy_r = (win_rate * avg_win_r) + ((1.0 - win_rate) * avg_loss_r)

        gross_profit = float(np.sum(wins)) if n_wins > 0 else 0.0
        gross_loss = float(abs(np.sum(losses))) if n_losses > 0 else 0.0
        net_profit_factor = gross_profit / max(gross_loss, 1e-4)

        net_avg_r = float(np.mean(realized_rs))

        # Drawdown calculation (peak-to-trough from initial equity 0.0)
        cumulative_r = np.insert(np.cumsum(realized_rs), 0, 0.0)
        running_max = np.maximum.accumulate(cumulative_r)
        drawdowns = running_max - cumulative_r
        max_dd_r = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

        # Max losing streak
        max_streak = 0
        current_streak = 0
        for r in realized_rs:
            if r <= 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0

        # Sharpe and Sortino
        std_r = float(np.std(realized_rs))
        sharpe = (net_avg_r / std_r) * np.sqrt(252.0) if std_r > 0 else 0.0

        downside_rs = realized_rs[realized_rs < 0]
        downside_std = float(np.std(downside_rs)) if len(downside_rs) > 0 else 0.0
        sortino = (net_avg_r / downside_std) * np.sqrt(252.0) if downside_std > 0 else 0.0
        calmar = (net_avg_r * len(filled)) / max(max_dd_r, 1e-4)

        # Bootstrap 10,000 resamples for 5th percentile expectancy
        bootstrap_means = np.empty(self.bootstrap_iterations)
        n_trades = len(realized_rs)
        for i in range(self.bootstrap_iterations):
            sample = self.rng.choice(realized_rs, size=n_trades, replace=True)
            bootstrap_means[i] = np.mean(sample)

        bootstrap_5th_pct = float(np.percentile(bootstrap_means, 5.0))

        # Cost contribution
        total_costs_r = sum(
            (t.fee_pct + t.slippage_pct + t.funding_pct) / max(t.risk_r, 1e-4) for t in filled
        )

        # Regime breakdown
        regime_breakdown = {}
        for reg in set(t.regime for t in filled):
            reg_trades = [t for t in filled if t.regime == reg]
            reg_rs = [t.realized_r for t in reg_trades]
            reg_wins = [r for r in reg_rs if r > 0]
            regime_breakdown[reg] = {
                "count": len(reg_trades),
                "win_rate": len(reg_wins) / len(reg_trades) if reg_trades else 0.0,
                "avg_r": float(np.mean(reg_rs)) if reg_trades else 0.0,
            }

        # Estimate bars from trades if not explicitly passed
        if total_bars is not None:
            effective_bars = total_bars
        else:
            max_exit = max(
                (t.exit_bar_idx for t in trades if t.exit_bar_idx is not None), default=96
            )
            effective_bars = max(96, max_exit)

        return BacktestReport(
            total_signals=total_signals,
            filled_trades=len(filled),
            missed_trades=len(missed),
            missed_fill_rate=missed_fill_rate,
            wins=n_wins,
            losses=n_losses,
            win_rate=win_rate,
            avg_win_r=avg_win_r,
            avg_loss_r=avg_loss_r,
            expectancy_r=expectancy_r,
            net_profit_factor=net_profit_factor,
            net_avg_r=net_avg_r,
            max_drawdown_r=max_dd_r,
            max_drawdown_pct=max_dd_r * 1.5,  # scaled by position sizing fraction
            max_losing_streak=max_streak,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            signals_per_day=float(len(filled) / max(1.0, effective_bars / 96.0)),  # 96 15m bars/day
            total_cost_contribution_r=total_costs_r,
            bootstrap_5th_pct_expectancy=bootstrap_5th_pct,
            regime_breakdown=regime_breakdown,
        )
