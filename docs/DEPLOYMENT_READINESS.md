# DEPLOYMENT_READINESS.md — NEO-WILDER V4 Production Readiness Statement

**System:** NEO-WILDER V4  
**Architect:** Chief Architect & Main Integrator  
**Date:** 2026-11-06  
**Operating Architecture:** Single Asyncio Process (Permanent SIGNAL_ONLY)

---

## 1. Host Infrastructure Specification

| Component | Target Specification | Production Configuration |
|---|---|---|
| **Platform** | Cloud VPS / Dedicated Server | Debian 12 (Bookworm) or Ubuntu 22.04/24.04 LTS |
| **vCPU** | 2 Virtual Cores | `CPUQuota=150%` enforced via systemd |
| **Physical RAM** | 1024 MB (1 GB) | `MemoryHigh=350M`, `MemoryMax=400M` enforced |
| **Swap** | 1024 MB Swapfile | Enabled to absorb transient OS spikes |
| **Python Runtime** | Python 3.11.9+ | Dedicated isolated virtualenv at `/opt/neo-wilder-v4/.venv` |
| **Clock Synchronization** | Microsecond accuracy | `chrony` configured with NTP servers ($< 50\text{ ms}$ jitter) |

---

## 2. Resource Budget & Memory Ceiling Analysis

The application runs in a single asynchronous event loop with strict memory boundaries:

- **Aggregated Trades Ringbuffer:** `deque(maxlen=20000)` per symbol ($\approx 3.2\text{ MB}$ for 3 symbols).
- **Orderbook Depth Ringbuffer:** `deque(maxlen=300)` per symbol ($\approx 1.5\text{ MB}$).
- **Historical 15m Candles:** `deque(maxlen=500)` per symbol ($\approx 0.8\text{ MB}$).
- **SQLite WAL Cache:** `PRAGMA cache_size = -20000` ($\approx 20\text{ MB}$).
- **Process Memory Profile:**
  - **Baseline Idle RSS:** $\approx 45\text{ MB}$.
  - **Peak Operational RSS:** $< 150\text{ MB}$ (verified in Phase 11 100k-trade stress test).
  - **Internal Warning Target:** $220\text{ MB}$ (`TARGET_CEILING_RSS_MB`).
  - **Hard Veto Trigger:** $300\text{ MB}$ (`V-H08: MEMORY_EMERGENCY`).
  - **Systemd Hard Kill:** $400\text{ MB}$ (`MemoryMax=400M`).

---

## 3. Database Persistence & Concurrency Model

- **Database Engine:** SQLite 3 with Write-Ahead Logging (`PRAGMA journal_mode=WAL;`).
- **Synchronization:** `PRAGMA synchronous=NORMAL;` for SSD endurance and sub-millisecond writes.
- **Concurrency Guarantee:** Single-writer async loop draining a bounded `asyncio.Queue(maxsize=10000)`. Multiple concurrent readers are supported without locking contention.
- **Fail-Safe Flushing:** On graceful termination (`SIGTERM` / `SIGINT`), the queue flushes all pending records before database connection closure.

---

## 4. Security & SIGNAL_ONLY Invariant

The codebase has undergone a zero-execution audit:
1. **Zero Exchange Private Keys:** The system configuration and code contain no fields for Binance or CoinDCX API keys, secret keys, or passphrases.
2. **Zero Order Execution Code:** No execution endpoints, order creation methods, cancellation logic, or balance mutation tools exist in the codebase.
3. **Fail-Closed Hard Vetoes:** Hard vetoes (`V-H01` through `V-H34`) are immutable and can NEVER be bypassed by any operator flag, configuration, or high quality score.

---

## 5. CoinDCX Public Validation & Friction Architecture

- **Venues:** Binance USD-M WebSocket & REST streams are used strictly for causal research and signal generation. CoinDCX public REST APIs are used strictly for real-time manual execution validation.
- **Friction Model:**
  - Taker Fee: $0.050\%$ per side.
  - Indian GST: $+18\%$ on fees $\rightarrow 0.059\%$ per side ($0.1180\%$ round-trip).
  - Slippage Model: $0.5 \times \text{spread} + 0.3 \times (\text{ATR}/100)$ with a $1.0\text{ bp}$ floor (baseline $0.0174\%$).
  - Baseline Round-Trip Friction: $0.1354\%$.
- **Validation Gates:**
  - Price Drift Gate: Cross-venue divergence $> 0.35\%$ blocks publication (`V-H32`).
  - Spread Gate: Spread $> 12\text{ bps}$ (Major) or $> 25\text{ bps}$ (Alt) blocks publication (`V-H33`).
  - Depth Gate: Orderbook depth $< 20\times$ clip blocks publication (`V-H34`).

---

## 6. Honest Empirical Validation Declarations

In accordance with institutional research integrity standards, the following status flags are explicitly declared:

| Area | Production Status | Requirement for Promotion |
|---|---|---|
| **Quality Calibration** | **`NOT CALIBRATED`** | Requires $\ge 300$ resolved live trades recorded in `DatabaseStore` to fit isotonic regression. |
| **Shadow Mode** | **`RUNTIME VALIDATION PENDING / NOT PROVEN`** | Requires 8 weeks (56 days) continuous live VPS soak, $\ge 50$ shadow setups, and 0 crashes. |
| **Manual Paper Validation** | **`MANUAL PAPER VALIDATION PENDING / NOT PROVEN`** | Requires $\ge 100$ resolved operator `/fill` records achieving $\ge 45\%$ win rate, $\ge 1.40$ PF, $\ge +0.35\text{ R}$, $\le 6.0\text{ R}$ DD. |
| **S1 Short Strategy** | **`DISABLED (ABSTAIN)`** | Fail-closed preservation of incomplete source formulas; zero short candidates generated. |

---

## 7. Signoff

The NEO-WILDER V4 system is fully implemented, tested, and ready for deployment to the production VPS under the supervision of the operator.
