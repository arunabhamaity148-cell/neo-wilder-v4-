# BLUEPRINT.md — NEO-WILDER V4 (Signal-Only, Modular Monolith)

## 1. One-line architecture
`Data plane -> Feature plane -> Edge plane -> Strategy plane -> Veto plane -> Score plane -> Publish plane`,
executed as a single asyncio process over a bounded event queue, with a separate offline research repo.

## 2. The five planes
| Plane | Responsibility | Hard rule |
|---|---|---|
| Data | Binance USD-M WS/REST ingest + CoinDCX public validation | never trades, never needs keys |
| Feature | deterministic, versioned, causal-only features | no look-ahead; `t` uses data <= `t` |
| Edge | one function per edge, returns EdgeResult or ABSTAIN | no edge can publish alone |
| Strategy | composes 1 setup edge + N confirmations into a candidate | max 3 strategies live |
| Veto | ordered hard vetoes then soft modifiers | hard veto = final |
| Score | 5 orthogonal groups, group caps, calibrated probability | score != probability |

## 3. Architecture decision (chosen: E — Hybrid, "One Spine, Three Plugs")
- A single **spine**: Liquidity Sweep + Reclaim (the only legacy setup with a complete, testable
  definition) generates candidates.
- **Plugs**: EdgeConfirmation (order flow / OI / basis) and RegimeRouting (which confirmations are
  required in which regime). Sessions act as soft modifiers, not as their own engines.
- Rejected: B (many independent bots) — correlation and ops cost blow past a 1 GB VPS;
  D (regime-first routing) — the regime classifier is not yet validated, so routing on it would
  multiply an unvalidated model; A (single strategy, no confirmation) — discards the only real
  legacy asset (microstructure confirmation).
- Evidence status: **ENGINEERING RECOMMENDATION**, not an empirical result. It must be re-decided
  after Phase 9 ablation (see BACKTEST_PROTOCOL.md).

## 4. Data plane
- Primary: `wss://fstream.binance.com/stream` streams `aggTrade`, `kline_5m`, `depth20@100ms`,
  `!forceOrder@arr`. Verified against the legacy client (stream.py:309-311) and Binance docs.
- Secondary/REST poll (>=30 s): `/fapi/v1/openInterest`, `/futures/data/openInterestHist`,
  `/fapi/v1/premiumIndex`, `/fapi/v1/klines`.
- Validation: CoinDCX public `current_prices/futures/rt` + `orderbook/{pair}-futures/10`.
- Data tiers: `TIER_A` (WS live), `TIER_B` (REST <=60 s old), `TIER_C` (older/missing) -> TIER_C blocks.

## 5. Publish plane
Signal object is immutable; every field in `COINDCX_MANUAL_EXECUTION_SPEC.md` §3 is mandatory.
Publication requires: 0 hard vetoes, score >= threshold, net R:R >= 1.5 after real fees,
CoinDCX validation price present and drift <= 0.35%.

## 6. Explicit non-goals (v4.0)
No GEX routing, no LSTM, no Hawkes-driven gating, no microbar volume-clock execution logic,
no sub-second Microprice entry timing, no Deribit cold path. All retained as SHADOW telemetry only.
