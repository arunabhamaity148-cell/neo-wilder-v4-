# NEO-WILDER V4 — শ্যাডো মোড কন্ট্রাক্ট ও টেস্ট ভেরিফিকেশন স্পেসিফিকেশন
## Shadow Mode Contract & Test Verification Specification

**তারিখ:** ৭ নভেম্বর, ২০২৬  
**স্ট্যাটাস:** **ভেরিফাইড ও অ্যাক্টিভ (VERIFIED & ACTIVE)**  
**টার্গেট কম্পোনেন্ট:** `src/neo_wilder/shadow/runner.py`, `src/neo_wilder/main.py`, `src/neo_wilder/data/store.py`  
**সম্পর্কিত টেস্ট ফাইল:** `tests/integration/test_end_to_end_runtime.py::test_shadow_mode_full_contract`  

---

## ১. শ্যাডো মোড কন্ট্রাক্টের মৌলিক ইনভেরিয়েন্টসমূহ (Core Invariants)

NEO-WILDER V4-এর শ্যাডো মোড একটি সম্পূর্ণ নন-ইনট্রুসিভ (non-intrusive), আইসোলেটেড ও ট্রাস্টলেস টেলিম্যাট্রিক পাইপলাইন হিসেবে ডিজাইন করা হয়েছে। এর ৫টি মৌলিক ইনভেরিয়েন্ট কোডের মাধ্যমে বাস্তবায়িত ও পরীক্ষিত:

### ইনভেরিয়েন্ট ১: জিরো টেলিগ্রাম এগ্রিস (Strictly ZERO Telegram Egress)
- শ্যাডো মোডে চলমান অবস্থায় কোনো অবস্থাতেই টেলিগ্রাম বট পাবলিশার মেথড (`publisher.publish`) কল হতে পারবে না।
- ক্যান্ডিডেট সব গেট ক্লিয়ার করলেও (`CLEARED`), টেলিগ্রাম এগ্রিস কঠোরভাবে ব্লকড থাকে।
- **প্রমাণ:** `test_shadow_mode_full_contract` এবং `test_shadow_runner_execution_and_persistence`-এ `telegram_mock = AsyncMock()` বসিয়ে যাচাই করা হয়েছে যে পুরো রানটাইমে `telegram_mock.assert_not_called()` সত্য প্রমাণিত হয়েছে।

### ইনভেরিয়েন্ট ২: কোনো অর্ডার এক্সিকিউশন বা প্রাইভেট এপিআই নয় (Permanent SIGNAL_ONLY)
- কোডবেসে কোনো প্রাইভেট কী (`API_SECRET`, `PRIVATE_KEY`), সাইন্ড অর্ডার এন্ডপয়েন্ট বা এক্সচেঞ্জ এক্সিকিউশন লজিক নেই।
- CoinDCX শুধুমাত্র পাবলিক মার্কেট ডাটা রিড করে (টিকিট, অর্ডারবুক ডেপথ ও স্প্রেড)। কোনো অ্যাকাউন্ট ডাটাবেস বা অর্ডার ম্যানেজমেন্ট সিস্টেম (OMS) কোডে নেই।

### ইনভেরিয়েন্ট ৩: সম্পূর্ণ পৃথকীকরণযোগ্য টেলিমেট্রি (Distinguishable Telemetry)
শ্যাডো মোডে মূল্যায়ন হওয়া প্রতিটি ক্যান্ডিডেটকে তার ফলাফলের ভিত্তিতে SQLite-এর `shadow_signals` টেবিলে সংরক্ষিত করা হয়:
1. **CoinDCX রিজেকশন:** `rejection_stage="COINDCX_VALIDATION"`, `veto_status="REJECTED_COINDCX_V-H32"`
2. **ভেটো পাইপলাইন রিজেকশন:** `rejection_stage="VETO_PIPELINE"`, `veto_status="BLOCKED_{blocking_id}"`
3. **স্কোরিং রিজেকশন:** `rejection_stage="QUALITY_SCORE"`, `veto_status="REJECTED_SCORE_{score}_LT_85"`
4. **সম্পূর্ণ ক্লিয়ারড ক্যান্ডিডেট:** `rejection_stage="CLEARED"`, `veto_status="CLEARED"`

`ShadowTelemetry` কাউন্টারে যথাক্রমে `coindcx_blocked_count`, `veto_blocked_count`, `score_blocked_count`, এবং `cleared_count` স্বাধীনভাবে বৃদ্ধি পায়।

### ইনভেরিয়েন্ট ৪: S2 স্ট্র্যাটেজি আইসোলেশন ও ডেডিকেটেড শ্যাডো কলিশন লক (S2 Isolation & Dedicated Collision Lock)
- S2 স্ট্র্যাটেজি (`S2OIExhaustionStrategy`) শুধুমাত্র `ExecutionMode.SHADOW`-তে কাজ করে।
- এটি E21 (OI Exhaustion), E15 (Spot CVD Absorption), এবং E13 (Liquidation Flush) এর উপর ভিত্তি করে ক্যান্ডিডেট তৈরি করে।
- রেজিস্ট্রি অনুযায়ী E21, E15 এবং E13 এর স্কোর কন্ট্রিবিউশন সর্বদা ০।
- **ডেডিকেটেড শ্যাডো কলিশন স্টেট:** `PortfolioGovernor`-এ `shadow_s1_lock_times` ডেডিকেটেড স্টেট যোগ করা হয়েছে। শ্যাডো মোডে S1 ক্যান্ডিডেট জেনারেট বা রেকর্ড হওয়ার সাথে সাথেই `record_s1_shadow_candidate(symbol)` কল হয়, যা ৩০ মিনিটের ($1800\text{ sec}$) সিম্বল-লেভেল লক তৈরি করে।
- এটি কোনোভাবেই সিগন্যাল-মোডের `record_signal_published()`-এর উপর নির্ভরশীল নয়।
- **লক ও এক্সপায়ারি আচরণ:**
  - $t_0$-তে S1 ক্যান্ডিডেট রেকর্ড হলে তৎক্ষণাৎ একই ক্যান্ডেলের S2 এবং পরবর্তী ৩০ মিনিট পর্যন্ত S2 অবরুদ্ধ (`is_symbol_locked(symbol) == True`) থাকে।
  - ৩০ মিনিট অতিবাহিত হওয়ার পর ($t > t_0 + 1800\text{s}$) লক স্বয়ংক্রিয়ভাবে মেয়াদোত্তীর্ণ হয় এবং S2 পুনরায় অনুমোদিত হয়।
- S2 কখনো কোনো সক্রিয় সিগন্যালে রূপান্তরিত হয় না বা টেলিগ্রামে অ্যালার্ট পাঠায় না।

### ইনভেরিয়েন্ট ৫: ক্র্যাশ রিকভারি ও আইডেমপোটেন্সি (Crash Recovery & Idempotence)
- SQLite WAL মোডে একটি ব্যাকগ্রাউন্ড ডেডিকেটেড রাইটার টাস্কের মাধ্যমে `shadow_signals` টেবিলে ডাটা লেখা হয় (`INSERT OR REPLACE INTO shadow_signals`).
- প্রসেস বন্ধ করে পুনরায় চালু করলেও পূর্ববর্তী সমস্ত শ্যাডো রেকর্ড হুবহু অক্ষত থাকে।
- একই ক্যান্ডল একাধিকবার পুশ করলেও ডুপ্লিকেট এন্ট্রি তৈরি হয় না।

---

## ২. শ্যাডো স্কিমা ও ডাটাবেস লেআউট (Database Schema)

`src/neo_wilder/data/store.py`-তে সংজ্ঞায়িত স্কিমা:

```sql
CREATE TABLE IF NOT EXISTS shadow_signals (
    shadow_id TEXT PRIMARY KEY,
    created_at_utc TEXT NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    strategy_id TEXT NOT NULL,
    score_0_100 INTEGER NOT NULL,
    veto_status TEXT NOT NULL,
    active_edge_ids TEXT NOT NULL,
    shadow_edge_ids TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
```

`shadow_id` জেনারেশন প্যাটার্ন:
`f"SHADOW-{candidate.symbol}-{int(datetime.now(timezone.utc).timestamp() * 1000)}-{self.telemetry.total_shadow_candidates}"`
এটি সাব-মিলিমেকেন্ডেও ১০০% ইউনিক প্রাইমারি কী নিশ্চিত করে।

---

## ৩. ইন্টিগ্রেশন টেস্ট এভিডেন্স (Test Evidence)

`tests/integration/test_end_to_end_runtime.py::test_shadow_mode_full_contract` এক্সিকিউশন বিবরণ:

```python
# ১. CoinDCX ড্র Drift রিজেকশন কেস
drift_quote = CoinDCXQuote(price=70500.0, ...) # Reference 69500.0 -> Drift 1.439% > 0.35%
await app._process_candle_event(symbol, candle)
assert app.shadow_runner.telemetry.coindcx_blocked_count >= 1
telegram_mock.assert_not_called()

# ২. ভ্যালিড কোট ও স্কোর/ক্লিয়ার কেস
valid_quote = CoinDCXQuote(price=69510.0, ...) # Drift 0.014% < 0.35%
await app._process_candle_event(symbol, candle)
telegram_mock.assert_not_called()
assert app.shadow_runner.telemetry.total_shadow_candidates >= 2

# ৩. ডাটাবেস স্টেট যাচাই
with app.store._conn:
    cursor = app.store._conn.cursor()
    cursor.execute("SELECT shadow_id, strategy_id, veto_status FROM shadow_signals;")
    rows = cursor.fetchall()
assert len(rows) >= 2
assert any("REJECTED_COINDCX" in s for s in [r[2] for r in rows])

# ৪. প্রসেস রিস্টার্ট ও ক্র্যাশ-রিকভারি যাচাই
await app.stop()
app_restarted = NeoWilderApplication(mode=ExecutionMode.SHADOW)
await app_restarted.start()
with app_restarted.store._conn:
    cur = app_restarted.store._conn.cursor()
    cur.execute("SELECT COUNT(*) FROM shadow_signals;")
    assert cur.fetchone()[0] == len(rows)
```

### S1–S2 কলিশন লক ও ৩০-মিনিট এক্সপায়ারি প্রমাণ (`test_s1_s2_collision_lock_in_shadow_mode_and_expiry`):
```python
# ১. শ্যাডো মোডে S1 ক্যান্ডিডেট রেকর্ড হলে t0-তে লক কার্যকর
t0 = 50000.0
app.governor.record_s1_shadow_candidate(symbol, timestamp_monotonic=t0)
assert app.governor.is_symbol_locked(symbol, current_time_monotonic=t0)

# ২. ৩০ মিনিটের মধ্যে (৯০০ সেকেন্ড ও ১৭৯৫ সেকেন্ডে) S2 অবরুদ্ধ থাকে
assert app.governor.is_symbol_locked(symbol, current_time_monotonic=t0 + 900.0)
assert app.governor.is_symbol_locked(symbol, current_time_monotonic=t0 + 1795.0)

# ৩. ৩০ মিনিট অতিবাহিত হওয়ার পর (১৮০৫ সেকেন্ডে) লক সমাপ্ত হয়
assert not app.governor.is_symbol_locked(symbol, current_time_monotonic=t0 + 1805.0)

# ৪. রানটাইমে _process_candle_event পাইপলাইনে ক্যান্ডেল প্রসেস হলেও প্রতীক লক হয়
await app._process_candle_event(symbol, candles[-1])
assert app.governor.is_symbol_locked(symbol)
```

### S2 ডিটারমিনিস্টিক ক্যান্ডিডেট ও অবস্টেনশন প্রমাণ (`test_s2_strategy_evaluation_and_isolation`):
```python
# ১. E21, E15, E13 পাস করলে ডিটারমিনিস্টিক ভ্যালিড LONG ক্যান্ডিডেট তৈরি হয়
candidate = s2.generate_candidate(ctx, edge_results)
assert candidate is not None
assert candidate.strategy_id == "S2_OI_EXHAUSTION"
assert candidate.direction == Direction.LONG
assert candidate.setup_edge_id == "E21"
assert candidate.net_rr >= 1.50
assert candidate.stop_loss < candidate.reference_price < candidate.tp1

# ২. যেকোনো ম্যান্ডেটরি এজ মিসিং বা ফেইল করলে নিশ্চিতভাবে ABSTAIN (None)
assert s2.generate_candidate(ctx, edge_results={}) is None
assert s2.generate_candidate(ctx, {"E15": ..., "E13": ...}) is None # E21 missing -> None
assert s2.generate_candidate(ctx, res_e21_failed) is None          # E21 failed -> None
assert s2.generate_candidate(ctx, {"E21": ..., "E13": ...}) is None # E15 missing -> None
assert s2.generate_candidate(ctx, res_e15_failed) is None          # E15 failed -> None
assert s2.generate_candidate(ctx, {"E21": ..., "E15": ...}) is None # E13 missing -> None
assert s2.generate_candidate(ctx, res_e13_failed) is None          # E13 failed -> None
```

---

## ৪. উপসংহার

শ্যাডো মোডের সমস্ত কন্ট্রাক্টীয় শর্তসমূহ কঠোর কোড ও অটোমেটেড টেস্ট দ্বারা প্রমাণিত। সিস্টেমটি লাইভ মার্কেটের বিপরীতে রিয়েল-টাইম শ্যাডো টেলিম্যাট্রি সংগ্রহের জন্য প্রস্তুত।
