# EDGE_RECONCILIATION.md — NEO-WILDER V4 Edge Inventory & Reconciliation

**Audit Date:** 2026-11-06  
**Auditor Role:** Chief Architect & Main Integrator  
**Audit Scope:** Comprehensive reconciliation of all 32 edges (28 legacy + 4 new), evidence classifications, data dependencies, cluster allocations, and isolation rules.

---

## 1. Complete 32-Edge Master Reconciliation Table

| ID | Edge Name | Archetype | Dir | V4 Status | Evidence Status | Primary Data Dependencies | Scoring Cluster | Activation / Gating Rule | Known Failure Mode / Missing Info |
|---|---|---|---|---|---|---|---|---|---|
| **E01** | Liquidity Sweep & Reclaim | SETUP | BOTH | **ACTIVE** | PROMISING | 15m klines, Swings (`E04`), ATR (`E11`) | C3 (Spine) | Wick 0.05–1.2 ATR beyond pool, close inside pool within 2 bars | Short formulas missing in spec; trend run-away sweeps |
| **E02** | 4-Stage Sweep Confirmation | CONFIRM | BOTH | **SHADOW** | NOT_PROVEN | 15m klines, ATR (`E11`) | C3 (cap 20) | Reclaim + retest + impulse sequence | Laggy in rapid V-reversals; unproven expectancy delta |
| **E03** | Sweep Depth Normalisation | FEATURE | BOTH | **ACTIVE** | PROMISING | 15m klines, ATR (`E11`) | C3 (Feature) | Normalised ratio `d_atr = d / ATR_14` | High volatility blowouts; division by near-zero ATR |
| **E04** | Liquidity Pool (EQH/EQL) | FEATURE | BOTH | **ACTIVE** | PROMISING | 15m swing highs/lows | C3 (Feature) | >=2 swings within 0.15 ATR threshold | Clustering threshold sensitivity; noise in chop regimes |
| **E05** | BOS and CHoCH Structure | CONFIRM | BOTH | **SHADOW** | PROMISING | 15m/1h swing pivots | C3 (cap 20) | Break of structure or change of character | Pivot lag (3 bars post-pivot); subjective swing definitions |
| **E06** | Supply / Demand Zones | CONFIRM | BOTH | **SHADOW** | SPECULATIVE | 15m klines, Volume | C3 (cap 20) | Retest of origin base consolidation zone | Zone decay rate uncalibrated; multiple overlapping zones |
| **E07** | Volume Profile POC/VAH/VAL | TARGET | BOTH | **ACTIVE** | PROMISING | 15m klines (volume at price) | C5 (Target) | Session POC/VAH/VAL as structural TP levels | Insufficient lookback window; low volume sessions |
| **E08** | Anchored VWAP | CONFIRM | BOTH | **EXPERIMENTAL** | SPECULATIVE | Klines, swing anchor | C5 (cap 10) | Price bounce from swing anchor VWAP | Anchor selection ambiguity; arbitrary reset events |
| **E09** | Poor High / Poor Low | CONFIRM | BOTH | **EXPERIMENTAL** | SPECULATIVE | 15m klines | C5 (cap 10) | Auction market theory single-tick extremes | Requires tick-level auction data; 15m kline proxy weak |
| **E10** | Fair Value Gap (FVG) | TARGET | BOTH | **SHADOW** | NOT_PROVEN | 15m klines | C5 (cap 10) | 3-bar imbalance gap fill target | High frequency of false FVG fills in trending markets |
| **E11** | ATR Realised Volatility | FEATURE | BOTH | **ACTIVE** | ESTABLISHED | 15m klines (14-period Wilder) | Risk / Sizing | ATR_bps in [4, 400]; feeds stop buffer & targets | Volatility clustering spikes; lagging in regime shifts |
| **E12** | Dynamic Stop Buffer | RISK | BOTH | **ACTIVE** | PROMISING | ATR (`E11`), Funding (`E23`) | Risk / Sizing | `buffer = alpha(pct_ATR) + 0.6·1[|funding|>=0.03%]` | Alpha percentile boundary artifacts; abrupt jump at 0.03% |
| **E13** | Liquidation Burst Z-score | CONFIRM | BOTH | **SHADOW** | NOT_PROVEN | `!forceOrder@arr` ring buffer | C1 (cap 12) | Z_liq >= 2.0 (volume burst vs 1h mean) | Binance 1000 ms rate limit = structural under-sampling |
| **E14** | Liq Cluster Proximity | CONFIRM | BOTH | **EXPERIMENTAL** | DATA_SOURCE_NOT_VERIFIED | External liq heatmap | C1 (cap 12) | Distance to estimated liq cluster < 0.5 ATR | No free external API (CoinGlass paid); unverifiable |
| **E15** | CVD Turn | CONFIRM | BOTH | **SHADOW** | PROMISING | `aggTrade` stream | C2 (cap 12) | Cumulative volume delta slope inflection | Delta divergence without price absorption = false signal |
| **E16** | Order Book Imbalance (OBI) | CONFIRM | BOTH | **SHADOW** | NOT_PROVEN | `depth20@100ms` stream | C2 (cap 12) | `(Bid - Ask) / (Bid + Ask) > threshold` | Spoofing & rapid cancellation; top-20 only (not full book) |
| **E17** | Book Density Absorption | CONFIRM | BOTH | **SHADOW** | NOT_PROVEN | `depth20@100ms`, `aggTrade` | C2 (cap 12) | High volume trade with near-zero book displacement | Double-counted in C1/C2 in legacy; needs tick precision |
| **E18** | Microprice | EXECUTION | BOTH | **REJECT** | UNSUPPORTED_FOR_HORIZON | `depth20@100ms` | None | Sub-second fair value estimate | Microsecond latency tool; irrelevant for 15m manual trading |
| **E19** | Microbar Volume Clock | EXECUTION | BOTH | **REJECT** | UNSUPPORTED_FOR_HORIZON | `aggTrade` volume slices | None | Information-clock bar construction | Severe memory overhead (state machines); zero manual edge |
| **E20** | Hawkes Trade Intensity | CONFIRM | BOTH | **SHADOW** | NOT_PROVEN | `aggTrade` timestamps | C1 (Diagnostic) | Self-exciting point process intensity spike | Parameter instability across regimes; CPU intensive |
| **E21** | OI Exhaustion Reversal | SETUP | LONG | **SHADOW** | PROMISING | `/openInterest`, 4h lows | C4 (S2 Spine) | OI flush >= 0.8% + CVD turn + Z_liq >= 2.0 | Poll latency (30s); only covers LONG; S2 collision risk |
| **E22** | Spot-Led Basis Divergence | CONFIRM | BOTH | **EXPERIMENTAL** | PROMISING | Spot trades vs Perp trades | C4 (S3 Spine) | Basis divergence >= 1.5 sigma across 3 bars | Feeds desync > 150 ms; Binance spot/perp clock offset |
| **E23** | Funding Context | RISK | BOTH | **ACTIVE** | ESTABLISHED | `/fapi/v1/premiumIndex` | C4 (Veto Input) | Current funding rate magnitude & time to settlement | 8h discrete settlement jumps; API rate limiting |
| **E24** | Mark / Index Divergence | RISK | BOTH | **ACTIVE** | ESTABLISHED | `/fapi/v1/premiumIndex` | C4 (Veto Input) | `abs(mark - index) / index <= 0.5%` | De-pegging during extreme market stress |
| **E25** | Variance Ratio Regime | REGIME | BOTH | **SHADOW** | ESTABLISHED_METHOD_NOT_CALIBRATED | Closes (15m, 1h) | C6 (Gate Only) | Lo-MacKinlay multi-lag variance ratio composite | Uncalibrated empirical quintiles; arbitrary boundaries |
| **E26** | GEX / Gamma Flip | REGIME | BOTH | **REJECT** | DATA_SOURCE_NOT_VERIFIED | Deribit options OI+IV | None | Dealer net gamma exposure sign | Dealer positioning sign is assumed (unverifiable) |
| **E27** | Session Classification | MODIFIER | BOTH | **EXPERIMENTAL** | PROMISING | Timestamp UTC | C6 (Soft Veto) | Asia / London / NY session window filters | Session overlap ambiguity; weekend liquidity distortions |
| **E28** | Signal Expiry Engine | RISK | BOTH | **ACTIVE** | ESTABLISHED | Klines, MFE, structure | Risk / Journal | `min(16, 4 + 2·vol_tier)` bars, CHoCH, MFE half-life | Missing execution fill feedback in manual trading |
| **X01** | BTC Directional Conflict | MODIFIER | BOTH | **ACTIVE_SOFT_VETO** | PROMISING | BTC 5m/15m klines | V-S01 | BTC 5m return opposing alt direction | Dual identity in registry; evaluate strictly as veto |
| **X02** | Relative Volume Gate | FILTER | BOTH | **ACTIVE** | PROMISING | 15m volume / 20-bar median | S1 Pre-filter | `rel_vol >= 0.80` mandatory for S1 setup | Low-volume holidays trigger false suppressions |
| **X03** | CoinDCX Spread/Liq Gate | FILTER | BOTH | **ACTIVE** | ESTABLISHED | CoinDCX orderbook & price | V-H12 / V-H13 | Spread <= 12/25 bps; Top-10 depth >= 20x clip | CoinDCX orderbook REST API latency (1–2s polling) |
| **X04** | Late Entry Suppression | FILTER | BOTH | **ACTIVE** | PROMISING | Live price vs Entry & TP1 | V-S10 | Progress to TP1 <= 0.35 of total distance | Delays in manual signal viewing; slippage erosion |

---

## 2. Status Breakdown & Distribution

| Status Category | Count | Edge IDs | Definition of Operational Role in V4 |
|---|---|---|---|
| **ACTIVE** | **11** | E01, E03, E04, E07, E11, E12, E23, E24, E28, X02, X03 | Fully wired into live signal pipeline; contributes to setup generation, risk geometry, or hard filtering. |
| **ACTIVE_SOFT_VETO** | **1** | X01 | Operates strictly as soft veto `V-S01` (confidence penalty / threshold increase). |
| **SHADOW** | **11** | E02, E05, E06, E10, E13, E15, E16, E17, E20, E21, E25 | Computed and journaled for telemetry/ablation; **strictly forbidden from altering active scores or gates**. |
| **EXPERIMENTAL** | **6** | E08, E09, E14, E22, E27, X04 | Under active research; requires sandbox testing or paid external data before consideration. |
| **REJECT** | **3** | E18, E19, E26 | Completely excluded from build. No code, no computation, zero runtime allocation. |
| **TOTAL** | **32** | — | — |

---

## 3. Deep Investigation: E17 Double-Counting Analysis

### 3.1 The Contradiction in Source Documents
In `EDGE_DEPENDENCY_MATRIX.md` §3 and `NEO-WILDER_V4_MASTER_RESEARCH_REPORT_BN.md` §10:
- **Cluster C1 (forced-flow):** Members listed as `E13, E14, E20, E17` (Cap: 1 slot, max 12 pts).
- **Cluster C2 (order flow):** Members listed as `E15, E16, E17` (Cap: 1 slot, max 12 pts).

### 3.2 Root Phenomenon
`E17` (Book Density Absorption) measures passive limit orders absorbing aggressive market volume. 
- In C1, the author viewed it as absorption of forced liquidations (`E13`).
- In C2, the author viewed it as absorption of aggressive directional volume delta (`E15`).

### 3.3 The Double-Counting Failure Mode
If an implementation evaluates E17 and awards points under C1 *and* under C2, a single absorption event contributes up to 24 points. This replicates the exact defect criticized in legacy `quality_score.py` (where OBI + CVD + Squeeze earned 30 points for one phenomenon).

### 3.4 Rigorous Architectural Resolution
1. **Current Isolation:** `E17` is classified as `SHADOW` (`evidence: NOT_PROVEN`). Per AGENT.md §3 and §0, shadow edges **must never award points to the active composite score**. Active score contribution is strictly **0 points**.
2. **Cluster Reassignment for Telemetry/Future Ablation:**
   - **Cluster C1 (forced-flow):** Restrict exclusively to liquidation burst and cascade events: `E13` (Z_liq), `E14` (Liq clusters), and `E20` (Hawkes intensity). Remove `E17` from C1.
   - **Cluster C2 (order flow):** Reassign `E17` strictly to C2 alongside `E15` (CVD) and `E16` (OBI).
   - **Structural Invariant:** Even if E17 is promoted in a future version, C1 and C2 have a combined ceiling: `C1 + C2 <= 24 points`.

---

## 4. Shadow and Experimental Edge Isolation Rules

To prevent data snooping, phantom score inflation, and runtime degradation:

1. **Zero Impact on Active Candidate:**
   A candidate emitted by S1 must evaluate identical entry zones, stops, targets, and net R:R regardless of whether shadow edges evaluate to `TRUE`, `FALSE`, or `ABSTAIN`.
2. **Zero Impact on Active Score:**
   The composite quality score `score_0_100` must compute exclusively from active features. Shadow edges (E02, E05, E06, E10, E13, E15, E16, E17, E20, E21, E25) must write their telemetry exclusively to the journal database (`shadow_evaluations` table) and never into the scoring accumulator.
3. **Pure Function Contract:**
   Shadow edge evaluators must conform to `evaluate(ctx) -> EdgeResult`, returning `EdgeResult.ABSTAIN` if required features are unavailable. They must never raise unhandled exceptions or block the asyncio event loop.
4. **Independent Failure Isolation:**
   If a shadow or experimental edge raises an unexpected exception or exceeds a 5 ms computation timeout, it is caught by the edge runner, logged as an error metric, and fails silently without interrupting active signal generation.

---

## 5. Ablation Support Architecture

Per `BACKTEST_PROTOCOL.md` §5, every edge must support dynamic runtime ablation without code modification:

1. **Configuration Flags:**
   `config/base.yaml` must provide an explicit boolean toggle for each edge:
   ```yaml
   edges:
     e01_sweep_reclaim: true
     e02_four_stage: false
     e05_structure: false
     e07_volume_profile: true
     # ...
   ```
2. **Backtest Ablation Matrix:**
   The backtest engine must iterate through:
   - Full active system baseline.
   - Full system minus each active edge individually (leave-one-out testing).
   - Full system plus each shadow edge individually (candidate promotion testing).
3. **Promotion Hurdle:**
   An edge is promoted to ACTIVE only if Phase 9 ablation proves:
   - Statistically significant increase in net expectancy ($p < 0.05$), OR
   - $\ge 15\%$ reduction in false positive trades with $\le 10\%$ reduction in overall trade count.
