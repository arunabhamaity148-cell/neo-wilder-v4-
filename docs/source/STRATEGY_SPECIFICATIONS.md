# STRATEGY_SPECIFICATIONS.md

All strategies share: setup TF 15m (closed bars only), context TF 1h/4h, execution = manual CoinDCX,
minimum **net** R:R 1.50 after 0.1354% friction, hard vetoes from `VETO_REGISTRY.yaml` applied after the
strategy emits a candidate.

---

## S1 — SWEEP-RECLAIM-v4 (ACTIVE, the spine)
**Setup conditions (all mandatory)**
1. A liquidity pool exists (>=2 swings within 0.15 ATR) at or beyond the current swing extreme. `E04`
2. A 15m bar wicks beyond the pool by `d = (pool - low)` where `0.05 ATR <= d <= 1.2 ATR`. `E01`
3. The same bar closes back inside the pool: `close > pool` (LONG) / `close < pool` (SHORT).
4. Reclaim confirmed within 2 bars.
5. **At least one** confirmation: `E05` structure shift OR displacement body > 0.6 ATR OR volume > 1.2x median.
**Entry**
- Entry zone = `[min(close_reclaim, pool), close_reclaim]` for LONG, widened to a minimum width of
  `max(0.20%, 0.05 ATR)`.
- Reference price = `close` of the reclaim bar (never the live price).
**Stop** — `sweep_extreme - buffer * ATR`, `buffer = alpha(pct_ATR) + 0.6·1[|funding| >= 0.03%]`,
`alpha ∈ {1.5, 2.2, 3.0}` at the 30/80 percentile of the last 100 ATR values (legacy E12, retained verbatim).
**Targets** — TP1 = nearest opposing swing or VAL/VAH that is >= 1.5R away; TP2 = 1.618 extension of TP1.
If no such level exists, the trade is **not taken** (v4 removes the legacy fallback that manufactured
an ATR-based target, because a manufactured target makes R:R a tautology).
**Expiry** — `min(16, 4 + 2·vol_tier)` bars on 15m, plus CHoCH invalidation, plus MFE half-life rule (E28).
**Must not trade when** — `NOISE_CHOP`, `atr_bps < 4`, weekend low-liquidity window, or
`rel_vol < 0.8` (X02).

## S2 — OI-EXHAUSTION-v4 (SHADOW until validated)
`E21` conditions plus a mandatory `E15` CVD turn and a mandatory `E13 Z_liq >= 2.0`.
LONG only in v4.0. Stop = flush low − 1.0 ATR. TP1 = prior 1h swing high; net R:R >= 1.5 else reject.
Cannot fire within 30 min of S1 on the same symbol.

## S3 — BASIS-DIVERGENCE-v4 (EXPERIMENTAL)
`E22` with the threshold tightened from ±0.5σ to ±1.5σ and requiring 3 consecutive bars of the same sign.
Requires synchronised spot+perp feeds with a measured clock offset; if the offset > 150 ms, the strategy abstains.

## Rejected strategy families (with reason)
| Family | Decision | Reason |
|---|---|---|
| Session Sweep + Reclaim as separate engine | NOT BUILT | Session is already a soft modifier (E27); a 4th engine multiplies config surface for an unmeasured effect |
| Trend Pullback Continuation | NOT BUILT | Requires a validated trend classifier; E25 is not calibrated yet |
| Mean-Reversion Reversal (pure) | NOT BUILT | No legacy implementation, no verified feature stack distinct from S1 |
| Funding/OI Crowding Reversal | NOT BUILT | 8h funding cadence gives too few independent events per month to validate on 1-2 years of data |
| Liquidation Flush + Absorption as a standalone engine | FOLDED INTO S2 | Otherwise S2 and it would double-count C1 |

## Regime eligibility table
| Regime (E25) | S1 | S2 | S3 |
|---|---|---|---|
| MEAN_REVERSION / ROTATIONAL | ON | ON | OFF |
| NEUTRAL | ON | OFF | ON |
| MOMENTUM_TREND | ON with `V-S13` check | ON | ON |
| NOISE_CHOP | OFF (hard veto V-H33) | OFF | OFF |
| LIQUIDITY_STRESS (atr_bps > 400 or spread veto) | OFF | OFF | OFF |
