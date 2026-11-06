# NEO-WILDER V4 — পরীক্ষিত ও যাচাইকৃত ত্রুটি রেজিস্ট্রি (VERIFIED DEFECT REGISTER)

**তারিখ:** 2026-11-07  
**প্রজেক্ট:** NEO-WILDER V4  
**স্ট্যাটাস:** সকল P0, P1, P2 এবং P3 ত্রুটি যাচাই ও কোডে স্থায়ীভাবে সমাধান সম্পন্ন।

---

## ১. P0 প্রায়োরিটি ত্রুটিসমূহ (Critical Blockers — Resolved)

### DEF-01: WebSocket Client কখনোই স্টার্ট হতো না
- **তীব্রতা:** CRITICAL (P0)
- **সংশ্লিষ্ট ফাইল ও ফাংশন:** `src/neo_wilder/main.py:198` (`NeoWilderApplication.start()`)
- **মূল সমস্যা:** `main.py`-তে `self.ws_client` ইনিশিয়ালাইজ করা হলেও `await self.ws_client.start()` কখনোই কল করা হয়নি। ফলে কোনো মার্কেট ডেটা সিস্টেমে ঢুকত না।
- **প্রমাণ ও রিপ্রোডাকশন:** অরিজিনাল কোডে `grep` করে দেখা যায় শুধুমাত্র `stop()`-এ `ws_client.stop()` ছিল, কিন্তু `start()`-এ কোনো স্টার্ট কল ছিল না।
- **স্থায়ী সমাধান:** `NeoWilderApplication.start()`-এ `await self.ws_client.start()` যুক্ত করা হয়েছে এবং গ্রেসফুল শাটডাউনে `await self.ws_client.stop()` নিশ্চিত করা হয়েছে।
- **যাচাইকারী টেস্ট:** `tests/unit/test_phase14_deployment.py::test_application_initialization` এবং `tests/integration/test_end_to_end_runtime.py::test_end_to_end_runtime_pipeline`।

### DEF-02: `generate_candidate()` মেথডে `TypeError`
- **তীব্রতা:** CRITICAL (P0)
- **সংশ্লিষ্ট ফাইল ও ফাংশন:** `src/neo_wilder/main.py:330` ও `src/neo_wilder/strategies/s1_sweep_reclaim.py:27`
- **মূল সমস্যা:** `S1SweepReclaimStrategy.generate_candidate(ctx, edge_results)` দুটি পজিশনাল আর্গুমেন্ট প্রত্যাশা করে। কিন্তু `main.py`-তে শুধু `generate_candidate(ctx)` কল করা হতো। ফলে রানটাইমে `TypeError` ঘটত এবং ব্রড এক্সেপ্ট ব্লকে নীরব মৃত্যু হতো।
- **প্রমাণ ও রিপ্রোডাকশন:** `mypy` ত্রুটি: `Missing positional argument "edge_results" in call to "generate_candidate" of "S1SweepReclaimStrategy"`।
- **স্থায়ী সমাধান:** `main.py`-তে `EdgeRunner.evaluate_all()` সম্পাদন করে বাস্তব `edge_results` ডিকশনারি `generate_candidate`-এ ইনজেক্ট করা হয়েছে।
- **যাচাইকারী টেস্ট:** `tests/integration/test_end_to_end_runtime.py` এবং `tests/unit/test_phase5_strategies.py`।

### DEF-03: ভুয়া হার্ডকোডেড এজ রেজাল্টস
- **তীব্রতা:** CRITICAL (P0)
- **সংশ্লিষ্ট ফাইল ও ফাংশন:** `src/neo_wilder/main.py:275-297`
- **মূল সমস্যা:** লাইভ পাইপলাইনে বাস্তব `EdgeRunner` না চালিয়ে কোডে কৃত্রিমভাবে `E01`, `E03`, `E04`-এর জন্য `passed=True, confidence=1.0` হার্ডকোড করা ছিল। এটি অডিট প্রিন্সিপল ৭ ("No Fabricated Validation") সরাসরি লঙ্ঘন করেছিল।
- **প্রমাণ ও রিপ্রোডাকশন:** সোর্স কোডে স্পষ্ট কৃত্রিম এজ ডিকশনারি উপস্থিত ছিল।
- **স্থায়ী সমাধান:** সব হার্ডকোডেড ডামি অবজেক্ট মুছে ফেলা হয়েছে এবং সিস্টেমে রেজিস্টার্ড সমস্ত এজ বাস্তব `EdgeRunner`-এর মাধ্যমে রান করা নিশ্চিত করা হয়েছে।
- **যাচাইকারী টেস্ট:** `tests/unit/test_phase4_edges.py::test_edge_runner_execution_and_ablation`।

### DEF-04: লাইভ স্কোরের গাণিতিক অসম্ভবতা (Max Score 84 < 85 Threshold)
- **তীব্রতা:** CRITICAL (P0)
- **সংশ্লিষ্ট ফাইল ও ফাংশন:** `src/neo_wilder/main.py:300` ও `src/neo_wilder/scoring/groups.py`
- **মূল সমস্যা:** অরিজিনাল `main.py`-তে শুধু C3 ক্লাস্টারের এজ হার্ডকোড করা ছিল যার সর্বোচ্চ ক্যাপ ২০। বেস ৬০ + ২০ + ৪ (RR) = ৮৪, যা ডিফল্ট পাবলিশ থ্রেশহোল্ড ৮৫-এর চেয়ে কম। ফলে কোনো সিগন্যাল পাবলিশ হওয়া গাণিতিকভাবে অসম্ভব ছিল।
- **প্রমাণ ও রিপ্রোডাকশন:** স্বাধীন হ্যান্ড-ক্যালকুলেশন ও অডিট রিপোর্ট সেকশন A-তে প্রমাণিত।
- **স্থায়ী সমাধান:** লাইভ পাইপলাইনে বাস্তব `EdgeRunner` সংযুক্ত হওয়ায় অন্যান্য ক্লাস্টারও (যেমন C4 ও C5) স্কোর প্রদান করে, ফলে স্বাভাবিক ও যোগ্য সেটআপে স্কোর ১০০ পর্যন্ত পৌঁছাতে পারে।
- **যাচাইকারী টেস্ট:** `tests/unit/test_phase7_scoring.py::test_scoring_cluster_caps_and_c1_c2_limit`।

### DEF-05: ৫ মিনিট বনাম ১৫ মিনিট টাইমফ্রেম অমিল
- **তীব্রতা:** CRITICAL (P0)
- **সংশ্লিষ্ট ফাইল ও ফাংশন:** `src/neo_wilder/data/ws_binance.py:71,162` ও `src/neo_wilder/main.py:281`
- **মূল সমস্যা:** বাইন্যান্স ওয়েবসকেটে সাবস্ক্রাইব করা ছিল `@kline_5m`, কিন্তু `on_candle_close` মেথড `timeframe != "15m"` হলে রিটার্ন করে দিত। ফলে কোনো ক্যান্ডেল কখনো প্রসেস হতো না।
- **প্রমাণ ও রিপ্রোডাকশন:** ওয়েবসকেট স্ট্রিমে ১৫ মিনিটের ক্যান্ডেল ইভেন্ট না আসায় ডেটাফ্লো সম্পূর্ণ অচল ছিল।
- **স্থায়ী সমাধান:** `ws_binance.py`-তে স্ট্রিমে `@kline_15m` সাবস্ক্রিপশন যুক্ত করা হয়েছে এবং ১৫ মিনিটের ক্লোজড ক্যান্ডেল ডেলিভারি নিশ্চিত করা হয়েছে।
- **যাচাইকারী টেস্ট:** `tests/unit/test_phase2_data.py::test_binance_ws_message_handling`।

### DEF-06: `FeatureContext`-এ ডেরিভেটিভস ডেটার অভাব এবং `V-H11` ব্লকিং
- **তীব্রতা:** CRITICAL (P0)
- **সংশ্লিষ্ট ফাইল ও ফাংশন:** `src/neo_wilder/main.py:217` ও `src/neo_wilder/vetoes/hard.py:129`
- **মূল সমস্যা:** `FeatureContext`-এ শুধুমাত্র ক্যান্ডেল ও ATR পাস করা হতো। ফান্ডিং এবং ওপেন ইন্টারেস্ট সর্বদা খালি থাকায় `HardVetoEvaluator`-এর `V-H11` (Critical Source Down) প্রতি ক্যান্ডেলকে ফেইল-ক্লোজড ব্লক করে দিত।
- **প্রমাণ ও রিপ্রোডাকশন:** সোর্স ট্রেসিংয়ে দেখা যায় `funding_context` এবং `oi_snapshot` কখনো পপুলেট হতো না।
- **স্থায়ী সমাধান:** `NeoWilderApplication`-এ ব্যাকগ্রাউন্ড পলিং লুপ `_poll_derivatives_loop` বাস্তবায়ন করা হয়েছে যা বাইন্যান্স প্রিমিয়াম ইনডেক্স ও ওপেন ইন্টারেস্ট ক্যাশ আপডেট করে এবং ক্যান্ডেল ইভেন্টে পূর্ণাঙ্গ `FeatureContext` তৈরি করে।
- **যাচাইকারী টেস্ট:** `tests/integration/test_end_to_end_runtime.py` ও `tests/unit/test_risk_guard.py`।

### DEF-07: মনোটনিক আপটাইম কুলডাউন বাগ (`is_symbol_locked()`)
- **তীব্রতা:** CRITICAL (P0)
- **সংশ্লিষ্ট ফাইল ও ফাংশন:** `src/neo_wilder/vetoes/governor.py:48-52`
- **মূল সমস্যা:** `is_symbol_locked()` ফাংশনে নতুন সিম্বলের ক্ষেত্রে ডিফল্ট টাইম 0.0 ধরে `time.monotonic() - 0.0 < 1800` হিসাব করা হতো। যেসব সিস্টেমে আপটাইম ১৮০০ সেকেন্ডের কম (যেমন ফ্রেশ মেশিন বা কনটেইনার), সেখানে বুট করার পর প্রথম ৩০ মিনিট প্রতিটি সিম্বল লক থাকত। এটিই ছিল স্বাধীন অডিটের ৪টি টেস্ট ফেইলিউরের একক কারণ।
- **প্রমাণ ও রিপ্রোডাকশন:** `test_execution.log`-এ ৪টি টেস্টের প্রত্যেকটিতে `V-H24` (সিম্বল কুলডাউন) দ্বারা অপ্রত্যাশিত ব্লকিং ঘটেছিল।
- **স্থায়ী সমাধান:** `is_symbol_locked()` এবং `is_duplicate_signal()` মেথডে সিম্বল যদি ট্র্যাকারে না থাকে, তবে তাৎক্ষণিক `False` রিটার্ন করা নিশ্চিত করা হয়েছে। এছাড়া ডুপ্লিকেট সিগন্যাল ট্র্যাকার এবং সিম্বল লক ট্র্যাকার পৃথক ডিকশনারিতে ভাগ করা হয়েছে।
- **যাচাইকারী টেস্ট:** `tests/unit/test_phase6_vetoes.py::test_fresh_governor_unlocked_and_cooldown` এবং পূর্বে ফেইল হওয়া ৪টি টেস্ট এখন সম্পূর্ণ গ্রিন।

---

## ২. P1 প্রায়োরিটি ত্রুটিসমূহ (High Priority — Resolved)

### DEF-08: `SwingPivot.bar_index` বনাম `index` অ্যাট্রিবিউট ত্রুটি
- **তীব্রতা:** HIGH (P1)
- **সংশ্লিষ্ট ফাইল ও ফাংশন:** `src/neo_wilder/features/rsi.py:96-112` ও `src/neo_wilder/domain/models.py:114`
- **মূল সমস্যা:** `models.py`-তে ফিল্ডের নাম ছিল `index`, কিন্তু `rsi.py`-তে `s.bar_index` কল করায় রানটাইমে সাইলেন্ট `AttributeError` হতো এবং ডাইভারজেন্স কখনো হিসাব হতো না।
- **স্থায়ী সমাধান:** `SwingPivot`-এ `@property def bar_index(self) -> int: return self.index` এলিয়াস যোগ করা হয়েছে এবং `rsi.py`-তে `s.index` ব্যবহার নিশ্চিত করা হয়েছে।
- **যাচাইকারী টেস্ট:** `python -m mypy src/` (০ এরর) এবং `tests/unit/test_phase3_features.py::test_rsi_divergence_engine`।

### DEF-09: ফান্ডিং উইন্ডো পোস্ট-সেটেলমেন্ট বাউন্ডারি বাগ
- **তীব্রতা:** HIGH (P1)
- **সংশ্লিষ্ট ফাইল ও ফাংশন:** `src/neo_wilder/features/funding.py:60`
- **মূল সমস্যা:** সেটেলমেন্টের পরবর্তী উইন্ডো স্পেক অনুযায়ী +৫ মিনিট হওয়ার কথা থাকলেও কোডে `-6` মিনিটে (অর্থাৎ সেটেলমেন্টের ৬ মিনিট পরে) উইন্ডো `True` দেখাত।
- **স্থায়ী সমাধান:** লজিক সংশোধন করে `-5.0 <= minutes_to_settlement <= 15.0` করা হয়েছে।
- **যাচাইকারী টেস্ট:** `tests/unit/test_phase3_features.py::test_funding_engine`।

### DEF-10: লাইভ পাইপলাইনে হার্ড ভিটো ফ্ল্যাগ পাস না করা
- **তীব্রতা:** HIGH (P1)
- **সংশ্লিষ্ট ফাইল ও ফাংশন:** `src/neo_wilder/main.py:259` ও `src/neo_wilder/vetoes/pipeline.py`
- **মূল সমস্যা:** `is_orderbook_stale` এবং `is_ws_disconnected` লাইভ কোডে হার্ডকোডেড `False` পাঠানো হতো, ফলে স্টেল অর্ডারবুক চেক নিষ্ক্রিয় থাকত।
- **স্থায়ী সমাধান:** অর্ডারবুক আপডেটের টাইমস্ট্যাম্প মনিটর করে বয়স ৩ সেকেন্ডের বেশি হলে `is_orderbook_stale=True` এবং ওয়েবসকেট ডাউন থাকলে `is_ws_disconnected=True` পাইপলাইনে পাস করা হয়েছে।
- **যাচাইকারী টেস্ট:** `tests/unit/test_phase6_vetoes.py::test_v_h06_orderbook_stale_blocks`।

### DEF-11: সফট ভিটো প্লেসহোল্ডার ও দ্বিমুখী লজিক
- **তীব্রতা:** HIGH (P1)
- **সংশ্লিষ্ট ফাইল ও ফাংশন:** `src/neo_wilder/vetoes/soft.py:52-160`
- **মূল সমস্যা:** ৬টি সফট ভিটোতে শুধু `pass` ছিল এবং `V-S10` ও `V-S11` শর্ট সাইডে ভুল পেনাল্টি প্রয়োগ করত।
- **স্থায়ী সমাধান:** লং ও শর্টের জন্য প্রতিসম চেক বাস্তবায়ন করা হয়েছে এবং `V-S02`, `V-S03`, `V-S05`, `V-S07`, `V-S08`, `V-S09`, `V-S11`, `V-S12`, `V-S15` পূর্ণাঙ্গভাবে সক্রিয় করা হয়েছে।
- **যাচাইকারী টেস্ট:** `tests/unit/test_phase6_vetoes.py::test_v_s11_weak_orderflow_confidence_penalty`।

### DEF-12: আউটকাম ট্র্যাকার রিস্টার্ট রিকভারি
- **তীব্রতা:** HIGH (P1)
- **সংশ্লিষ্ট ফাইল ও ফাংশন:** `src/neo_wilder/journal/outcomes.py` ও `src/neo_wilder/data/store.py`
- **মূল সমস্যা:** বট রিস্টার্ট নিলে মেমরিতে থাকা ওপেন পজিশন ট্র্যাকার মুছে যেত, ফলে ডেটাবেসে থাকা অমীমাংসিত সিগন্যাল ট্র্যাক হতো না।
- **স্থায়ী সমাধান:** `store.py`-তে `fetch_unresolved_signals()` মেথড তৈরি করে `OutcomeResolver.reload_unresolved_signals()`-এর মাধ্যমে স্টার্টআপে মেমরিতে ট্র্যাকার পুনর্গঠন নিশ্চিত করা হয়েছে।
- **যাচাইকারী টেস্ট:** `tests/integration/test_end_to_end_runtime.py`।

### DEF-13: রেজিস্ট্রি ও কোড স্ট্যাটাস বাউন্ডারি রক্ষা
- **তীব্রতা:** HIGH (P1)
- **সংশ্লিষ্ট ফাইল ও ফাংশন:** `src/neo_wilder/edges/registry.py` ও `docs/KNOWN_LIMITATIONS.md`
- **মূল সমস্যা:** ১১টি রেজিস্ট্রি এজ কোডে সক্রিয় ছিল না, অথচ কোনো কোনো ডকুমেন্টে ভুলভাবে সেগুলোকে ইমপ্লিমেন্টেড দাবি করা হয়েছিল।
- **স্থায়ী সমাধান:** স্পষ্ট ফেইল-ক্লোজড নীতি বজায় রেখে `E21` ও `S2` শ্যাডো মোডে সীমিত রাখা হয়েছে এবং কোনো মিসিং ফর্মুলা বা এজ অ্যাক্টিভ স্কোরে প্রবেশ করতে দেওয়া হয়নি।
- **যাচাইকারী টেস্ট:** `tests/unit/test_phase1_foundation.py::test_edge_registry_completeness`।

---

## ৩. P2 ও P3 ত্রুটিসমূহ (Medium / Operational — Resolved)

### DEF-14: CoinDCX ভিটো আইডি রেজিস্ট্রি মিসম্যাচ
- **তীব্রতা:** MEDIUM (P2)
- **সংশ্লিষ্ট ফাইল:** `src/neo_wilder/coindcx/validator.py:99-154`
- **স্থায়ী সমাধান:** রেজিস্ট্রি মেনে স্প্রেডকে `V-H12`, ডেপথকে `V-H13`, ড্র্রিফটকে `V-H32` এবং কোট অনুপুস্থিতিকে `V-H31`-এ পুনঃসংযোজিত করা হয়েছে।
- **যাচাইকারী টেস্ট:** `tests/unit/test_phase9_coindcx_validation.py` (৬/৬ পাস)।

### DEF-15: ডাটাবেস রাইটার লুপ `task_done()` ব্যালান্স
- **তীব্রতা:** MEDIUM (P2)
- **সংশ্লিষ্ট ফাইল:** `src/neo_wilder/data/store.py:95`
- **স্থায়ী সমাধান:** `try...finally` ব্লকের মধ্যে `batch.clear()` এবং `task_done()` নিশ্চিত করা হয়েছে এবং `fetch_recent_candles_async()` মেথডে `asyncio.to_thread` ব্যবহার করে ইভেন্ট-লুপ ব্লকিং দূর করা হয়েছে।
- **যাচাইকারী টেস্ট:** `tests/unit/test_phase2_data.py::test_database_store_wal_and_crud`।

### DEF-16: সিগন্যাল মেটাডাটা ও এক্সপায়ারি টাইমিং
- **তীব্রতা:** MEDIUM (P2)
- **সংশ্লিষ্ট ফাইল:** `src/neo_wilder/main.py:321`
- **স্থায়ী সমাধান:** `expires_at_utc = created_at + timedelta(minutes=candidate.expiry_bars * 15)` এবং সক্রিয় সফট ভিটো তালিকা মেটাডেটায় সংযুক্ত করা হয়েছে।
- **যাচাইকারী টেস্ট:** `tests/unit/test_phase1_foundation.py::test_signal_schema_invariants`।

### DEF-17: রিস্ক গার্ড ও হার্ড ভিটো ডেপথ থ্রেশহোল্ড একীকরণ
- **তীব্রতা:** MEDIUM (P2)
- **সংশ্লিষ্ট ফাইল:** `src/neo_wilder/vetoes/hard.py` ও `src/neo_wilder/vetoes/risk_guard.py`
- **স্থায়ী সমাধান:** একক কনফিগারেশন মান (500 USD) ব্যবহার নিশ্চিত করা হয়েছে।
- **যাচাইকারী টেস্ট:** `tests/integration/test_risk_guard_integration.py`।

### DEF-18: কনফিগারেশন লোডার বাস্তবায়ন
- **তীব্রতা:** MEDIUM (P2)
- **সংশ্লিষ্ট ফাইল:** `src/neo_wilder/config.py`
- **স্থায়ী সমাধান:** `config/base.yaml` ও `thresholds.yaml` রিড করে টাইপ-সেফ ডাটা মডেলে সরবরাহকারী `load_config()` লোডার তৈরি করা হয়েছে।
- **যাচাইকারী টেস্ট:** `tests/unit/test_phase14_deployment.py`।

### DEF-19: রেজিম ক্লাসিফায়ার সিঙ্গেলটন হিস্টেরেসিস
- **তীব্রতা:** LOW (P3)
- **সংশ্লিষ্ট ফাইল:** `src/neo_wilder/main.py`
- **স্থায়ী সমাধান:** প্রতি ক্যান্ডেল ইভেন্টে নতুন অবজেক্ট তৈরি না করে অ্যাপ্লিকেশনের লাইফসাইকেলে একবার ইনিশিয়ালাইজ করা ক্লাসিফায়ার ব্যবহার করা হয়েছে।
- **যাচাইকারী টেস্ট:** `tests/unit/test_phase3_features.py::test_regime_classifier`।

### DEF-20: সিস্টেমড স্যান্ডবক্সিং ও ডিস্ক স্পেস নিরাপত্তা
- **তীব্রতা:** LOW (P3)
- **সংশ্লিষ্ট ফাইল:** `deploy/neo-wilder.service`
- **স্থায়ী সমাধান:** `MemoryMax=400M`, `CPUQuota=150%`, `NoNewPrivileges=true` নির্দেশিকা নিশ্চিত করা হয়েছে।
- **যাচাইকারী টেস্ট:** `tests/unit/test_phase14_deployment.py::test_systemd_service_unit`।
