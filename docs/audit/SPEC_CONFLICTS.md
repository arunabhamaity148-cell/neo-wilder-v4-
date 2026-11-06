# SPEC_CONFLICTS.md — NEO-WILDER V4 Specification Conflict Audit

**Audit Date:** 2026-11-06  
**Auditor Role:** Chief Architect & Main Integrator  
**Audit Scope:** Rigorous identification and technical reconciliation of all contradictory, ambiguous, or incomplete specifications discovered across the research documents.

---

## 1. Conflict Summary Matrix

| # | Conflict Title | Primary Sources | Secondary / Contradicting Source | Technical Impact | Resolution Status | Approval Required? |
|---|---|---|---|---|---|---|
| 1 | **Score Scale Bug** | `scoring/quality_score.py` (0–100) | `telegram/formatter.py:106` (`/200`) | Distorts operator confidence by 50% | Freeze to 0–100 integer | **Resolved (Mandated)** |
| 2 | **Score Threshold Discrepancy** | `quality_score.py` (76) | `calibration.py` (76..86), `base.yaml` (85.0) | Non-deterministic signal emission | Config driven by calibration, default 85.0 | **Requires Signoff** |
| 3 | **Minimum Net R:R Ratio** | `guards/risk_geometry.py` (1.30) | `base.yaml` (1.50), `V-H22` (1.50) | Negative expectancy in production | Strictly enforce Net R:R >= 1.50 | **Resolved (Mandated)** |
| 4 | **Portfolio Concurrency Limits** | `guards/portfolio_risk.py` (4 trades / 6%) | `governors.py` (2 trades), `V-H26` (2 trades / 3%) | Correlation blowout & VPS strain | Strictly enforce max 2 trades / 3% risk | **Resolved (Mandated)** |
| 5 | **Transaction Cost & GST Friction** | `vetoes.py` (0.0010 flat, no GST) | `BACKTEST_PROTOCOL.md` (0.05% + 18% GST + slip) | Understates friction by ~26–35% | 4-part friction model (0.1354% base RT) | **Resolved (Needs App Audit)** |
| 6 | **Regime Taxonomies** | `strategies/router.py` (5 int states) | `regime/vr_tracker.py` (3 str states) | Type errors & invalid regime gating | 3 state dimensions -> 5 strategy regimes | **Requires Signoff** |
| 7 | **Veto Count (49 vs 50 rows vs 56)** | `VETO_REGISTRY.yaml` (49 items: 34H + 15S) | `ROADMAP.md` line 8 ("50 veto rows"), `enums.py` (56) | Confusion over missing or phantom vetoes | Reconcile 49 canonical IDs; explain 50 count | **Requires Signoff** |
| 8 | **Phantom Edge Slots in Scoring** | Legacy "Edges 1-7" claim | `strategies/edges.py` (only E1 wired; E2-5 absent) | Phantom score inflation without logic | Pure registry-driven; no phantom slots | **Resolved (Mandated)** |
| 9 | **X01 Dual Identity (Edge vs Veto)** | `EDGE_REGISTRY.yaml` (`ACTIVE_SOFT_VETO`) | `VETO_REGISTRY.yaml` (`V-S01`) | Double evaluation in edge & veto planes | Compute feature once; evaluate as `V-S01` | **Requires Signoff** |
| 10 | **E17 Double Cluster Assignment** | `EDGE_DEPENDENCY_MATRIX.md` §3 (in C1) | `EDGE_DEPENDENCY_MATRIX.md` §3 (in C2) | 24 pt double count of single phenomenon | Restrict E17 to C2 only; C1 = liq burst | **Requires Signoff** |
| 11 | **CoinDCX Validation Pipeline Order** | `VETO_REGISTRY.yaml` (V-H31/32 at step 8) | `BN` report §4 & §12 (before risk geometry) | Redundant R:R math on untradable drift | Move execution validation before net R:R | **Requires Signoff** |
| 12 | **Telegram Formatter Duplication** | `telegram/formatter.py` (8,312 B) | `adapters/telegram/formatter.py` (8,312 B) | Dead code & import collision | Single publisher in `src/neo_wilder/publish/` | **Resolved (Mandated)** |
| 13 | **Dual Process vs Single Process** | Legacy `ARCHITECTURE.md` (SHM dual daemon) | `AGENT.md` §5 & `BLUEPRINT.md` (1 process) | VPS OOM crash (>300 MB RSS) | Single asyncio process + SQLite WAL | **Resolved (Mandated)** |
| 14 | **Missing Short-Side S1 Formulas** | `STRATEGY_SPECIFICATIONS.md` S1 (LONG only) | `BN` report §6 (mentions `∓`) | Agents guess math; invalid shorts | Formalize symmetric short-side formulas | **CRITICAL BLOCKER** |

---

## 2. Exhaustive Conflict Analysis

### Conflict 1: Score Scale Bug (100 vs /200)
- **Source 1:** `LEGACY_EDGE_VETO_INVENTORY.md` §0 & §3.3; `scoring/quality_score.py` (kernel sum capped at 100).
- **Source 2:** Legacy `telegram/formatter.py:106` (`format_signal` printed `Score: {score}/200`).
- **Technical Impact:** If a signal achieved a score of 82/100, the Telegram alert printed `82/200` (41%), confusing the manual operator into skipping high-quality setups.
- **Proposed Resolution:** The V4 score engine strictly outputs an integer in `[0, 100]`. Schema in `COINDCX_MANUAL_EXECUTION_SPEC.md` §3 enforces `score_0_100`. The Telegram formatter must display `{score_0_100}/100`.
- **Approval Status:** **APPROVED / MANDATED** (Core requirement of V4).

---

### Conflict 2: Score Threshold Discrepancy (76 vs 76..86 vs 85.0)
- **Source 1:** Legacy `quality_score.SCORE_THRESHOLD = 76`.
- **Source 2:** Legacy `calibration.MIN_SCORE_CUTOFF = 76`, `MAX_SCORE_CUTOFF = 86`.
- **Source 3:** Legacy `config/base.yaml` `scoring.publish_threshold = 85.0`.
- **Technical Impact:** Candidates scoring 78 would pass edge scoring but get suppressed at publisher configuration, causing phantom drops and silent failures.
- **Proposed Resolution:** In V4, no threshold is hardcoded in Python code. `config/base.yaml` and `config/thresholds.yaml` govern publication. Until empirical walk-forward calibration is completed on >= 300 resolved trades, the default threshold is set to **85.0**. Any signal with `score < 85` triggers soft veto `V-S15` (`SCORE_BELOW_PUBLISH`).
- **Approval Status:** **REQUIRES ARCHITECT/USER CONFIRMATION** to lock 85.0 as the Phase 1 default threshold.

---

### Conflict 3: Minimum Net R:R Ratio (1.30 vs 1.50)
- **Source 1:** Legacy `guards/vetoes.py:30` (`MIN_NET_RR_RATIO = 1.30`).
- **Source 2:** `config/base.yaml` (`guards.min_r_multiple = 1.50`), `VETO_REGISTRY.yaml` (`V-H22`: `net R:R after fees+slip+funding < 1.50`), `STRATEGY_SPECIFICATIONS.md` line 4 (`minimum net R:R 1.50`).
- **Technical Impact:** A 1.30 net R:R leaves virtually zero statistical edge after CoinDCX real-world execution delay (20–120s manual entry delay) and slippage.
- **Proposed Resolution:** Hard veto `V-H22` strictly enforces `net_rr >= 1.50`. Any candidate with `net_rr < 1.50` is blocked fail-closed.
- **Approval Status:** **APPROVED / MANDATED**.

---

### Conflict 4: Portfolio Concurrency Limits (4 trades / 6% vs 2 trades / 3%)
- **Source 1:** Legacy `guards/portfolio_risk.py:22` (`max_concurrent_trades = 4`, max open risk = 6.0%).
- **Source 2:** Legacy `guards/governors.py:18` (`ClusterHeatGovernor(max_concurrent=2)`), `VETO_REGISTRY.yaml::V-H26` (`concurrent >= 2 or open risk > 3.0%`).
- **Technical Impact:** On 8 crypto symbols, running 4 concurrent trades creates severe directional correlation during market-wide BTC flushes, violating the 1 GB VPS risk boundary.
- **Proposed Resolution:** Hard veto `V-H26` enforces:
  - `concurrent_trades < 2` (maximum 1 active trade; a 2nd candidate is blocked).
  - `total_open_risk <= 3.0%` of account equity.
- **Approval Status:** **APPROVED / MANDATED**.

---

### Conflict 5: Transaction Cost and GST Friction Model
- **Source 1:** Legacy `guards/vetoes.py:30` (`ROUND_TRIP_FEE_PCT = 0.0010`, i.e. 0.10% flat, zero GST, zero dynamic slippage).
- **Source 2:** `BACKTEST_PROTOCOL.md` §2, `RESEARCH_REFERENCES.md` §B.5, `COINDCX_MANUAL_EXECUTION_SPEC.md`: CoinDCX Taker fee 0.050% per side, +18% Indian GST = 0.059% per side (0.118% round-trip), plus dynamic slippage `0.5*spread_bps + 0.3*ATR_bps/100` (floor 1.0 bp), plus 8h funding rate. Total estimated base round-trip friction = **0.1354%**.
- **Technical Impact:** Legacy understated execution friction by >35%. Strategies that appeared profitable in legacy backtests were deeply negative after GST and slippage.
- **Proposed Resolution:** Adopt the complete 4-factor friction model in `BACKTEST_PROTOCOL.md` §2 for both backtesting and live candidate net R:R calculation.
- **Approval Status:** **APPROVED / MANDATED** (With note: User must re-verify Global Futures fee schedule in CoinDCX app prior to live deployment).

---

### Conflict 6: Market Regime Taxonomies
- **Source 1:** Legacy `strategies/router.py:34` (5 integer states: `0: TRENDING_UP`, `1: TRENDING_DOWN`, `2: RANGING`, `3: BREAKOUT`, `4: HIGH_VOLATILITY`).
- **Source 2:** Legacy `regime/vr_tracker.py` (3 string states: `'MEAN_REVERTING'`, `'RANDOM_WALK'`, `'TRENDING'`).
- **Source 3:** `STRATEGY_SPECIFICATIONS.md` §Regime eligibility table:
  1. `MEAN_REVERSION / ROTATIONAL`
  2. `NEUTRAL`
  3. `MOMENTUM_TREND`
  4. `NOISE_CHOP`
  5. `LIQUIDITY_STRESS`
- **Technical Impact:** Incompatible state representations lead to runtime exceptions or uncontrolled signal generation in prohibited regimes like `NOISE_CHOP`.
- **Proposed Resolution:** Standardize on the 3 continuous state variables defined in `NEO-WILDER_V4_MASTER_RESEARCH_REPORT_BN.md` §11:
  1. `vr_state`: Lo-MacKinlay Variance Ratio composite (Mean-Reverting vs Random Walk vs Trending).
  2. `vol_state`: ATR bps percentile (`LOW`, `NORMAL`, `HIGH`, `EXTREME`).
  3. `liquidity_stress`: Boolean flag (`spread > threshold` or `atr_bps > 400`).
  These 3 continuous variables deterministically map to the 5 eligibility categories in `STRATEGY_SPECIFICATIONS.md`.
- **Approval Status:** **REQUIRES ARCHITECT SIGNOFF** on enum definitions.

---

### Conflict 7: Veto Count Discrepancy (49 IDs vs "50 Veto Rows" vs 56 Legacy Enum)
- **Source 1:** `VETO_REGISTRY.yaml` lines 16–50 define exactly **34 Hard Vetoes** (`V-H01`..`V-H34`). Lines 51–66 define exactly **15 Soft Vetoes** (`V-S01`..`V-S15`). Total = **49 IDs**.
- **Source 2:** `IMPLEMENTATION_ROADMAP.md` line 8 states: *"Verification: 201 files listed, 32 edge rows, 50 veto rows, 10 integrity defects."*
- **Source 3:** Legacy `domain/enums.py::HardVetoReason` contains **56** enum members.
- **Root Cause Analysis:**
  1. Line 50 of `VETO_REGISTRY.yaml` is the final row of the `hard_vetoes` section (`V-H34`). A mechanical line/row count of that block or a draft table that included a summary/header row resulted in the text string "50 veto rows".
  2. `EDGE_REGISTRY.yaml` line 36 introduces `X01` (BTC Directional Conflict) with `status: ACTIVE_SOFT_VETO`. If `X01` was counted as a veto entry alongside the 49 rows in `VETO_REGISTRY.yaml`, the sum is 49 + 1 = 50 rows.
  3. The legacy 56-member `HardVetoReason` enum contained many redundant and unimplemented members (e.g. orphan vetoes, duplicate memory checks, and un-wired guards). V4 consolidated these into 34 hard vetoes and 15 soft vetoes.
- **Proposed Resolution:**
  - Officially freeze the V4 veto catalog at **49 unique IDs** (34 Hard: `V-H01`–`V-H34`, 15 Soft: `V-S01`–`V-S15`).
  - Declare `X01` in `EDGE_REGISTRY.yaml` to be an edge alias pointing to Soft Veto `V-S01`.
  - Document that the "50 veto rows" phrase in `IMPLEMENTATION_ROADMAP.md` was an off-by-one counting artifact and not a missing 50th veto ID.
- **Approval Status:** **REQUIRES ARCHITECT/USER CONFIRMATION**.

---

### Conflict 8: Edge Implementation Gaps and Phantom Scoring Slots
- **Source 1:** Legacy documentation claimed "Edges 1 to 7".
- **Source 2:** Legacy code inspection revealed only `EDGE_1` (`sweep_reclaim_v1.py`), `EDGE_6`, and `EDGE_7` (`advanced_edges.py`) had evaluators. `EDGE_2` through `EDGE_5` were never coded.
- **Source 3:** `scoring/quality_score.py` allocated 10 points each to phantom slots `idea2_oi_cvd_score`, `idea3`, `idea4`, and `idea5_squeeze_score`.
- **Technical Impact:** Legacy scored non-existent signals and produced inflated quality scores.
- **Proposed Resolution:** In V4, all edges are governed strictly by `EDGE_REGISTRY.yaml`. Only active edges produce features for active strategies. Phantom scoring slots are completely eliminated.
- **Approval Status:** **APPROVED / MANDATED**.

---

### Conflict 9: X01 Dual Nature (Edge vs Soft Veto)
- **Source 1:** `EDGE_REGISTRY.yaml` defines `X01` (`BTC Directional Conflict`) with `archetype: MODIFIER`, `status: ACTIVE_SOFT_VETO`.
- **Source 2:** `VETO_REGISTRY.yaml` defines `V-S01` (`BTC_DIRECTIONAL_CONFLICT`, effect: `conf -15, threshold +5`, escalates to hard if `BTC 5m < -1.0%`).
- **Technical Impact:** If Agent B implements X01 as an edge module and Agent D implements V-S01 as a veto module, the same BTC return calculation is duplicated and could apply penalties twice.
- **Proposed Resolution:**
  - `src/neo_wilder/features/btc_context.py` computes the BTC 5m return and directional bias as a pure feature.
  - No standalone `edges/x01_btc.py` score-adding module is built.
  - `src/neo_wilder/vetoes/soft.py` evaluates `V-S01` using the BTC feature.
  - In `EDGE_REGISTRY.yaml`, `X01` is annotated as `REFER_TO_VETO_V_S01`.
- **Approval Status:** **REQUIRES ARCHITECT SIGNOFF**.

---

### Conflict 10: E17 Double Cluster Assignment (C1 vs C2)
- **Source 1:** `EDGE_DEPENDENCY_MATRIX.md` §3 lists `E17` (Book density / absorption) as a member of **Cluster C1 (forced-flow)** with a 12-point cap.
- **Source 2:** `EDGE_DEPENDENCY_MATRIX.md` §3 also lists `E17` as a member of **Cluster C2 (order flow)** with a 12-point cap.
- **Source 3:** `NEO-WILDER_V4_MASTER_RESEARCH_REPORT_BN.md` §10 confirms this dual listing.
- **Technical Impact:** If E17 were active and scored in both clusters, a single book absorption event would receive up to 24 points (12 from C1 + 12 from C2), directly violating the anti-double-counting principle.
- **Proposed Resolution:**
  1. `E17` is currently classified as `SHADOW` (`evidence: NOT_PROVEN`). Per AGENT.md, shadow edges **must never award points to the active composite score**.
  2. For shadow telemetry and future ablation, `E17` is assigned strictly to **Cluster C2 (order flow)** alongside CVD (`E15`) and OBI (`E16`).
  3. Cluster C1 (forced-flow) is restricted exclusively to liquidation events: Z_liq burst (`E13`), Liquidation clusters (`E14`), and Hawkes intensity (`E20`).
- **Approval Status:** **REQUIRES ARCHITECT SIGNOFF**.

---

### Conflict 11: CoinDCX Validation Order in Veto Pipeline
- **Source 1:** `VETO_REGISTRY.yaml` lines 3–14 specifies the processing order:
  - Step 6: `risk_geometry` (`V-H19`..`V-H23`)
  - Step 8: `execution_validation` (`V-H31`, `V-H32`)
- **Source 2:** `NEO-WILDER_V4_MASTER_RESEARCH_REPORT_BN.md` §4 & §12 explicitly states:
  > *"আপনার প্রস্তাবিত ক্রমে execution validation শেষে ছিল; V4-এ এটি risk geometry-র আগে আনা হয়েছে, কারণ CoinDCX-এ drift/স্প্রেড খারাপ হলে R:R পুনর্গণনারই প্রয়োজন নেই — সেটি অপ্রাসঙ্গিক সিগন্যাল ব্লক করার পরে হিসাব করার অপচয়।"*
- **Source 3:** `COINDCX_MANUAL_EXECUTION_SPEC.md` §4 lists the publication gate order as: No hard veto -> Net R:R >= 1.50 -> CoinDCX price present -> Spread -> Depth -> Late entry.
- **Technical Impact:** Net R:R calculation (`V-H22`) requires the CoinDCX execution price and CoinDCX spread to compute slippage and net reward. If risk geometry runs before CoinDCX validation, it either uses the Binance reference price (inaccurate) or fails if CoinDCX data is missing.
- **Proposed Resolution:** Align the pipeline execution sequence:
  1. Data integrity (`V-H01`..`V-H04`)
  2. Infra health (`V-H05`..`V-H11`)
  3. Market safety (`V-H12`..`V-H14`)
  4. Event & derivatives risk (`V-H15`..`V-H18`, `V-H33`)
  5. **CoinDCX Execution Validation** (`V-H31`, `V-H32` drift check, CoinDCX spread/depth)
  6. **Risk Geometry & Net R:R** (`V-H19`..`V-H23` using actual CoinDCX validated price and slippage)
  7. Exposure & exhaustion (`V-H26`..`V-H30`)
  8. Dedupe & cooldown (`V-H24`, `V-H25`, `V-H34`)
  9. Soft modifiers (`V-S01`..`V-S15`)
- **Approval Status:** **REQUIRES ARCHITECT SIGNOFF**.

---

### Conflict 12: Telegram Formatter Duplication
- **Source 1:** Legacy `telegram/formatter.py` (8,312 bytes).
- **Source 2:** Legacy `adapters/telegram/formatter.py` (8,312 bytes).
- **Technical Impact:** Duplicate maintenance, divergent bug fixes, and broken imports (the adapter directory lacked a `publisher.py`).
- **Proposed Resolution:** Single canonical implementation under `src/neo_wilder/publish/telegram.py` consuming an immutable `Signal` dataclass from `src/neo_wilder/publish/schema.py`.
- **Approval Status:** **APPROVED / MANDATED**.

---

### Conflict 13: Single Process Monolith vs Dual Process SHM Bridge
- **Source 1:** Legacy `docs/ARCHITECTURE.md` specified a 128-byte shared-memory (SHM) IPC bridge between a hot execution daemon and a cold research daemon.
- **Source 2:** `AGENT.md` §5, `FINAL_FOLDER_STRUCTURE.md` line 81, and `BLUEPRINT.md` mandate a single asyncio process within a 220 MB RAM budget on a 1 GB / 2 vCPU VPS.
- **Technical Impact:** Dual processes double baseline runtime memory to ~400 MB+, triggering kernel OOM killer and VPS thrashing, with zero signal precision gain for 15-minute manual execution.
- **Proposed Resolution:** Complete rejection of dual daemon and SHM bridge. NEO-WILDER V4 runs strictly as a single asyncio process.
- **Approval Status:** **APPROVED / MANDATED**.

---

### Conflict 14: Missing Short-Side Formulas in Strategy Specifications (CRITICAL)
- **Source 1:** `STRATEGY_SPECIFICATIONS.md` §S1 lines 10–25 provides explicit mathematical definitions for LONG setups, but leaves SHORT setups incomplete or mathematically broken:
  - Line 12: `d = (pool - low)` where `0.05 ATR <= d <= 1.2 ATR`. For SHORT, low is below the pool; a short sweep occurs above the pool (`high - pool`).
  - Line 17: `Entry zone = [min(close_reclaim, pool), close_reclaim] for LONG`. SHORT entry zone is completely unstated.
  - Line 20: `Stop — sweep_extreme - buffer * ATR`. For SHORT, subtracting buffer from the high places the stop loss *inside* or *below* the entry! (Bengali report line 137 noted `sweep_extreme ∓ buffer·ATR`).
  - Line 22: `TP2 = 1.618 extension of TP1`. The reference baseline (Entry vs Sweep Extreme vs Opposing Swing) for the 1.618 extension is unspecified.
- **Technical Impact:** Coding Agent C cannot write deterministic S1 short code without guessing or inventing formulas, directly violating AGENT.md.
- **Proposed Resolution (Submitted for User/Architect Approval):**
  1. **Short Sweep Depth:** `d_short = high - pool`, requiring `0.05 ATR <= d_short <= 1.2 ATR`.
  2. **Short Reclaim:** 15m bar wicks above pool, closes back below pool (`close < pool`), confirmed within 2 bars.
  3. **Short Entry Zone:** `[close_reclaim, max(close_reclaim, pool)]`, widened to minimum width `max(0.20%, 0.05 ATR)`. Reference price = `close_reclaim`.
  4. **Short Stop Loss:** `sweep_extreme + buffer * ATR` (where `sweep_extreme` is the sweep wick high).
  5. **Short TP1:** Nearest opposing swing low or VAL (Value Area Low) that provides `net_rr >= 1.50`.
  6. **TP2 Extension Formula:** `TP2 = Entry ∓ 1.618 * abs(TP1 - Entry)` (directional extension from Entry through TP1).
- **Approval Status:** **CRITICAL BLOCKER — REQUIRES EXPLICIT USER SIGNOFF BEFORE PHASE 1**.
