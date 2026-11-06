# STRATEGY_AUDIT.md — NEO-WILDER V4 Strategy Specifications Audit

**Audit Date:** 2026-11-06  
**Auditor Role:** Chief Architect & Main Integrator  
**Audit Scope:** Rigorous rule breakdown of S1, S2, and S3, identification of formula omissions, mathematical asymmetries, regime constraints, and collision rules.

---

## 1. Strategy Overview Matrix

| Strategy ID | Name | Role in V4 | Direction | Setup TF / Context TF | Status | Evidence Classification |
|---|---|---|---|---|---|---|
| **S1** | `SWEEP-RECLAIM-v4` | Core Active Spine | LONG & SHORT | 15m closed bars / 1h & 4h context | **ACTIVE** | PROMISING |
| **S2** | `OI-EXHAUSTION-v4` | Liquidation Flush Setup | LONG Only (v4.0) | 15m closed bars / 1h & 4h context | **SHADOW** | PROMISING |
| **S3** | `BASIS-DIVERGENCE-v4` | Spot/Perp Lead Divergence | LONG & SHORT | 15m closed bars / 1h context | **EXPERIMENTAL** | PROMISING |

---

## 2. Strategy S1 — SWEEP-RECLAIM-v4 (Active Spine)

S1 is the primary candidate generator of NEO-WILDER V4. It identifies false breakouts (liquidity sweeps) beyond established swing pools followed by immediate reclaims.

### 2.1 Setup & Trigger Rules

1. **Liquidity Pool Identification (`E04`):**
   - Must identify an Equal High (EQH) or Equal Low (EQL) pool consisting of $\ge 2$ swing pivots within $0.15 \times \text{ATR}_{14}$ of each other at or beyond the current swing extreme.
2. **Sweep Depth Requirement (`E01`):**
   - A single 15m candle must wick beyond the liquidity pool boundary.
   - Sweep depth $d$ must satisfy:
     $$0.05 \times \text{ATR}_{14} \le d \le 1.20 \times \text{ATR}_{14}$$
   - *Source Formula (LONG):* $d_{\text{long}} = \text{pool\_level} - \text{bar\_low}$.
   - *Source Formula (SHORT):* **OMITTED IN SOURCE TEXT** (Identified in §5 below).
3. **Reclaim Requirement:**
   - The same sweeping 15m candle must close back inside the pool:
     - LONG: $\text{bar\_close} > \text{pool\_level}$
     - SHORT: $\text{bar\_close} < \text{pool\_level}$
4. **Reclaim Confirmation Window:**
   - Reclaim must be confirmed within a maximum of 2 bars following the sweep bar.
5. **Confirmation Requirements (At least 1 mandatory):**
   - **Market Structure Shift (`E05`):** Minor BOS or CHoCH in trade direction.
   - **Displacement Body:** Sweeping bar real body $> 0.60 \times \text{ATR}_{14}$ in reclaim direction.
   - **Volume Spike (`X02`):** Sweeping bar volume $> 1.20 \times \text{median}(\text{volume}_{20})$.

### 2.2 Entry, Stop Loss, and Take Profit Geometry

1. **Entry Zone:**
   - LONG Entry Zone: $[\min(\text{close}_{\text{reclaim}}, \text{pool}), \text{close}_{\text{reclaim}}]$.
   - SHORT Entry Zone: **OMITTED IN SOURCE TEXT** (Identified in §5 below).
   - Minimum Zone Width: Widened to $\max(0.20\%, 0.05 \times \text{ATR}_{14})$ to accommodate manual execution delay.
   - Reference Price: Strictly the `close` of the reclaim bar (never the live price).
2. **Stop Loss Geometry (`E12`):**
   - Stop Price Formula:
     $$\text{Stop}_{\text{long}} = \text{sweep\_extreme} - (\text{buffer} \times \text{ATR}_{14})$$
     $$\text{Stop}_{\text{short}} = \text{sweep\_extreme} + (\text{buffer} \times \text{ATR}_{14})$$
   - Dynamic Buffer Multiplier:
     $$\text{buffer} = \alpha(\text{pct\_ATR}) + 0.60 \times \mathbb{I}_{[|\text{funding}| \ge 0.03\%]}$$
     where $\alpha \in \{1.5, 2.2, 3.0\}$ determined by the 30th and 80th percentiles of the trailing 100 ATR values (legacy E12).
   - Hard Veto Bounds (`V-H20`): $\text{SL}_{\text{dist}} \ge \max(0.65\%, 0.50 \times \text{ATR}_{14})$ and $\text{SL}_{\text{dist}} \le 4.50 \times \text{ATR}_{14}$.
3. **Take Profit Levels:**
   - **TP1:** Nearest opposing swing pivot or Volume Profile level (VAL/VAH, `E07`) that provides $\text{Net R:R} \ge 1.50$.
   - **TP2:** $1.618 \times \text{extension}$ of the entry-to-TP1 move.
   - **Tautology Elimination:** Legacy permitted a fallback target manufactured from $2.0 \times \text{ATR}$. V4 explicitly bans this fallback: **if no structural level exists with $\ge 1.50$ Net R:R, the candidate is NOT emitted**.

### 2.3 Expiry & Invalidation Mechanics

1. **Time Expiry (`E28`):** $\min(16, 4 + 2 \times \text{vol\_tier})$ bars on 15m (maximum 4 hours).
2. **Structural Invalidation:** Any 15m close that breaks market structure in the opposite direction (CHoCH) immediately invalidates the signal.
3. **MFE Half-Life Invalidation:** If price achieves $> 50\%$ progress toward TP1 and then retraces back beyond the entry reference price, the signal expires immediately.

---

## 3. Strategy S2 — OI-EXHAUSTION-v4 (Shadow Engine)

S2 identifies forced unwinding of crowded positioning near multi-hour extremes.

### 3.1 Setup Conditions (All Mandatory)
1. **Direction:** **LONG ONLY** in V4.0 (short-side OI unwinds behave asymmetrically during structural bull regimes).
2. **Positioning Context (`E21`):** Price at or below 4-hour swing lows with an Open Interest contraction $\ge 0.80\%$ over the trailing 15-minute window.
3. **Order Flow Turn (`E15`):** Cumulative Volume Delta (CVD) inflection from aggressive selling to aggressive buying on the 1m/5m timeframe.
4. **Liquidation Burst (`E13`):** Mandatory liquidation burst with $Z_{\text{liq}} \ge 2.0$ over trailing 1-hour mean liquidation volume.

### 3.2 Risk Geometry & Collision Lock
- **Stop Loss:** $\text{flush\_low} - 1.0 \times \text{ATR}_{14}$.
- **Target:** Prior 1-hour swing high; requires $\text{Net R:R} \ge 1.50$.
- **Collision Rule:** S2 **cannot fire within 30 minutes of an S1 signal** on the same symbol to prevent redundant duplicate alerts on the same liquidation event.
- **Status:** **SHADOW ONLY**. Does not publish to live channels until Phase 9 ablation proves statistical significance.

---

## 4. Strategy S3 — BASIS-DIVERGENCE-v4 (Experimental Engine)

S3 detects divergences where Binance spot trades lead perpetual futures trades during dislocation events.

### 4.1 Setup Conditions
1. **Basis Divergence (`E22`):** Perp price minus spot index price normalized as a z-score:
   $$|Z_{\text{basis}}| \ge 1.50\sigma$$
   (tightened from legacy $\pm 0.5\sigma$).
2. **Persistence Requirement:** The basis divergence must persist across **3 consecutive closed 15m bars** of identical sign.
3. **Clock Synchronization Pre-condition:** Requires synchronized Binance spot and perp streams. If the measured inter-feed timestamp clock offset exceeds **150 ms**, the strategy **abstains** fail-closed.
4. **Status:** **EXPERIMENTAL ONLY**.

---

## 5. Audit of Missing, Incomplete, and Asymmetric Formulas

> [!CAUTION]
> **SOURCE AUDIT FINDING — INVENTED FORMULAS ARE FORBIDDEN:**  
> The following formulas are absent or mathematically incorrect in `STRATEGY_SPECIFICATIONS.md`. Per `AGENT.md` §0 Rule 5 and the user prompt, **the Chief Architect cannot invent missing formulas**. These must be formally reviewed and signed off by the User before Agent C writes strategy code.

### 5.1 Omission 1: Short-Side Sweep Depth Formula
- **Source Text (`STRATEGY_SPECIFICATIONS.md` line 12):**
  > *"A 15m bar wicks beyond the pool by $d = (pool - low)$ where $0.05\text{ ATR} \le d \le 1.2\text{ ATR}$."*
- **Defect:** For a SHORT sweep, price wicks *above* an EQH pool. $pool - low$ would be positive and meaningless.
- **Architect Recommendation (Needs Approval):**
  $$d_{\text{short}} = \text{bar\_high} - \text{pool\_level}$$
  requiring $0.05 \times \text{ATR}_{14} \le d_{\text{short}} \le 1.20 \times \text{ATR}_{14}$.

### 5.2 Omission 2: Short-Side Entry Zone Formula
- **Source Text (`STRATEGY_SPECIFICATIONS.md` line 17):**
  > *"Entry zone = $[\min(close\_reclaim, pool), close\_reclaim]$ for LONG, widened to a minimum width of $\max(0.20\%, 0.05\text{ ATR})$."*
- **Defect:** The short-side entry zone is completely unwritten. For SHORT, $close\_reclaim < pool$.
- **Architect Recommendation (Needs Approval):**
  $$\text{Entry\_Zone}_{\text{short}} = [close\_reclaim, \max(close\_reclaim, pool)]$$
  widened upwards to maintain minimum width $\max(0.20\%, 0.05 \times \text{ATR}_{14})$.

### 5.3 Omission 3: Short-Side Stop Loss Formula Sign Error
- **Source Text (`STRATEGY_SPECIFICATIONS.md` line 20):**
  > *"Stop — $sweep\_extreme - buffer * ATR$..."*
- **Defect:** Subtracting buffer from the high extreme for a short trade places the stop loss *below* entry price. (Note: `NEO-WILDER_V4_MASTER_RESEARCH_REPORT_BN.md` line 137 correctly used $sweep\_extreme \mp buffer \cdot ATR$, but the English spec contained the subtraction bug).
- **Architect Recommendation (Needs Approval):**
  $$\text{Stop}_{\text{short}} = \text{sweep\_extreme\_high} + (\text{buffer} \times \text{ATR}_{14})$$

### 5.4 Ambiguity 4: TP2 1.618 Fibonacci Extension Reference Anchor
- **Source Text (`STRATEGY_SPECIFICATIONS.md` line 22):**
  > *"TP2 = 1.618 extension of TP1."*
- **Defect:** A Fibonacci extension requires an origin anchor and an impulse anchor. The text does not state whether the 1.618 multiplier applies to:
  - Option A: $\text{Entry} \pm 1.618 \times |\text{TP1} - \text{Entry}|$ (Extension from Entry through TP1).
  - Option B: $\text{Sweep\_Extreme} \pm 1.618 \times |\text{TP1} - \text{Sweep\_Extreme}|$ (Extension from Extreme).
- **Architect Recommendation (Needs Approval):** Adopt Option A:
  $$\text{TP2} = \text{Reference\_Price} \pm 1.618 \times |\text{TP1} - \text{Reference\_Price}|$$

---

## 6. Regime Eligibility Matrix

| Regime Identifier (E25 / VR Composite) | S1 (Sweep-Reclaim) | S2 (OI-Exhaustion) | S3 (Basis-Divergence) | Action on Candidate |
|---|---|---|---|---|
| **`MEAN_REVERSION / ROTATIONAL`** | **ON** | **ON** | **OFF** | Emits normally |
| **`NEUTRAL`** | **ON** | **OFF** | **ON** | Emits normally |
| **`MOMENTUM_TREND`** | **ON** (with `V-S13` penalty) | **ON** | **ON** | Conf -12 applied; must counter-trend filter |
| **`NOISE_CHOP`** | **OFF** | **OFF** | **OFF** | **Hard Veto `V-H33` Blocks All** |
| **`LIQUIDITY_STRESS`** | **OFF** | **OFF** | **OFF** | **Hard Veto `V-H33` / `V-H12` Blocks All** |

---

## 7. Rejected Strategy Families (Explicit Non-Goals)

| Strategy Family | Architectural Decision | Empirical & Operational Rationale |
|---|---|---|
| **Session Sweep Standalone Engine** | **NOT BUILT** | Session effects are modeled as soft modifiers (`E27`); building a separate engine duplicates state without proven edge. |
| **Trend Pullback Continuation** | **NOT BUILT** | Requires a validated trend regime classifier. `E25` is not yet calibrated on OOS data. |
| **Pure Mean-Reversion Reversal** | **NOT BUILT** | No legacy implementation; lacks distinct microstructure confirmation features. |
| **Funding/OI Crowding Reversal** | **NOT BUILT** | 8h funding rate cadence provides $<10$ events/month per symbol, statistically under-powered for 2-year backtesting. |
| **Standalone Liquidation Flush Engine** | **FOLDED INTO S2** | Running a separate liquidation engine would double-count Cluster C1 forced-flow alongside S2. |
