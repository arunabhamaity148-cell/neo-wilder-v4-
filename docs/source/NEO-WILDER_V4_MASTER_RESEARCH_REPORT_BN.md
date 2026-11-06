# NEO-WILDER V4 — মাস্টার ডিপ রিসার্চ রিপোর্ট
### Institutional-Grade, Signal-Only Crypto Futures Intelligence System (Binance Research → CoinDCX Manual Execution)

তারিখ: ২০২৬-১১-০৫ · প্রমাণের শ্রেণি: `[CODE]` = ZIP থেকে সরাসরি পড়া · `[DOC]` = আপনার দেওয়া PDF · `[EXT]` = এই সেশনে যাচাইকৃত বাহ্যিক সূত্র · `[ENG]` = প্রকৌশল সুপারিশ · `[HYP]` = পরীক্ষা-সাপেক্ষ অনুমান

---

## ১. Executive Verdict

**সিদ্ধান্ত: GO — তবে শুধুমাত্র Phase 9 (backtest + ablation) পাস করার শর্তে, এবং legacy কোডবেস পুনঃব্যবহার না করে নতুন করে লিখে।**

তিনটি নির্ণায়ক তথ্য:

1. আপনার দেওয়া `neo-audit-final.zip` (201 ফাইল, 30 ডিরেক্টরি) আসলে একটি **অসম্পূর্ণ v2→v3 রিফ্যাক্টরিং**। সবচেয়ে বড় ফাইল `apply_fixes.py`, এবং `.env.example` / `requires.txt` / `guards/kill_switch.py` / `config/development.yaml` / `main.py` কার্যত খালি। [CODE]
2. legacy রিপো **SIGNAL_ONLY শর্ত ভঙ্গ করে** — `execution/coindcx_client.py:133-149` HMAC দিয়ে প্রাইভেট POST `/exchange/v1/derivatives/futures/positions` করে, এবং `maker_engine.py`, `exit_manager.py`, `adapters/exchange/execution_bridge.py`, `adapters/exchange/indian_adapter.py` বিদ্যমান। [CODE]
3. আপনার PDF-এ দাবি করা **"১৪টি hard veto" কোডে নেই**। `guards/pipeline.py` মাত্র **১১টি** guard ওয়্যার করে; `guards/vetoes.py`-এ **৭টি** numeric veto + ১টি news flag = ৮, এবং `VetoEngine` পাইপলাইনে **import-ই করা হয়নি** (dead code)। → **UNVERIFIED / CONTRADICTED**। [CODE]

তবে একটি বাস্তব সম্পদ আছে: **Liquidity Sweep + Reclaim সেটআপ** (`strategies/sweep_reclaim_v1.py:60-240`) সম্পূর্ণ, পরীক্ষাযোগ্য এবং dynamic-stop লজিকসহ বাস্তবায়িত। V4-এর ভিত্তি এটিই।

**Readiness:** v3 = 48.2/100 (NO-GO, আপনার PDF-এও একই)। v4 **আজ** = 0/100 প্রোডাকশন (কোড নেই), কিন্তু **আর্কিটেকচার = 100% নির্ধারিত**।

---

## ২. Legacy Codebase Audit

| যাচাই | ফলাফল |
|---|---|
| ডিরেক্টরি / ফাইল | 30 / 201 [CODE] |
| `src/` ফাইল | 122 (guards 16, features 17, strategies 6, validation 10) [CODE] |
| `tests/` | 49 মডিউল [CODE] |
| `HardVetoReason` enum | ঠিক **56** সদস্য [CODE] |
| পাইপলাইনে wired guard | **11** [CODE] |
| `vetoes.py` veto ফাংশন | **7** + news = 8, সব **dead code** [CODE] |
| Edge 1–7 | EDGE_1 wired; EDGE_6, EDGE_7 বাস্তবায়িত; **EDGE_2..EDGE_5 এর কোনো evaluator নেই** [CODE] |
| Score scale | কোডে max **100**, Telegram-এ ছাপা হয় **/200** → bug [CODE] |

### ১০টি নিশ্চিত Integrity Defect
1. `telegram/formatter.py` ও `adapters/telegram/formatter.py` হুবহু একই (দুটোই 8,312 B), কিন্তু `adapters/telegram/publisher.py` নেই → ওই পথে publish অসম্ভব।
2. `VetoEngine` dead code (উপরে)।
3. তিনটি বিরোধী score threshold: `quality_score.SCORE_THRESHOLD=76`, `calibration.MIN/MAX=76..86`, `config/base.yaml publish_threshold=85.0`।
4. দুই R:R threshold: `base.yaml min_r_multiple=1.5` vs `vetoes.MIN_NET_RR_RATIO=1.30`।
5. দুই concurrency limit: `portfolio_risk.max_concurrent_trades=4` vs `governors.ClusterHeatGovernor(max_concurrent=2)`।
6. দুই regime taxonomy: `strategies/router.py` (৫ state, int enum) vs `regime/vr_tracker.py` (৩ state, str enum)।
7. `quality_score`-এ `idea2/idea3/idea4/idea5` slot আছে কিন্তু কোনো evaluator নেই → phantom edge স্কোর ফুলিয়ে দেয়।
8. SIGNAL_ONLY লঙ্ঘন (উপরে)।
9. `docs/ARCHITECTURE.md`-এ 128-byte SHM bridge + hot/cold dual daemon — 1 GB VPS-এ ~২গুণ baseline RAM, signal quality-তে শূন্য লাভ।
10. `cold/deribit.py`-এ dealer gamma sign **অনুমান** করা হয়েছে (call +1 / put −1); বাস্তব dealer positioning-এর কোনো যাচাইযোগ্য সূত্র নেই। [CODE]

---

## ৩. সম্পূর্ণ Legacy Edge Inventory (২৮টি verified edge + ৪টি নতুন)

| ID | নাম | সোর্স | V4 সিদ্ধান্ত |
|---|---|---|---|
| E01 | Liquidity Sweep & Reclaim | `sweep_reclaim_v1.py:60-240` | **ACTIVE (spine)** |
| E02 | 4-Stage Sweep | `sweep_detector.py:49` | SHADOW |
| E03 | Sweep depth / ATR | `calibration.py:49` | ACTIVE (feature) |
| E04 | Liquidity pool EQH/EQL | `liquidity_pools.py:51` | ACTIVE |
| E05 | BOS / CHoCH | `structure.py:42` | SHADOW |
| E06 | Supply/Demand zone | `zones.py:38` | SHADOW |
| E07 | Volume Profile POC/VAH/VAL | `volume_profile.py:40` | ACTIVE (target) |
| E08 | Anchored VWAP | `anchored_vwap.py:13` | EXPERIMENTAL |
| E09 | Poor High/Low | `poor_hl_fvg.py:22` | EXPERIMENTAL |
| E10 | Fair Value Gap | `poor_hl_fvg.py:69` | SHADOW |
| E11 | ATR / vol regime | `volatility.py:59` | ACTIVE |
| E12 | Dynamic stop buffer | `sweep_reclaim_v1.py:34` | ACTIVE |
| E13 | Z_liq burst | `liq_heatmap.py:16` | SHADOW |
| E14 | Liq cluster proximity | `liq_heatmap.py:68` | EXPERIMENTAL |
| E15 | CVD turn | `orderflow.py:58` | SHADOW |
| E16 | OBI top-10 | `orderflow.py:15` | SHADOW |
| E17 | Book density / absorption | `book_density.py:17,44` | SHADOW |
| E18 | Microprice | `micro_price.py:15` | **REJECT** |
| E19 | Microbar volume clock | `microbar.py:16` | **REJECT** |
| E20 | Hawkes intensity | `hawkes.py:33` | SHADOW (diagnostic) |
| E21 | OI exhaustion (EDGE_6) | `advanced_edges.py:159` | SHADOW |
| E22 | Spot-led basis (EDGE_7) | `advanced_edges.py:218` | EXPERIMENTAL |
| E23 | Funding context | `funding_context.py:85` | ACTIVE (veto) |
| E24 | Mark/Index divergence | `funding_context.py:60` | ACTIVE (veto) |
| E25 | Variance-ratio regime | `router.py:34` / `vr_tracker.py` | SHADOW |
| E26 | GEX / gamma flip | `cold/deribit.py:93-161` | **REJECT** |
| E27 | Session classification | `walk_forward.py:100` | EXPERIMENTAL |
| E28 | Expiry / invalidation engine | `expiry_engine.py:32-355` | **ACTIVE** |
| X01 | BTC directional conflict | নতুন | ACTIVE (soft veto) |
| X02 | Relative volume gate | নতুন | ACTIVE |
| X03 | CoinDCX spread/liquidity gate | নতুন | ACTIVE |
| X04 | Late-entry suppression | নতুন | ACTIVE |

**কেন E18/E19 বাদ:** আপনার হরাইজন ৫–১৫ মিনিট এবং execution **ম্যানুয়াল**। মাইক্রোপ্রাইস ও ভলিউম-ক্লক মাইক্রোসেকেন্ড-স্কেল টুল; এই হরাইজনে এদের কোনো প্রমাণিত অবদান নেই, কিন্তু একটি সমান্তরাল bar-universe + state machine-এর খরচ আছে। [ENG]

**কেন E26 বাদ (routing থেকে):** dealer gamma sign কোডে **ধরে নেওয়া**, যাচাই করা যায় না। চিহ্ন ভুল হলে সম্পূর্ণ সিদ্ধান্ত উল্টে যায় → `DATA SOURCE NOT VERIFIED`। [CODE][EXT]

---

## ৪. সম্পূর্ণ Veto Inventory

**৩৪টি Hard Veto (V-H01..V-H34)** — সম্পূর্ণ তালিকা `VETO_REGISTRY.yaml`-এ। মূল গ্রুপ:

| গ্রুপ | ID | উদাহরণ |
|---|---|---|
| Data integrity | V-H01..V-H04 | stale, gap, ts invalid, duplicate candle |
| Infra health | V-H05..V-H11 | ws down >5s, book stale, clock skew >1s, RSS >300MB, kill switch, watchdog, critical source down |
| Market safety | V-H12..V-H14 | spread >12bps major / 25bps alt, depth <20× clip, gap >3% |
| Event/derivatives | V-H15..V-H18, V-H33 | news −15/+30min, calendar outage, funding ±15/5min, mark-index >0.5%, regime ineligible |
| Risk geometry | V-H19..V-H23 | zone inverted, SL <max(0.65%,0.5ATR), TP ordering, **net R:R <1.50**, slippage >15% of SL |
| Exposure | V-H26..V-H30 | concurrent ≥2, cluster >2.0R, day −3%, week −6%, halted |
| Execution validation | V-H31, V-H32 | CoinDCX feed নেই → **block**, drift >0.35% → block |
| Governance | V-H24, V-H25, V-H34 | duplicate, cooldown, calibration artefact >90 দিন |

**১৫টি Soft Veto (V-S01..V-S15)** — প্রতিটি হয় confidence কমায়, নয়তো risk multiplier কমায়, নয়তো অতিরিক্ত confirmation দাবি করে; চরম অবস্থায় hard-এ escalate করে (যেমন `V-S04` funding >0.05%, `V-S10` entry progress >0.35)।

**Processing order (উন্নত):** data integrity → infra → market safety → event+derivatives+regime → strategy eligibility → risk geometry → exposure → **execution validation** → dedupe/cooldown → soft modifiers → final approval।
আপনার প্রস্তাবিত ক্রমে execution validation শেষে ছিল; V4-এ এটি risk geometry-র **আগে** আনা হয়েছে, কারণ CoinDCX-এ drift/স্প্রেড খারাপ হলে R:R পুনর্গণনারই প্রয়োজন নেই — সেটি অপ্রাসঙ্গিক সিগন্যাল ব্লক করার পরে হিসাব করার অপচয়।

**কোনো hard veto override করা যাবে না** — score, ML probability, config flag বা operator flag কোনোটিই নয়।

---

## ৫. প্রস্তাবিত Strategy Architecture — Hybrid ("One Spine, Three Plugs")

আপনার পছন্দ (একটি modular bot, অনেক আলাদা live bot নয়) **সঠিক** — তবে কারণটি আপনার দেওয়া কারণ নয়। কারণটি অপারেশনাল: 1 GB/2 vCPU-তে একাধিক প্রসেস + আলাদা state = OOM। বাজার-গাণিতিক কারণটিও আছে: sweep/reclaim, OI-exhaustion ও basis-divergence একই forced-flow ঘটনার তিনটি দিক, তাই আলাদা bot চালালে **একই ঘটনায় তিনটি সিগন্যাল** যাবে — যা আপনার নিজের "signal spam is a failure" নীতির বিরুদ্ধে।

| আর্কিটেকচার | সিদ্ধান্ত | কারণ |
|---|---|---|
| A. একক strategy | আংশিক | confirmation বাদ দিলে microstructure সম্পদ নষ্ট |
| B. অনেক independent bot | **REJECT** | RAM, duplicate signal, correlation |
| C. multi-edge scoring only | **REJECT** | score দিয়ে setup ছাড়া signal তৈরি করা যায় না |
| D. regime-first routing | **স্থগিত** | regime classifier (E25) এখনো অ-ক্যালিব্রেটেড, তার উপর routing = অজানা মডেলকে গুণ করা |
| **E. Hybrid** | **SELECTED** | spine = S1, plugs = confirmation + regime gating |

---

## ৬. Strategy-by-Strategy Specification (সারসংক্ষেপ)

**S1 SWEEP-RECLAIM-v4 (ACTIVE)**
- সেটআপ: pool (≥2 swing, 0.15 ATR-এর মধ্যে) + wick penetration `0.05–1.2 ATR` + same-bar reclaim + 2 bar-এর মধ্যে নিশ্চিত + অন্তত একটি confirmation (structure / displacement body >0.6 ATR / volume >1.2× median)।
- Entry zone: `[min(reclaim_close, pool), reclaim_close]`, সর্বনিম্ন প্রস্থ `max(0.20%, 0.05 ATR)`। Reference = reclaim bar-এর **close** (live price নয়)।
- Stop: `sweep_extreme ∓ buffer·ATR`, `buffer = α(pct_ATR) + 0.6·1[|funding|≥0.03%]`, α ∈ {1.5, 2.2, 3.0} (legacy E12 অপরিবর্তিত)।
- TP1 = নিকটতম opposing swing / VAH-VAL যেটি ≥1.5R; TP2 = 1.618 extension। **উপযুক্ত level না থাকলে ট্রেড নেওয়া হবে না** — legacy-র "ATR দিয়ে target বানানো" fallback বাদ, কারণ তাতে R:R একটি tautology হয়ে যায়।
- Expiry: `min(16, 4+2·vol_tier)` bar + CHoCH + MFE half-life।
- নিষিদ্ধ: NOISE_CHOP, atr_bps<4, সপ্তাহান্ত low-liquidity, rel_vol<0.8।

**S2 OI-EXHAUSTION-v4 (SHADOW)** — E21 + বাধ্যতামূলক E15 CVD turn + E13 Z_liq ≥2.0. শুধু LONG.
**S3 BASIS-DIVERGENCE-v4 (EXPERIMENTAL)** — E22, threshold ±0.5σ → **±1.5σ**, টানা 3 bar, feed clock offset >150ms হলে abstain।

**যে strategy families বানানো হবে না:** Session Sweep আলাদা engine, Trend Pullback Continuation, pure Mean-Reversion, Funding/OI Crowding Reversal — কারণ ও যুক্তি `STRATEGY_SPECIFICATIONS.md`-এ।

---

## ৭. Edge-by-Edge Research (কীভাবে প্রমাণ ছাড়া কিছুই দাবি করা হয়নি)

প্রতিটি edge-এর ১৭টি ফিল্ড (hypothesis, regime, formula, detection logic, confirmation, invalidation, deps, failure modes, data availability, backtest method, ablation method, recommendation) সম্পূর্ণ আছে `EDGE_REGISTRY.yaml` + `EDGE_DEPENDENCY_MATRIX.md`-এ।

উদাহরণ — **E13 Z_liq**-এর failure mode, যা আপনার নিজের নিয়ম অনুযায়ী লিখতে হয়েছে:
> Binance-এর `!forceOrder@arr` স্ট্রিম প্রতি সিম্বলে প্রতি **১০০০ ms উইন্ডোতে শুধু সর্বশেষ** liquidation প্রকাশ করে [EXT]। ফলে Z_liq প্রকৃত liquidation volume-এর একটি **lower bound**; এই sampling bias ক্লায়েন্ট-সাইডে ঠিক করার উপায় নেই। তাই historical liquidation dataset **DATA SOURCE NOT VERIFIED** এবং E13 কেবল SHADOW।

---

## ৮. Hard Veto Specification
`VETO_REGISTRY.yaml::hard_vetoes` — ৩৪টি, প্রতিটির `id`, `reason`, `severity`, `cond`, এবং প্রতিটির জন্য একটি টেস্ট কেস। বাধ্যতামূলক ১২টি: V-H01, H02, H03, H05, H08, H09, H12, H15, H17, H19, H22, H31।

## ৯. Soft Veto Specification
১৫টি; প্রতিটির `effect` (confidence ডেল্টা / risk multiplier / threshold ডেল্টা) এবং `escalates_to_hard` শর্ত।

---

## ১০. Correlation-Aware Scoring (double counting বন্ধ)

**৬টি cluster, প্রতিটির একটি slot ও cap** (বিস্তারিত `EDGE_DEPENDENCY_MATRIX.md`):

| Cluster | সদস্য | Cap |
|---|---|---|
| C1 forced-flow | E13,E14,E20,E17 | 12 |
| C2 order flow | E15,E16,E17 | 12 |
| C3 structure | E01,E02,E05,E06 | 20 |
| C4 positioning | E21,E22,E23,E24 | 12 |
| C5 location | E07,E08,E09,E10 | 10 |
| C6 regime | E25,E27 | score নয়, শুধু gate |

Score = `Σ cluster_score + rr_bonus`, সর্বোচ্চ ১০০। **legacy-র সমস্যা:** `quality_score.py` OBI (10) + OI/CVD (10) + squeeze (10) আলাদা slot দিত — তিনটিই C1/C2-এর ভেতরে, অর্থাৎ **৩০ পয়েন্ট একই ঘটনার জন্য**। V4-এ C1+C2 মিলে সর্বোচ্চ ২৪।

**Score ≠ Probability।** `calibrated_probability` কেবল তখনই ছাপা হবে যখন ≥300 resolved trade-এর OOS isotonic calibration artefact থাকে (hash + training window সহ); নাহলে স্ট্রিং লেখা হবে `NOT CALIBRATED`। V-H34 এটি বাধ্যতামূলক করে।

---

## ১১. Regime Detection Model

E25 = Lo–MacKinlay variance ratio, multi-lag composite `VR(q) = Var(r_q)/(q·Var(r_1))`।
- regime গুলো **mutually exclusive নয়** — state variable তিনটি: (a) VR trend state, (b) ATR bps vol state, (c) liquidity/spread stress flag।
- Hysteresis: VR threshold-এ ±0.03 dead-band, state পরিবর্তন হতে টানা 3 bar দরকার।
- ক্যালিব্রেশন: প্রতিটি সিম্বলের ২৪ মাসের ডেটায় VR-এর empirical quintile থেকে threshold, **arbitrary 0.96/1.05 নয়**।
- Eligibility: `STRATEGY_SPECIFICATIONS.md`-এর regime table।
- GEX regime (E26) **বাদ** — data source যাচাইযোগ্য নয়।

## ১২. CoinDCX Manual Execution Validation
যাচাইকৃত public endpoint: `current_prices/futures/rt` (fr, efr, mp সহ), `candlesticks` (res 1/5/**60**/1D — **15m নেই**), `orderbook/{pair}-futures/10|20|50`, `trades`। **open interest ও liquidation endpoint নেই** [EXT docs.coindcx.com]।
→ পরিণতি: CoinDCX-এ 15m সিগন্যাল জেনারেশন অসম্ভব, derivatives context-ও নেই। Binance = research venue, CoinDCX = execution venue — এটি স্থায়ী asymmetry।
Fee: Taker 0.050%, Maker 0.044%, **+18% GST** [EXT-SNIPPET coindcx.com/fees] → round-trip taker ≈ **0.118%**, slippage সহ ≈ **0.1354%**। legacy-র `0.0010` flat fee **GST বাদ দিয়ে** হিসাব করত → ভুল।

## ১৩. Data Source & API Feasibility

| ডেটা | সোর্স | অবস্থা |
|---|---|---|
| 15m/5m/1m klines | `/fapi/v1/klines` | VERIFIED |
| aggTrades (CVD) | `/fapi/v1/aggTrades` + ws | VERIFIED |
| depth20@100ms | ws | VERIFIED (top-20, full book নয়) |
| liquidation | `!forceOrder@arr` | VERIFIED কিন্তু **প্রতি সিম্বলে প্রতি সেকেন্ডে ১টি** → under-sampled |
| funding / mark | `/fapi/v1/premiumIndex` | VERIFIED |
| OI | `/fapi/v1/openInterest`, `/futures/data/openInterestHist` | VERIFIED (poll ≥30s) |
| long/short ratio | `/futures/data/*` | VERIFIED (top trader-এ API key লাগে) |
| GEX dealer positioning | কোনো verified সোর্স নেই | **DATA SOURCE NOT VERIFIED** |
| historical liquidation (backtest) | CoinGlass paid, free tier নেই | **DATA SOURCE NOT VERIFIED** |

## ১৪. Backtesting Framework
`BACKTEST_PROTOCOL.md` — ২৪ মাস × ≥8 symbol, as-of-date universe, fee+GST+funding+slippage চারটিই মডেল করা, next-bar-open fill, missed-fill গণনা, intrabar ambiguity-তে SL-first, purge 24 bar, walk-forward 12/3।

## ১৫. Statistical Validation Protocol
Purged walk-forward + 6 মাস untouched OOS + deflated-Sharpe haircut + bootstrap 10,000 (5th percentile রিপোর্ট) + regime/direction/symbol partition + **প্রতি edge-এ ablation**।

## ১৬. ML বনাম Rule-Based
**সুপারিশ: rule-based + isotonic calibration; ML নয়।**
কারণ: (a) ১৫ মিনিট হরাইজনে sweep-setup-এর সংখ্যা বছরে কয়েকশ — XGBoost/LightGBM-এর জন্য যথেষ্ট নয়, (b) LODO/regime drift-এ tree model ভেঙে পড়ে, (c) inference cost 1 GB VPS-এ অপ্রয়োজনীয়, (d) ML কখনো hard veto bypass করতে পারবে না — ফলে ML-এর একমাত্র অবদান score-এ, যা rule-based group cap দিয়েও পাওয়া যায়। ML কেবল তখনই বিবেচ্য যখন Phase 9-এ ≥1000 resolved trade জমে এবং logistic regression OOS Brier score-এ rule-based-কে >5% হারায়। [ENG]

## ১৭. Final System Architecture
Data → Feature → Edge → Strategy → Veto → Score → Publish, **একক asyncio প্রসেস**, bounded queue, SQLite WAL একক writer। SHM bridge, cold path, দ্বিতীয় daemon — সব বাদ।

## ১৮. Complete Folder Structure
`FINAL_FOLDER_STRUCTURE.md` — `src/neo_wilder/{data,features,edges,strategies,vetoes,scoring,publish,journal,observability}` + `research/` (VPS-এ কখনো deploy হবে না) + মডিউল-প্রতি contract table (input/output/deps/error handling/unit/integration test)।

## ১৯. VPS Resource Budget (1 GB / 2 vCPU)

| উপাদান | RSS |
|---|---|
| Python + numpy | 55 MB |
| 8 symbol × bounded ringbuffers | 70 MB |
| SQLite page cache | 20 MB |
| aiohttp/Telegram | 15 MB |
| headroom | 60 MB |
| **মোট** | **220 MB** (hard block 300 MB, systemd `MemoryMax=400M`) |

**উত্তর: হ্যাঁ, ফিট করবে — কিন্তু শুধু একক প্রসেসে।** legacy-র dual daemon + SHM এই বাজেটে ফিট করে না।

## ২০. Telegram Signal Specification
Header: direction + symbol + strategy id + active/confirming edge ids + regime + BTC context।
Body: entry zone, reference, **CoinDCX validation price + spread bps**, SL, TP1/TP2, gross R:R, fee/slippage/funding, **net R:R**, score (0–100) + `NOT CALIBRATED` বা calibrated p, veto status, soft veto list, created/expiry UTC, max drift 0.35%, invalidation list, এক অনুচ্ছেদের Bengali thesis।
Footer: `SIGNAL_ONLY` ডিসক্লেইমার + `/fill <signal_id> <price> <size>` নির্দেশ।
**নিষিদ্ধ:** "90% accurate" জাতীয় লেবেল, `/200` স্কোর (legacy bug), unvalidated সিগন্যাল।

## ২১. Test & Acceptance Criteria
প্রতি veto-তে একটি "score 100 + veto ⇒ block" টেস্ট; look-ahead টেস্ট (future bar shuffle করে output অভিন্ন হতে হবে); determinism replay টেস্ট; chaos টেস্ট (feed kill, clock skew, disk full); restart drill; 6h soak।

## ২২. Risk Register

| ঝুঁকি | সম্ভাবনা | প্রভাব | প্রশমন |
|---|---|---|---|
| Overfit (edge সংখ্যা বেশি, trade কম) | উচ্চ | উচ্চ | ablation gate, deflated Sharpe, t>3 |
| CoinDCX drift/slippage > মডেল | উচ্চ | উচ্চ | V-H32 drift veto, `/fill` self-report |
| liquidation data under-sampled | নিশ্চিত | মধ্যম | E13 শুধু SHADOW, নিষ্ক্রিয় gate নয় |
| 1 GB OOM | মধ্যম | উচ্চ | একক প্রসেস, V-H08, MemoryMax |
| Binance API/symbol পরিবর্তন | মধ্যম | মধ্যম | active_instruments startup mapping, fail-closed |
| manual execution বিলম্ব | উচ্চ | মধ্যম | late-entry veto X04, expiry engine |
| regime classifier ভুল | মধ্যম | উচ্চ | routing নয়, শুধু gating; phase 9-এ যাচাই |

## ২৩. Implementation Roadmap
`IMPLEMENTATION_ROADMAP.md` — Phase 0 (সম্পন্ন) → 1 registries → 2 data → 3 features → 4 edges → 5 strategies → 6 vetoes → 7 scoring/calibration → 8 CoinDCX — **9 backtest+ablation (গেট)** → 10 shadow ≥8 সপ্তাহ → 11 paper ≥100 সিগন্যাল → 12 controlled live।
**Phase 9 go condition:** full system-এর net expectancy > S1 একার net expectancy, এবং OOS degradation <40%। 실패하면 **S1 একার কাছে ফিরে যেতে হবে**।

## ২৪. Final Go/No-Go
**Go (শর্তসাপেক্ষ):** নতুন কোডবেস, spine = S1, veto-first, CoinDCX validation বাধ্যতামূলক, একক প্রসেস, Phase 9 gate।
**No-Go (চিরতরে):** legacy কোডবেস deploy, MARGE/auto execution, GEX routing, unvalidated probability display, multi-bot architecture।

---

## §19 প্রশ্নের সরাসরি উত্তর

1. **এক strategy না একাধিক engine?** একটি spine (S1) + confirmation plugs + regime gating — একাধিক স্বাধীন live engine নয়।
2. **শুরুতে কোন edge active?** E01, E03, E04, E07, E11, E12, E23, E24, E28 + X01–X04।
3. **কোনগুলো shadow?** E02, E05, E06, E10, E13, E15, E16, E17, E20, E21, E25।
4. **কোনগুলো experimental?** E08, E09, E14, E22, E27, এবং S3।
5. **কোনগুলো reject ও কেন?** E18 (microprice — ম্যানুয়াল ৫–১৫ মিনিট হরাইজনে অপ্রাসঙ্গিক), E19 (microbar — پیچیدگی বিনা লাভে), E26 (GEX — dealer sign যাচাইযোগ্য নয়)।
6. **বাধ্যতামূলক hard veto?** V-H01,02,03,05,08,09,12,15,17,19,22,31 (+H32)।
7. **বাধ্যতামূলক soft veto?** V-S01 (BTC conflict), V-S04 (funding extreme), V-S10 (late entry), V-S11 (weak order flow)।
8. **সেরা scoring architecture?** ৬ cluster, এক slot প্রতি cluster, cap মোট ১০০, RR bonus ≤4, probability আলাদা ও calibrated।
9. **সেরা regime architecture?** ৩টি স্বাধীন state variable (VR trend, ATR vol, liquidity stress) — mutually exclusive একক label নয়।
10. **live activation-এর ন্যূনতম প্রমাণ?** ≥300 resolved trade, walk-forward+OOS-এ net expectancy >0, bootstrap 5th pct >0, ablation-এ প্রতিটি active edge ইতিবাচক, ≥8 সপ্তাহ shadow-এ veto miss শূন্য।
11. **1 GB VPS-এ ফিট?** হ্যাঁ — ২২০ MB বাজেট, একক প্রসেস, bounded buffers।
12. **precision বাড়ানোর সবচেয়ে বাস্তব উপায়?** signal সংখ্যা কমানো নয় — **veto কঠোর করা + late-entry ব্লক + CoinDCX drift ব্লক + একই ঘটনায় duplicate সিগন্যাল নিষিদ্ধ করা**।
13. **প্রথমে কী বানাবেন?** Phase 2 data plane + integrity (কারণ বাকি সব ওটার উপর নির্ভরশীল)।
14. **কখনো কী বানাবেন না?** order placement, execution engine, AUTO/SEMI-AUTO, CoinDCX trading API key, GEX routing, uncalibrated probability।
