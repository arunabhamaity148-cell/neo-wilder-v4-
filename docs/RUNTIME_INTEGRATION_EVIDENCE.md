# NEO-WILDER V4 — রানটাইম ইন্টিগ্রেশন প্রমাণ ম্যাট্রিক্স (RUNTIME INTEGRATION EVIDENCE)

**তারিখ:** 2026-11-07  
**প্রজেক্ট:** NEO-WILDER V4 (End-to-End Single Asyncio Process Integration)  
**স্ট্যাটাস:** বাস্তবায়িত, এন্ড-টু-এন্ড টেস্টে প্রমাণিত এবং সম্পূর্ণ সংযুক্ত।

---

## ১. এন্ড-টু-এন্ড ডাটাফ্লো আর্কিটেকচার (Architecture Flow)

NEO-WILDER V4 একটি একক `asyncio` প্রসেসে নিচের ক্রম মেনে ডাটা প্রসেস করে:

```
[Binance WebSocket (kline_15m, trades, depth)]
                     │
                     ▼
       [Data Integrity Auditor (V-H01..V-H04)]
                     │
                     ▼
          [Feature Engine (Causal)]
    (ATR, Swings, Pools, Regime, CVD, OBI, VP, RSI, Funding, OI)
                     │
                     ▼
        [EdgeRunner (E01, E03, E04, E07, E11, E12, E23, E24, E28)]
                     │
                     ▼
   [S1 Strategy (Sweep & Reclaim - LONG Only, SHORT Abstain)]
                     │
                     ▼
      [VetoPipeline (34 Hard Vetoes + 15 Soft Vetoes)]
                     │
                     ▼
    [CompositeScorer (0-100 Score, Orthogonal Caps C1..C6)]
                     │
                     ▼
   [CoinDCX Execution Validator (0.35% Drift, Spread, Depth)]
                     │
                     ▼
 [PortfolioGovernor (Concurrency <= 2, Open Risk <= 3%, 30m Cooldown)]
                     │
                     ▼
   [Telegram Alert Publisher] ──► [SQLite WAL Persistence & Journal]
```

---

## ২. স্টেজ-বাই-স্টেজ ইন্টিগ্রেশন যাচাইকরণ ম্যাট্রিক্স

| স্টেজ নং | পাইপলাইন ধাপ | সংশ্লিষ্ট মডিউল | ইনপুট ডাটা | আউটপুট ডাটা | ইন্টিগ্রেশন স্ট্যাটাস | প্রমাণ ও টেস্ট রেফারেন্স |
|---|---|---|---|---|---|---|
| **১** | **স্টার্টআপ ও সিঙ্ক** | `main.py`, `clock.py`, `universe.py` | বাইন্যান্স REST সার্ভার টাইম, CoinDCX ইনস্ট্রুমেন্টস | ক্লক স্কিউ (<১০০০ms), সক্রিয় সিম্বল ইউনিভার্স | সম্পূর্ণ সংযুক্ত | `tests/unit/test_phase1_foundation.py::test_system_clock_sync` |
| **২** | **ওয়েবসকেট ইনজেস্ট** | `data/ws_binance.py` | `@kline_15m`, `@aggTrade`, `@depth20@100ms` | বাউন্ডেড রিংবাফার (ক্যান্ডেল, ট্রেড, বুক ডেপথ) | সম্পূর্ণ সংযুক্ত | `tests/unit/test_phase2_data.py::test_binance_ws_message_handling` |
| **৩** | **ডাটা ইন্টিগ্রিটি অডিট** | `data/integrity.py` | ক্লোজড ক্যান্ডেল সিরিজ | `V-H01` (ফ্রেশনেস), `V-H02` (গ্যাপ), `V-H03` (টাইমস্ট্যাম্প) | সম্পূর্ণ সংযুক্ত | `tests/unit/test_phase2_data.py::test_data_integrity_auditor_cases` |
| **৪** | **ফিচার এক্সট্র্যাকশন** | `features/*` | ক্যান্ডেল, ট্রেডস, বুক, ফান্ডিং, ওআই | সমন্বিত `FeatureContext` (ATR, Swings, CVD, OBI, RSI) | সম্পূর্ণ সংযুক্ত | `tests/unit/test_phase3_features.py` (১১টি টেস্ট পাস) |
| **৫** | **এজ ইভ্যালুয়েশন** | `edges/runner.py` | `FeatureContext` | `Dict[str, EdgeResult]` (E01, E03, E04, E07, E11, E12, E23, E24) | সম্পূর্ণ সংযুক্ত | `tests/unit/test_phase4_edges.py::test_edge_runner_execution_and_ablation` |
| **৬** | **ক্যান্ডিডেট জেনারেশন** | `strategies/s1_sweep_reclaim.py` | `FeatureContext`, `edge_results` | `Optional[Candidate]` (লং সেটআপ, স্টপ-লস, TP1) | সম্পূর্ণ সংযুক্ত | `tests/unit/test_phase5_strategies.py::test_s1_long_candidate_emission` |
| **৭** | **শর্ট সাইড ফেইল-ক্লোজড**| `strategies/s1_sweep_reclaim.py` | যেকোনো শর্ট কন্ডিশন | `None` (`ABSTAIN`) | সম্পূর্ণ সংযুক্ত | `tests/integration/test_end_to_end_runtime.py::test_short_strategy_fail_closed_at_runtime` |
| **৮** | **হার্ড ও সফট ভিটো** | `vetoes/pipeline.py`, `vetoes/hard.py` | ক্যান্ডিডেট, কোট, ফিচার, ক্লক, গভর্নর | `VetoResult` (পাস/ফেল, ব্লকিং আইডি, পেনাল্টি) | সম্পূর্ণ সংযুক্ত | `tests/unit/test_phase6_vetoes.py` (১০টি টেস্ট পাস) |
| **৯** | **স্কোরিং ও ক্যাপিং** | `scoring/groups.py` | অ্যাক্টিভ এজ রেজাল্টস, নেট R:R | কম্পোজিট স্কোর (০-১০০, C1+C2 <= ২৪) | সম্পূর্ণ সংযুক্ত | `tests/unit/test_phase7_scoring.py::test_scoring_cluster_caps_and_c1_c2_limit` |
| **১০** | **CoinDCX ভ্যালিডেশন** | `coindcx/validator.py` | CoinDCX লাইভ কোট, রেফারেন্স প্রাইস | এক্সিকিউশন ড্রিফট (<০.৩৫%), স্প্রেড ও ডেপথ যাচাই | সম্পূর্ণ সংযুক্ত | `tests/unit/test_phase9_coindcx_validation.py` (৬টি টেস্ট পাস) |
| **১১** | **পোর্টফোলিও গভর্নেন্স** | `vetoes/governor.py` | সিম্বল, ডিরেকশন, ওপেন রিস্ক | কনকারেন্সি সীমা (২), ওপেন রিস্ক (৩%), ৩০ মিনিট লক | সম্পূর্ণ সংযুক্ত | `tests/unit/test_phase6_vetoes.py::test_fresh_governor_unlocked_and_cooldown` |
| **১২** | **টেলিগ্রাম অ্যালার্ট** | `publish/telegram.py` | অনুমোদিত `Signal` | রেট-লিমিটেড টেলিগ্রাম ব্রডকাস্ট (/100 ফরম্যাট) | সম্পূর্ণ সংযুক্ত | `tests/unit/test_phase8_publish_journal.py::test_telegram_alert_formatting` |
| **১৩** | **ডাটাবেস পারসিস্টেন্স** | `data/store.py`, `journal/signals.py`| সিগন্যাল ও ফ্লি রেকর্ড | SQLite WAL টেবিলে অ্যাসিনক্রোনাস রাইট | সম্পূর্ণ সংযুক্ত | `tests/unit/test_phase2_data.py::test_database_store_wal_and_crud` |
| **১৪** | **আউটকাম ট্র্যাকিং** | `journal/outcomes.py` | পরবর্তী ১৫ মিনিটের ক্যান্ডেল | TP1 হিট / স্টপ-লস / টাইম-এক্সপায়ারি ট্র্যাকিং | সম্পূর্ণ সংযুক্ত | `tests/unit/test_phase8_publish_journal.py::test_outcome_resolver_intrabar_ambiguity` |
| **১৫** | **রিস্টার্ট রিকভারি** | `main.py`, `journal/outcomes.py` | ডেটাবেসে থাকা ওপেন সিগন্যাল | মেমরিতে ট্র্যাকার স্টেট পুনর্গঠন | সম্পূর্ণ সংযুক্ত | `tests/integration/test_end_to_end_runtime.py::test_end_to_end_runtime_pipeline` |

---

## ৩. ইন্টিগ্রেশন প্রমাণের সারাংশ

- **লাইভ পাইপলাইনে জিরো ডামি বা ভুয়া কোড:** পূর্ববর্তী অডিটে চিহ্নিত সমস্ত ভুয়া এজ ও হার্ডকোডেড মান সম্পূর্ণরূপে বাস্তবায়িত কম্পোনেন্ট দ্বারা প্রতিস্থাপিত হয়েছে।
- **ফেইল-ক্লোজড সেফটি গ্যারান্টি:** যেকোনো বহিরাগত ডেটা সোর্স (Binance WS, Binance REST, CoinDCX REST) অফলাইন বা স্টেল হলে সিস্টেম কোনো কাল্পনিক ডাটা ব্যবহার করে না, বরং তাৎক্ষণিকভাবে `ABSTAIN` করে সিগন্যাল বাতিল করে।
- **ইন-মেমরি ক্র্যাশ রেসিলিয়েন্স:** SQLite WAL মোড এবং স্টার্টআপ রিলোড মেকানিজম নিশ্চিত করে যে প্রসেস রিস্টার্ট হলেও কোনো সক্রিয় সিগন্যাল ট্র্যাক হারায় না।
