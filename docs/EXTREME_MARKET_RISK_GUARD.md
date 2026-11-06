# EXTREME_MARKET_RISK_GUARD.md — Bidirectional Institutional Safety Layer

**System:** NEO-WILDER V4  
**Classification:** Protective Safety Layer (NOT a Trading Strategy)  
**Status:** Frozen & Implemented  
**Date:** 2026-11-06

---

## 1. Architectural Mandate & Non-Strategy Nature

The **EXTREME_MARKET_RISK_GUARD** is a multi-dimensional, causal risk interception subsystem designed to protect capital from structural anomalies, liquidity vacuums, derivative crowding, and violent liquidation cascades.

### Strict Governance Rules:
- **Safety Layer Only:** This module emits zero candidate trade setups. It acts solely as an interceptor within the fail-closed veto pipeline.
- **Fail-Closed Missing Data Policy:** Any critical missing or stale data (OI outage $> 10\text{ min}$, funding snapshot absent, orderbook stale $> 3\text{s}$) triggers immediate `ABSTAIN` / hard veto block (`V-H11` or `V-H06`).
- **Zero Score Influence:** Hard vetoes triggered by this guard **can NEVER be overridden** by any composite score, probability calibration, operator flag, or machine learning model.
- **Preservation of Registry Statuses:** Shadow edges (`E13`, `E15`, `E16`, `E17`, `E21`) and Experimental edges (`E14`, `E22`) remain strictly isolated; they contribute **zero points** to the active composite score.
- **SHORT Strategy Blocker Preserved:** S1 SHORT setups remain strictly disabled (`ABSTAIN`) pursuant to the Phase 0 audit finding. The guard audits SHORT danger symmetrically to provide complete bidirectional protection for future verified short spines.

---

## 2. The Six Audited Risk Conditions

```
                                    ┌───────────────────────────────────────────────┐
                                    │         EXTREME MARKET RISK GUARD             │
                                    └──────────────────────┬────────────────────────┘
                                                           │
          ┌─────────────────┬─────────────────┬────────────┴────┬─────────────────┬─────────────────┐
          ▼                 ▼                 ▼                 ▼                 ▼                 ▼
   1. OI & Price     2. Funding        3. CVD Spot/Perp   4. Liquidation    5. Orderbook      6. Structural
     Divergence       Overheating        Divergence          Cascade        Liquidity Void      Exhaustion
    (E21 SHADOW)     (E23 ACTIVE)       (E15 SHADOW,       (E13 SHADOW,      (X03 ACTIVE,      (E01 ACTIVE,
                                       E22 EXPERIMENTAL)  E14 EXPERIMENTAL) E16/17 SHADOW)    Tested RSI)
```

### 1. OI and Price Divergence (E21 SHADOW)
- **Data Source:** Binance USD-M `/fapi/v1/openInterest` and rolling open interest history.
- **Causal Metric:**
  $$\Delta \text{OI} = \frac{\text{OI}_t - \text{OI}_{t-k}}{\text{OI}_{t-k}}, \quad \Delta P = \frac{P_t - P_{t-k}}{P_{t-k}}$$
- **Risk Invariants:**
  - **Rapid Contraction:** If $\Delta \text{OI} < -5.0\%$ within a rolling window, severe forced position liquidation/deleveraging is in progress. Increases volatility cascade risk $\rightarrow$ triggers `V-S05` / risk flag.
  - **Directional Traps:**
    - *LONG Danger:* $\Delta P < -1.0\%$ accompanied by $\Delta \text{OI} > +3.0\%$. Indicates aggressive short positioning or trapped long accumulation catching a falling knife.
    - *SHORT Danger:* $\Delta P > +1.0\%$ accompanied by $\Delta \text{OI} > +3.0\%$. Indicates aggressive long positioning or short squeeze acceleration.
  - **Registry Status:** E21 remains SHADOW; zero score contribution.

### 2. Funding Overheating (E23 ACTIVE)
- **Data Source:** Binance `/fapi/v1/premiumIndex` (`FundingSnapshot`).
- **Causal Metric:** 8-hour funding rate $F$ and countdown to next settlement $T_{\text{settle}}$.
- **Risk Invariants:**
  - **Settlement Window Gate (`V-H17`):** If $T_{\text{settle}} \in [-5\text{m}, +15\text{m}]$ of 8-hour settlement, signal publication is blocked by hard veto.
  - **Positive Funding Crowding ($F > +0.05\%$):** Evaluated strictly as **LONG-side risk**. Longs are paying extreme funding ($> 54\%\text{ APR}$) to shorts; crowding risk triggers `V-S04` escalation to Hard Veto for LONG candidates.
  - **Negative Funding Crowding ($F < -0.05\%$):** Evaluated strictly as **SHORT-side risk**. Shorts are paying extreme funding to longs; short squeeze crowding risk triggers `V-S04` escalation to Hard Veto for SHORT candidates.
  - **Mark-Index Divergence Gate (`V-H18`):** $|P_{\text{mark}} - P_{\text{index}}| / P_{\text{index}} > 0.5\%$ triggers hard veto.

### 3. Spot/Futures CVD Divergence (E15 SHADOW, E22 EXPERIMENTAL)
- **Data Source:** Aggregated perpetual trades vs Spot aggregated trades.
- **Causal Metric:** Cumulative Volume Delta slope $\text{Slope}(\text{CVD}_{\text{perp}})$ vs $\text{Slope}(\text{CVD}_{\text{spot}})$.
- **Risk Invariants:**
  - **Perpetual-Led Rally Without Spot:**
    $$\text{Slope}(\text{CVD}_{\text{perp}}) > 0 \quad \text{AND} \quad \text{Slope}(\text{CVD}_{\text{spot}}) \le 0$$
    Synthetic rally driven entirely by leveraged futures speculation without physical spot demand. Extreme flush vulnerability $\rightarrow$ intercepts and blocks dangerous LONG entries.
  - **Perpetual-Led Dump Without Spot Selling:**
    $$\text{Slope}(\text{CVD}_{\text{perp}}) < 0 \quad \text{AND} \quad \text{Slope}(\text{CVD}_{\text{spot}}) \ge 0$$
    Futures dump meeting passive institutional spot absorption. Squeeze vulnerability $\rightarrow$ intercepts and blocks dangerous SHORT entries.
  - **Registry Status:** E15 remains SHADOW; E22 remains EXPERIMENTAL.

### 4. Liquidation Cascade (E13 SHADOW, E14 EXPERIMENTAL)
- **Data Source:** Binance WebSocket `!forceOrder@arr` liquidation event stream.
- **Critical Data Integrity Rule:**
  > [!IMPORTANT]
  > Binance public WebSocket liquidation feeds are heavily sampled and throttled. Missing liquidation events MUST NEVER be interpreted as absence of liquidations. Liquidation data is treated strictly as an asymmetrical warning trigger, never as an active trade signal.
- **Risk Invariants:**
  - **Long Liquidation Burst:** Forced market sell volume $> \$500,000$ in trailing 15m. Cascade in progress $\rightarrow$ flags LONG-side danger (falling knife).
  - **Short Liquidation Burst:** Forced market buy volume $> \$500,000$ in trailing 15m. Vertical short squeeze in progress $\rightarrow$ flags SHORT-side danger.
  - **Registry Status:** E13 remains SHADOW; E14 remains EXPERIMENTAL.

### 5. Orderbook Liquidity Void (X03 ACTIVE, E16/E17 SHADOW)
- **Data Source:** CoinDCX Public Orderbook Depth & Binance L2 snapshots.
- **Risk Invariants:**
  - **Stale Book Gate (`V-H06`):** Depth update $> 3.0\text{s}$ old triggers immediate fail-closed hard veto.
  - **Spread Gate (`V-H12` / `V-H33`):** Spread $> 12\text{ bps}$ (Major) or $> 25\text{ bps}$ (Alt) triggers hard veto.
  - **Depth Gate (`V-H13` / `V-H34`):** Top-10 orderbook depth $< 20\times$ clip triggers hard veto.
  - **Liquidity Imbalance Voids:**
    - *Bid-Side Void:* Order Book Imbalance $\text{OBI}_{10} < -0.60$ (severe ask book skew). Elevated air-pocket collapse risk $\rightarrow$ flags LONG danger.
    - *Ask-Side Void:* Order Book Imbalance $\text{OBI}_{10} > +0.60$ (severe bid book skew). Elevated air-pocket spike risk $\rightarrow$ flags SHORT danger.
  - **Registry Status:** X03 remains ACTIVE; E16 and E17 remain SHADOW.

### 6. Structural Exhaustion (E01 ACTIVE, E05 SHADOW, Tested Wilder RSI)
- **Data Source:** Trailing closed candles and identified structural Swing Pivots.
- **Causal Metric:** Tested 14-period Wilder Relative Strength Index ([`RSIEngine`](file:///c:/projects/neo-wilder-v4/src/neo_wilder/features/rsi.py)) and structural divergence over confirmed swing pivots.
- **Risk Invariants:**
  - **Bearish Divergence (LONG Danger):**
    $$P(\text{SwingHigh}_2) > P(\text{SwingHigh}_1) \quad \text{AND} \quad \text{RSI}(\text{SwingHigh}_2) < \text{RSI}(\text{SwingHigh}_1)$$
    Price printing Higher High while momentum prints Lower High in overbought territory ($\text{RSI} > 65$) $\rightarrow$ structural exhaustion. Blocks/abstains LONG entries into terminal tops.
  - **Bullish Divergence (SHORT Danger):**
    $$P(\text{SwingLow}_2) < P(\text{SwingLow}_1) \quad \text{AND} \quad \text{RSI}(\text{SwingLow}_2) > \text{RSI}(\text{SwingLow}_1)$$
    Price printing Lower Low while momentum prints Higher Low in oversold territory ($\text{RSI} < 35$) $\rightarrow$ structural exhaustion. Blocks/abstains SHORT entries into terminal bottoms.
  - **Registry Status:** E01 remains ACTIVE; E05 remains SHADOW.

---

## 3. Bidirectional Danger Matrix

| Risk Dimension | LONG-Side Danger Profile | SHORT-Side Danger Profile | Automated Action |
|---|---|---|---|
| **OI Divergence** | Trapped long buildup ($\Delta P < -1\%$, $\Delta \text{OI} > +3\%$) | Trapped short buildup ($\Delta P > +1\%$, $\Delta \text{OI} > +3\%$) | Soft penalty (-8 pts) |
| **Rapid Deleveraging** | $\Delta \text{OI} < -5\%$ (violent unwinding) | $\Delta \text{OI} < -5\%$ (violent unwinding) | Soft penalty (-8 pts) |
| **Funding Crowding** | $F > +0.05\%$ (Longs paying exorbitant fee) | $F < -0.05\%$ (Shorts paying exorbitant fee) | **Hard Veto Escalation** (`V-S04_ESCALATED`) |
| **Settlement Window** | Within $[-15\text{m}, +5\text{m}]$ of 8h settlement | Within $[-15\text{m}, +5\text{m}]$ of 8h settlement | **Hard Veto** (`V-H17`) |
| **CVD Divergence** | Perp CVD up, Spot CVD down/flat | Perp CVD down, Spot CVD up/flat | Soft penalty (-10 pts) |
| **Liquidation Cascade** | Long liquidation burst $> \$500,000$ | Short liquidation burst $> \$500,000$ | Soft penalty (-8 pts) |
| **Liquidity Void** | Bid void ($\text{OBI} < -0.60$) | Ask void ($\text{OBI} > +0.60$) | Soft penalty (-6 pts) |
| **Book Staleness** | Orderbook depth $> 3\text{s}$ old | Orderbook depth $> 3\text{s}$ old | **Hard Veto** (`V-H06`) |
| **Abnormal Spread** | Spread $> 12\text{ bps}$ (Major) / $> 25\text{ bps}$ (Alt) | Spread $> 12\text{ bps}$ (Major) / $> 25\text{ bps}$ (Alt) | **Hard Veto** (`V-H12` / `V-H33`) |
| **Book Depth** | Top-10 Depth $< 20\times$ clip | Top-10 Depth $< 20\times$ clip | **Hard Veto** (`V-H13` / `V-H34`) |
| **RSI Exhaustion** | Bearish Divergence (Price HH, RSI LH) | Bullish Divergence (Price LL, RSI HL) | Soft penalty (-10 pts) |
| **Composite Multi-Danger** | $\ge 2$ simultaneous active danger flags | $\ge 2$ simultaneous active danger flags | **Hard Veto Escalation** (`V-H33_RISK_GUARD`) |

---

## 4. Pipeline Integration & Fail-Closed Precedence

The guard is directly integrated into [`VetoPipeline.evaluate_candidate`](file:///c:/projects/neo-wilder-v4/src/neo_wilder/vetoes/pipeline.py#L40):

1. **Stage 1:** Invariant Hard Veto evaluation (`V-H01` through `V-H34`).
2. **Stage 2:** [`ExtremeMarketRiskGuard.evaluate_candidate`](file:///c:/projects/neo-wilder-v4/src/neo_wilder/vetoes/risk_guard.py#L50).
   - If any hard veto or escalated crowding condition is met: candidate is blocked immediately.
   - If missing critical data is detected: returns fail-closed `ABSTAIN` / block.
   - If soft danger flags are detected: soft penalty points are passed into the scoring engine.
   - If $\ge 2$ danger flags are concurrent: candidate is escalated to hard block (`V-H33_RISK_GUARD`).
3. **Stage 3:** Standard Soft Veto evaluation and escalation checks.
