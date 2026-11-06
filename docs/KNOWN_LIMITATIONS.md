# KNOWN_LIMITATIONS.md — NEO-WILDER V4 Deliberate Fail-Closed Boundaries

**Document Version:** 4.0.0  
**Status:** ACTIVE & ENFORCED  
**Policy:** Fail-Closed Research Compliance (No Invented Formulas)

---

## 1. Executive Statement of Architectural Invariants

Per the Phase 0 Master Source Audit and autonomous execution authorization, NEO-WILDER V4 strictly adheres to research-supported specifications. Where research formulas were omitted, asymmetric, or mathematically ambiguous, **no formulas have been invented**. Instead, all affected operational paths are explicitly disabled fail-closed.

---

## 2. Inactive & Disabled Strategy Functionality

### 2.1 Strategy S1 (`SWEEP-RECLAIM-v4`): SHORT Candidate Generation Disabled
- **Status:** **DISABLED (FAIL-CLOSED ABSTAIN)**
- **Audit Defect:** The source document `STRATEGY_SPECIFICATIONS.md` §S1 omitted the short-side sweep depth formula ($d = \text{pool} - \text{low}$ was defined for LONG only), omitted the short-side entry zone formula, and contained a sign error in the stop-loss formula ($sweep\_extreme - buffer \times ATR$).
- **Enforced Runtime Behavior:**
  - Any detected bearish sweep of Equal Highs (EQH) produces an immediate `EdgeResult.ABSTAIN`.
  - Strategy S1 emits candidate objects **exclusively for LONG setups**.
  - No short entry zone, short stop-loss, or short target calculation is computed or published.
- **Lifting Condition:** Requires formal specification and user signoff of symmetric short-side formulas.

### 2.2 Take Profit 2 (TP2) Ambiguity & Target Geometry
- **Status:** **RESTRICTED TO FULLY SPECIFIED TARGETS (TP1)**
- **Audit Defect:** `STRATEGY_SPECIFICATIONS.md` line 22 states *"TP2 = 1.618 extension of TP1"* without specifying the reference anchor (e.g. extension from Entry vs extension from Sweep Extreme).
- **Enforced Runtime Behavior:**
  - Mandatory target geometry evaluates exclusively against structural **TP1** (nearest opposing swing or Volume Profile level providing $\text{Net R:R} \ge 1.50$).
  - If a signal payload requires a secondary target and the reference anchor is unresolved, TP2 is populated as `None` or identical to TP1, avoiding fabricated extensions. If mandatory target geometry cannot be satisfied without an invented formula, the candidate generator returns `ABSTAIN`.
- **Lifting Condition:** Formal specification of the Fibonacci extension anchor point.

### 2.3 Strategy S2 (`OI-EXHAUSTION-v4`)
- **Status:** **SHADOW TELEMETRY ONLY**
- **Operational Boundary:** Evaluated for internal journal logging; strictly forbidden from emitting live Telegram signals until Phase 9 ablation testing passes. S2 is LONG-only in V4.0 per specification.

### 2.4 Strategy S3 (`BASIS-DIVERGENCE-v4`)
- **Status:** **EXPERIMENTAL / SANDBOX ONLY**
- **Operational Boundary:** Evaluated only when Binance Spot and Perp streams are connected and inter-feed clock offset is $\le 150\text{ ms}$. Does not emit live signals.

---

## 3. Data Source Limitations & Constraints

### 3.1 CoinDCX 15-Minute Candle Absence
- **Finding:** CoinDCX public candlestick REST API supports only resolutions `1`, `5`, `60`, and `1D`. There is **no 15-minute candle resolution**.
- **Consequence:** 15-minute technical setups can never be generated natively from CoinDCX.
- **Architectural Boundary:** Binance USD-M Futures is the permanent research venue. CoinDCX is strictly the manual execution validation venue.

### 3.2 CoinDCX Derivatives Context Absence
- **Finding:** CoinDCX exposes no public Open Interest or Liquidation feeds.
- **Consequence:** All derivatives context features (CVD, OI Delta, Liquidations) derive solely from Binance USD-M.

### 3.3 Binance Liquidation Stream Under-Sampling
- **Finding:** Binance `!forceOrder@arr` publishes snapshots throttled at 1 event per symbol per 1000 ms.
- **Consequence:** Total liquidation volume during rapid cascades is a lower bound. Edge `E13` ($Z_{\text{liq}}$) is restricted to `SHADOW` status.

---

## 4. Scoring & Probability Display Constraints

### 4.1 Probability Calibration Display
- **Condition:** Per `V-H34` and `AGENT.md` §0 Rule 5, unless an empirical isotonic calibration artefact (`score_v4_YYYYMMDD.json`) based on $\ge 300$ resolved out-of-sample trades exists and is $\le 90$ days old:
- **Output:** The published signal must display `"calibrated_probability": "NOT CALIBRATED"`.
- **Prohibition:** No estimated probability, percentage win-rate claim, or machine-learning confidence score may be presented to the user.

---

## 5. Summary of Compliance
All limitations documented above represent **deliberate, research-faithful risk controls**. The system guarantees zero fabricated numbers, zero unverified endpoints, and zero unproven strategy formulas in production.
