# DATA_SOURCE_AUDIT.md — NEO-WILDER V4 Data Architecture & Feasibility Audit

**Audit Date:** 2026-11-06  
**Auditor Role:** Chief Architect & Main Integrator  
**Audit Scope:** Verification of Binance USD-M and CoinDCX endpoints, field schemas, refresh frequencies, rate limits, structural limitations, and verification statuses.

---

## 1. Venue Separation & Architectural Boundary

```mermaid
flowchart LR
    subgraph Research Venue [Venue 1: Binance USD-M Futures (Research & Setup)]
        B_WS[Binance WebSocket: aggTrade, klines, depth20, forceOrder]
        B_REST[Binance REST: klines 15m, premiumIndex, openInterest]
    end

    subgraph Internal Engine [NEO-WILDER V4 Engine]
        PIPE[Feature -> Edge -> Strategy -> Veto -> Scoring]
    end

    subgraph Execution Venue [Venue 2: CoinDCX Public APIs (Validation Only)]
        C_PRICE[CoinDCX current_prices/rt: price, fr, efr, mp]
        C_BOOK[CoinDCX orderbook/10: depth, spread]
        C_INST[CoinDCX active_instruments: mapping]
    end

    subgraph Manual Operator [Human Trader]
        TG[Telegram Channel: Signal Payload]
        APP[CoinDCX App: Manual Order Entry]
    end

    B_WS --> PIPE
    B_REST --> PIPE
    PIPE --> V_GATE{Execution Gate}
    C_PRICE --> V_GATE
    C_BOOK --> V_GATE
    C_INST --> V_GATE
    V_GATE -- Pass (Drift <= 0.35%) --> TG
    V_GATE -- Fail --> DROP[Block: V-H31 / V-H32]
    TG --> APP
```

> [!IMPORTANT]
> **Permanent Asymmetry Rule:**  
> Binance is the **research and signal-generation venue**. CoinDCX is strictly the **execution-validation venue**. No private CoinDCX API keys, HMAC signatures, or order placement endpoints exist or will ever be implemented.

---

## 2. Binance USD-M Futures Data Architecture

### 2.1 Public WebSocket Streams (`wss://fstream.binance.com/stream`)

| Stream Name | Pattern / Endpoint | Target Features / Edges | Update Cadence | Status | Verified Limitations |
|---|---|---|---|---|---|
| **`aggTrade`** | `<symbol>@aggTrade` | CVD (`E15`), Microstructure (`E17`), Hawkes (`E20`) | Real-time (per trade tick) | **VERIFIED** | High message volume on BTC/ETH; requires non-blocking bounded queue |
| **`kline_5m`** | `<symbol>@kline_5m` | Intrabar momentum, volatility | 250 ms / bar close | **VERIFIED** | Closed bar evaluated only on `x: true` flag |
| **`depth20@100ms`** | `<symbol>@depth20@100ms` | Order Book Imbalance (`E16`), Spread | 100 ms | **VERIFIED** | Top-20 levels only; not full book. Suffices for 15m manual context |
| **`!forceOrder@arr`** | `!forceOrder@arr` | Liquidation burst $Z_{\text{liq}}$ (`E13`) | Snapshot per liquidation | **VERIFIED (LIMITED)** | **Structural Limitation:** Binance publishes at most **1 liquidation per symbol per 1000 ms**. Heavy cascades are under-sampled |

### 2.2 Public REST Endpoints (`https://fapi.binance.com`)

| Endpoint Path | Target Features / Vetoes | Poll Cadence | Rate Weight | Status | Verified Limitations |
|---|---|---|---|---|---|
| **`/fapi/v1/klines`** | 15m closed bars (`E01`, `E04`, `E11`) | Startup + every 15m | 5–10 | **VERIFIED** | 1000 bars max per call; backfill requires paginated chunking |
| **`/fapi/v1/premiumIndex`** | Mark/Index divergence (`V-H18`), Funding (`E23`, `V-H17`) | Every 30s | 1 | **VERIFIED** | Returns `markPrice`, `indexPrice`, `lastFundingRate`, `nextFundingTime` |
| **`/fapi/v1/openInterest`** | OI exhaustion (`E21`, `S2`) | Every 30s | 1 | **VERIFIED** | Current snapshot only |
| **`/futures/data/openInterestHist`**| Trailing OI delta calculation | Startup / 15m | 1 | **VERIFIED** | 5m granularity, 30-day historical limit |
| **`/futures/data/takerlongshortRatio`**| Long/Short taker volume ratio | Diagnostic | 1 | **VERIFIED** | Useful for telemetry only |
| **`/futures/data/topLongShortPositionRatio`**| Top trader sentiment | None (Dropped) | 1 | **UNVERIFIED / REQUIRES KEY** | Documentation specifies `X-MBX-APIKEY` required; dropped in V4 |

---

## 3. CoinDCX Public Data Architecture & Verified Limitations

### 3.1 Public REST Endpoints

| Purpose | Exact Endpoint URL | Verified Fields | Verification Status | Rate Limit & Quota |
|---|---|---|---|---|
| **Real-time Futures Prices** | `GET https://public.coindcx.com/market_data/v3/current_prices/futures/rt` | `fr` (funding rate), `efr` (estimated funding), `mp` (mark price), `price` | **VERIFIED** | 10 req/sec public pool |
| **Orderbook Depth** | `GET https://public.coindcx.com/market_data/v3/orderbook/{instrument}-futures/10` | `bids[{price, quantity}]`, `asks[{price, quantity}]` | **VERIFIED** | Depth levels 10, 20, 50 supported |
| **Recent Public Trades** | `GET https://api.coindcx.com/exchange/v1/derivatives/futures/data/trades?pair=...` | `price`, `quantity`, `timestamp`, `maker` | **VERIFIED** | Trailing 50 trades |
| **Active Instruments** | `GET https://api.coindcx.com/exchange/v1/derivatives/futures/data/active_instruments` | Symbol mapping, tick_size, min_quantity, status | **VERIFIED** | Queried once at startup |
| **Candlesticks** | `GET https://public.coindcx.com/market_data/candlesticks?...&pcode=f` | `open`, `high`, `low`, `close`, `volume` | **VERIFIED (LIMITED)** | **Supported resolutions: 1, 5, 60, 1D only** |
| **Open Interest** | *None* | — | **DOES NOT EXIST** | No public endpoint documented |
| **Liquidation Stream** | *None* | — | **DOES NOT EXIST** | No public endpoint documented |

### 3.2 Critical Finding: Absence of CoinDCX 15-Minute Candle Endpoint

> [!WARNING]
> **EXPLICIT AUDIT VERIFICATION — NO 15-MINUTE CANDLES ON COINDCX:**  
> External API audit of `https://docs.coindcx.com/` confirms that CoinDCX public candlestick API supports only resolutions:
> - `1` (1 minute)
> - `5` (5 minutes)
> - `60` (1 hour)
> - `1D` (1 day)
>
> There is **no native 15-minute (`15`) candle resolution on CoinDCX**.
>
> **Consequences for V4 System:**
> 1. Signal generation on 15m timeframe **cannot be computed natively from CoinDCX candles**.
> 2. Even if aggregated from 5m candles, CoinDCX lacks Open Interest, Mark/Index streams, and Liquidation feeds.
> 3. Therefore, **Binance is confirmed as the sole, non-negotiable research and signal generation engine**. CoinDCX data is strictly used to validate whether the published Binance setup is actionable and executable by a human manual trader.

---

## 4. Symbol Mapping & Price Drift Gate

### 4.1 Canonical Symbol Mapping Convention
CoinDCX futures pair names format as:
$$\text{CoinDCX Pair} = \text{"B-"} + \text{BASE} + \text{"\_USDT"}$$
- Binance `BTCUSDT` $\longrightarrow$ CoinDCX `B-BTC_USDT`
- Binance `ETHUSDT` $\longrightarrow$ CoinDCX `B-ETH_USDT`
- Binance `SOLUSDT` $\longrightarrow$ CoinDCX `B-SOL_USDT`

At startup, `data/rest_coindcx.py` queries `/active_instruments`. If a Binance symbol has no active corresponding CoinDCX contract (or status $\ne \text{"TRADING"}$), that symbol is automatically dropped from the active universe.

### 4.2 Price Drift & Spread Gating Logic

When S1 generates a candidate signal at Binance close $P_{\text{ref}}$, the engine immediately queries CoinDCX `current_prices/rt` and `orderbook/10`:

1. **CoinDCX Feed Availability (`V-H31`):**
   If CoinDCX REST times out, returns HTTP error, or returns an empty price payload, **`V-H31` blocks the signal fail-closed**.
2. **Price Drift Threshold (`V-H32`):**
   $$\text{Drift} = \frac{|P_{\text{coindcx}} - P_{\text{ref}}|}{P_{\text{ref}}}$$
   If $\text{Drift} > 0.35\%$, **`V-H32` blocks the signal**.
3. **Execution Spread Check (`V-H12` / `X03`):**
   $$\text{Spread}_{\text{bps}} = \frac{\text{Ask}_{\text{best}} - \text{Bid}_{\text{best}}}{\text{Bid}_{\text{best}}} \times 10,000$$
   Must be $\le 12 \text{ bps}$ for Major pairs (BTC, ETH) and $\le 25 \text{ bps}$ for Altcoins.
4. **Order Book Depth Check (`V-H13` / `X03`):**
   Top-10 cumulative notional depth on CoinDCX must be $\ge 20 \times \text{intended clip notional}$ (e.g. $\ge \$10,000$ for a $\$500$ clip).

---

## 5. Cost Model & Indian GST Accounting

| Friction Component | Baseline Assumption | Verified Citation / Calculation |
|---|---|---|
| **CoinDCX Taker Fee** | $0.050\%$ per side | Verified via CoinDCX fee schedule snippet (`RESEARCH_REFERENCES.md` §B.5) |
| **CoinDCX Maker Fee** | $0.044\%$ per side | Verified via CoinDCX fee schedule snippet |
| **Indian GST on Fees** | $+18.0\%$ on brokerage fees | Mandatory Indian GST statute: $0.050\% \times 1.18 = 0.059\%$ per side |
| **Round-Trip Fee + GST** | **$0.1180\%$** | $2 \times 0.059\% = 0.1180\%$ (taker entry + taker exit) |
| **Dynamic Slippage Model** | **$0.0174\%$** (median estimate) | $\text{Slippage} = 0.5 \times \text{spread\_bps} + 0.3 \times \frac{\text{ATR\_bps}}{100}$, floored at $1.0\text{ bp}$ |
| **Total Baseline Round-Trip Friction** | **$0.1354\%$** | $0.1180\% + 0.0174\% = 0.1354\%$ |
| **Holding Cost (Funding)** | Dynamic historical | Applied per 8h settlement period elapsed during trade |

> [!CAUTION]
> **Legacy Defect Contrast:**  
> Legacy `guards/vetoes.py` used a flat round-trip fee of `0.0010` (0.10%) with **zero GST**. This understated trading costs by $35.4\%$, converting marginally losing strategies into false positives. V4 enforces the full $0.1354\%$ minimum friction in all net R:R calculations (`V-H22`).
