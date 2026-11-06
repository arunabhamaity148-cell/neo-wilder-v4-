# IMPLEMENTATION_ROADMAP.md

Each phase has a numeric go/no-go. **No phase may start before the previous one is signed off.**

## Phase 0 — Source & document audit  ✅ DONE (this report)
Deliverables: `LEGACY_EDGE_VETO_INVENTORY.md`, count reconciliation table.
Acceptance: every legacy file accounted for; every claim in the supplied PDFs either CONFIRMED or CONTRADICTED.
Verification: 201 files listed, 32 edge rows, 50 veto rows, 10 integrity defects.

## Phase 1 — Registries frozen
Deliverables: `EDGE_REGISTRY.yaml`, `VETO_REGISTRY.yaml`, `EDGE_DEPENDENCY_MATRIX.md`.
Acceptance: YAML parses; every edge has status/evidence; every veto has an id and a test.
Go: registries load in CI and reject unknown ids.

## Phase 2 — Data plane + integrity
Deliverables: `data/*`, `integrity.py`, replay fixtures (>= 90 days x 8 symbols).
Acceptance: 6-hour soak with zero unhandled disconnects; gap detection catches 100% of injected gaps;
RSS < 120 MB after 6 h. Fail: any unbounded buffer growth.

## Phase 3 — Feature engine
Acceptance: determinism test — shuffle future bars, all feature outputs for index `t` identical;
feature parity vs a slow reference pandas implementation within 1e-9.
Fail: any look-ahead leak, any NaN escaping into edges.

## Phase 4 — Edge modules
Acceptance: each edge has positive fixture + negative fixture + ABSTAIN test; registry-driven on/off.

## Phase 5 — Strategies + regime
Acceptance: S1 emits candidates on the historical fixture at a rate of 0.5-6 per symbol-day;
100% of emitted candidates pass V-H19..V-H21 in a synthetic geometry test.

## Phase 6 — Veto framework
Acceptance: 34 hard-veto tests + 15 soft-veto tests pass; a "score 100 with veto" test must block;
chaos test (kill feed, skew clock, fill disk) never publishes.

## Phase 7 — Scoring + calibration
Acceptance: group caps enforced (max 24 pts from C1+C2); reliability diagram on OOS with
Brier score reported; **if the calibration set has < 300 resolved trades, the system publishes
`NOT CALIBRATED` and no probability number.**

## Phase 8 — CoinDCX validation + risk geometry
Acceptance: 200 live public quotes captured; symbol mapping 100% resolved; drift veto fires
exactly when `|Δ| > 0.35%`; net R:R recomputed with the real fee table (incl. GST) and cross-checked
against a hand calculation.

## Phase 9 — Backtest + ablation  (the gate)
Acceptance: `BACKTEST_PROTOCOL.md` §6 table filled for S1 alone, S1+S2, full system, and
`full minus each of 12 edges`; bootstrap CI reported; cost contribution reported.
Go condition: **full system net expectancy > S1 alone net expectancy, with OOS degradation < 40%**.
No-go: revert to S1 alone. This is the single decision that determines whether the multi-edge
architecture is justified.

## Phase 10 — Shadow mode (>= 8 weeks)
Signals generated but sent to a private channel only. Acceptance: signal rate within forecast band,
zero hard-veto misses, journal reconciliation 100%.

## Phase 11 — Manual paper validation (>= 100 resolved signals)
Acceptance: hit rate CI overlap with backtest CI; slippage within model; fill rate recorded.

## Phase 12 — Controlled live
Acceptance: 4 consecutive profitable weeks with no rule breach OR a pre-committed evaluation window;
daily loss cap and kill switch rehearsed. Demotion is automatic on 2 consecutive rule breaches.

## Failure conditions that stop everything
- Any look-ahead leak. Any published signal without CoinDCX validation. Any hard veto bypassed.
- OOS degradation > 60% at Phase 9.
- RSS > 300 MB in shadow.
