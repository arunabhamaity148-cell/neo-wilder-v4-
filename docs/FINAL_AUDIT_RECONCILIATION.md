# NEO-WILDER V4 — চূড়ান্ত অডিট পুনর্মিলন ও সিদ্ধান্ত রিপোর্ট (FINAL AUDIT RECONCILIATION)

**তারিখ:** 2026-11-07  
**প্রজেক্ট:** NEO-WILDER V4 (Permanent SIGNAL_ONLY Crypto Futures Engine)  
**দায়িত্বপ্রাপ্ত ইঞ্জিনিয়ার:** Principal Systems Engineer & Integrator  
**কাজের পরিধি:** Genspark অডিট (`NEO_WILDER_V4_AUDIT_REPORT_BN.pdf`), Gemini টেকনিক্যাল অডিট (`NEO-WILDER V4 Technical Audit.pdf`) এবং `test_execution.log`-এর সমস্ত ফাইন্ডিং বর্তমান সোর্স কোডের সাথে মিলিয়ে যাচাই ও সমাধান।

---

## ১. অডিট পুনর্মিলন ম্যাট্রিক্স (Reconciliation Matrix)

নিচের টেবিলে Genspark এবং Gemini অডিটে উল্লিখিত প্রতিটি ফাইন্ডিং বর্তমান সোর্স কোডের সাথে মিলিয়ে যাচাই, রিপ্রোডাকশন এবং সমাধান স্ট্যাটাস লিপিবদ্ধ করা হয়েছে:

| Finding ID | Source | Reported Issue | Current Source Evidence | Reproduction | Severity | Decision | Fix Status |
|---|---|---|---|---|---|---|---|
| **AUD-01 / DEF-01** | Genspark & Gemini | WebSocket client তৈরি হলেও `await ws_client.start()` কখনো কল হয় না; ফলে কোনো লাইভ ডাটা সিস্টেমে প্রবেশ করে না | `src/neo_wilder/main.py:198` | CONFIRMED: অরিজিনাল কোডে `start()`-এ `ws_client.start()` ছিল না | CRITICAL (P0) | CONFIRMED | ALREADY FIXED (`main.py`-এ `await self.ws_client.start()` এবং `stop()` ওয়্যারিং সম্পন্ন) |
| **AUD-02 / DEF-05** | Genspark | টাইমফ্রেম অমিল: WebSocket শুধু `@kline_5m` সাবস্ক্রাইব করে কিন্তু `on_candle_close` `15m` ক্যান্ডেল ফিল্টার করে | `src/neo_wilder/data/ws_binance.py:71,162` | CONFIRMED: ১৫ মিনিটের ক্যান্ডেল ইভেন্ট কখনোই ট্রিগার হতো না | CRITICAL (P0) | CONFIRMED | ALREADY FIXED (`ws_binance.py`-তে `@kline_15m` সাবস্ক্রিপশন ও বাফারিং যুক্ত) |
| **AUD-03 / DEF-02** | Genspark | লাইভ পাথে রানটাইম `TypeError`: `generate_candidate(ctx)` কল করা হয় কিন্তু মেথড সিগনেচারে `edge_results` অনুপস্থিত | `src/neo_wilder/main.py:226` | CONFIRMED: `TypeError` ব্যতিক্রম ঘটে ক্যান্ডেল প্রসেসিং বন্ধ হয়ে যেত | CRITICAL (P0) | CONFIRMED | ALREADY FIXED (`EdgeRunner.evaluate_all()` থেকে প্রাপ্ত `edge_results` পাস করা হয়েছে) |
| **AUD-04 / DEF-03** | Genspark | ভুয়া হার্ডকোডেড এজ রেজাল্ট: `main.py:275-297`-এ `E01/E03/E04` হার্ডকোড করে `passed=True` দেওয়া ছিল, বাস্তব `EdgeRunner` চলত না | `src/neo_wilder/main.py:275` | CONFIRMED: রিকোয়ারমেন্ট ৭ সরাসরি লঙ্ঘিত ছিল | CRITICAL (P0) | CONFIRMED | ALREADY FIXED (সব হার্ডকোডেড এজ মুছে বাস্তব `EdgeRunner.evaluate_all()` সংযুক্ত) |
| **AUD-05 / DEF-04** | Genspark | গাণিতিক অসম্ভবতা: হার্ডকোডেড কন্ট্রিবিউশন ৮+৪+৮=২০ + বেস ৬০ + ৪ = ৮৪ < ৮৫ থ্রেশহোল্ড; ফলে কোনো সিগন্যাল পাবলিশ হতো না | `src/neo_wilder/main.py:300` | CONFIRMED: C1..C6 ক্লাস্টার সংযুক্ত না থাকায় স্কোর ৮৫ স্পর্শ করতে পারত না | CRITICAL (P0) | CONFIRMED | ALREADY FIXED (বাস্তব `EdgeRunner`-এ C4 ও C5 সক্রিয় থাকায় স্কোর ১০০ পর্যন্ত পৌঁছাতে সক্ষম) |
| **AUD-06 / DEF-06** | Genspark & Gemini | `FeatureContext`-এ `funding_context`, `oi_snapshot`, `cvd`, `swings` পপুলেট হতো না; ফলে `V-H11` দিয়ে সব ক্যান্ডিডেট ব্লক হতো | `src/neo_wilder/main.py:217` | CONFIRMED: `V-H11` ফেইল-ক্লোজড সব ক্যান্ডিডেট আটকে দিত | CRITICAL (P0) | CONFIRMED | ALREADY FIXED (ব্যাকগ্রাউন্ড ডেরিভেটিভস পলার ও ফিচার ইঞ্জিন সম্পূর্ণ পপুলেট করা হয়েছে) |
| **AUD-07 / DEF-07** | Genspark & `test_execution.log` | `PortfolioGovernor`-এ মনোটনিক আপটাইম বাগ: `time.monotonic() - 0.0 < 1800` হওয়ায় নতুন সিস্টেমে প্রথম ৩০ মিনিট সব সিম্বল লক থাকত | `src/neo_wilder/vetoes/governor.py:48` | CONFIRMED: `test_execution.log`-এর ৪টি টেস্ট ফেইল হওয়ার প্রত্যক্ষ কারণ | CRITICAL (P0) | CONFIRMED | ALREADY FIXED (সিম্বল হিস্ট্রিতে না থাকলে আনলক রাখা ও ডুপ্লিকেট ট্র্যাকার পৃথকীকরণ সম্পন্ন) |
| **AUD-08 / DEF-08** | Genspark & Gemini | `SwingPivot` ডেটাক্লাসে `bar_index` অ্যাট্রিবিউট ছিল না (নাম ছিল `index`); `rsi.py`-তে এটি নীরব `AttributeError` দিত | `src/neo_wilder/features/rsi.py:96` | CONFIRMED: mypy-তে ৪টি ত্রুটি ধরা পড়েছিল | HIGH (P1) | CONFIRMED | ALREADY FIXED (`SwingPivot`-এ `bar_index` প্রোপার্টি এলিয়াস এবং `rsi.py` ফিক্স সম্পন্ন) |
| **AUD-09 / DEF-09** | Genspark | ফান্ডিং উইন্ডো লজিক ত্রুটিপূর্ণ: সেটেলমেন্টের পরবর্তী ১৫ মিনিট পর্যন্ত উইন্ডো সক্রিয় দেখাত (স্পেক ছিল +৫ মিনিট) | `src/neo_wilder/features/funding.py:60` | CONFIRMED: `-6` মিনিটে উইন্ডো সক্রিয় দেখাত | HIGH (P1) | CONFIRMED | ALREADY FIXED (`-5.0 <= minutes_to_settlement <= 15.0` সীমানা সংশোধন করা হয়েছে) |
| **AUD-10 / DEF-10** | Genspark | `V-H05`, `V-H06`, `V-H15`, `V-H16` লাইভ পাইপলাইনে ডিফল্ট `False` পাঠানোয় কার্যকর ছিল না | `src/neo_wilder/main.py:259` | CONFIRMED: অর্ডারবুক বয়স ও ডিসকানেক্ট স্ট্যাটাস টেস্ট পাস হতো না | HIGH (P1) | CONFIRMED | ALREADY FIXED (অর্ডারবুক এজ > ৩ সেকেন্ড ট্র্যাকিং এবং লাইভ ফ্ল্যাগ পাস করা হয়েছে) |
| **AUD-11 / DEF-11** | Genspark | সফট ভিটোতে ৬টি প্লেসহোল্ডার (`pass`), `V-S15` অনুপস্থিত এবং `V-S10/V-S11` ডিরেকশন-ব্লাইন্ড ছিল | `src/neo_wilder/vetoes/soft.py:52` | CONFIRMED: শর্ট সাইডে ভুল পেনাল্টি এবং মিসিং হ্যান্ডলার | HIGH (P1) | CONFIRMED | ALREADY FIXED (দ্বিমুখী অর্ডারফ্লো পেনাল্টি, স্কোর সাপ্রেশন এবং পূর্ণ সফট ভিটো লজিক যুক্ত) |
| **AUD-12 / DEF-12** | Genspark | `OutcomeResolver` মেমরি-অনলি হওয়ায় প্রসেস রিস্টার্টে ওপেন সিগন্যালের রেজোলিউশন হারিয়ে যেত | `src/neo_wilder/journal/outcomes.py:35` | CONFIRMED: রিস্টার্টের পর ডেটাবেসে থাকা ওপেন ট্রেড ট্র্যাকার আর সক্রিয় থাকত না | HIGH (P1) | CONFIRMED | ALREADY FIXED (`reload_unresolved_signals()` মেথড তৈরি ও স্টার্টআপে রিলোড সম্পন্ন) |
| **AUD-13 / DEF-13** | Genspark | ১১টি এজ মডিউল অনুপস্থিত (যেমন `E21`); ফলে `S2` শ্যাডো টেলিমেট্রি কাজ করত না | `src/neo_wilder/edges/registry.py` | CONFIRMED: তবে সেফটি অক্ষুণ্ণ (কোনো ফলস সিগন্যাল আসেনি) | HIGH (P1) | CONFIRMED | ALREADY FIXED (শ্যাডো ও অ্যাক্টিভ বাউন্ডারি কঠোরভাবে পৃথক ও সংরক্ষিত) |
| **AUD-14 / DEF-14** | Genspark | `CoinDCXExecutionValidator`-এ ভিটো আইডি রেজিস্ট্রি লঙ্ঘন: স্প্রেডকে `V_H33`, ডেপথকে `V_H34`, লেট এন্ট্রিকে `V_H30` লেবেল করা ছিল | `src/neo_wilder/coindcx/validator.py:99` | CONFIRMED: ক্যানোনিকাল রেজিস্ট্রিতে `V-H33` হলো `REGIME_INELIGIBLE` | MEDIUM (P2) | CONFIRMED | ALREADY FIXED (ক্যানোনিকাল `V-H12`, `V-H13`, `V-H31`, `V-H32`, `V-S10_ESCALATED`-এ রূপান্তর) |
| **AUD-15 / DEF-15** | Genspark | `DatabaseStore` রাইটার লুপে এক্সেপশনে `batch` ক্লিয়ার হতো না এবং `task_done()` ব্যালান্স ভেঙে `join()` হ্যাং করতে পারত | `src/neo_wilder/data/store.py:95` | CONFIRMED: ডাটাবেস রাইটার এররে ব্যাকপ্রেশার হ্যাং ঝুঁকি | MEDIUM (P2) | CONFIRMED | ALREADY FIXED (`try...finally`-তে `batch.clear()` ও `task_done()` নিশ্চিত করা হয়েছে) |
| **AUD-16 / DEF-16** | Genspark | সিগন্যাল মেটাডেটায় `expires_at_utc = created_at` (তাত্ক্ষণিক এক্সপায়ার্ড), `soft_veto_list` খালি | `src/neo_wilder/main.py:321` | CONFIRMED: সিগন্যাল জেনারেট হওয়ার সাথে সাথে এক্সপায়ার্ড দেখাত | MEDIUM (P2) | CONFIRMED | ALREADY FIXED (`expires_at_utc = created_at + expiry_bars * 15m` এবং মেটাডাটা ফিক্স) |
| **AUD-17 / DEF-17** | Genspark | `hard.py` এবং `risk_guard.py`-তে ডেপথ ক্লিপ অসঙ্গতি (১০০০ বনাম ৫০০ USD) | `src/neo_wilder/vetoes/hard.py:228` | CONFIRMED: ভিন্ন স্থানে ভিন্ন সীমা ব্যবহার করা হয়েছিল | MEDIUM (P2) | CONFIRMED | ALREADY FIXED (কনফিগারেশন ফাইল থেকে একক থ্রেশহোল্ড ব্যবহার নিশ্চিত করা হয়েছে) |
| **AUD-18 / DEF-18** | Genspark | `config/base.yaml` এবং `thresholds.yaml` কোডে লোড হতো না, সব হার্ডকোডেড ছিল | `src/neo_wilder/config.py` | CONFIRMED: কনফিগারেশন ড্র্রিফট ঝুঁকি ছিল | MEDIUM (P2) | CONFIRMED | ALREADY FIXED (`src/neo_wilder/config.py`-তে স্ট্রাকচার্ড কনফিগ লোডার বাস্তবায়িত) |
| **AUD-19 / DEF-19** | Genspark | প্রতি ক্যান্ডেলে নতুন `RegimeClassifier` ইনস্ট্যান্স তৈরি হওয়ায় হিস্টেরেসিস মেমরি কাজ করত না | `src/neo_wilder/main.py:214` | CONFIRMED: রেজিম ট্রানজিশন স্মুথিং কাজ করত না | LOW (P3) | CONFIRMED | ALREADY FIXED (`NeoWilderApplication`-এ একক সিঙ্গেলটন ইনস্ট্যান্স সংরক্ষিত) |
| **AUD-20 / DEF-20** | Genspark & Gemini | কিল সুইচ ইউআই, প্রসেস লকিং ও জার্নালডি লগ সাইজ লিমিট অনুপস্থিত | `deploy/neo-wilder.service` | CONFIRMED: লং-টার্ম ভিপিএস অপারেশনে ডিস্ক পূর্ণ হওয়ার ঝুঁকি | LOW (P3) | CONFIRMED | ALREADY FIXED (সিস্টেমড ইউনিটে স্যান্ডবক্সিং ও লগ সীমা নির্দেশিকা সংযোজিত) |
| **GEM-01** | Gemini | হার্ড ভিটো ফাংশনে মিসিং এক্সটার্নাল ডেটায় ফলব্যাক পাস হওয়ার ঝুঁকি (ফেইল-ক্লোজড লঙ্ঘন) | `src/neo_wilder/vetoes/hard.py` | CONFIRMED: বহিরাগত ফিড অফলাইন থাকলে পাস হওয়া নিষিদ্ধ | CRITICAL (P0) | CONFIRMED | ALREADY FIXED (যেকোনো মিসিং ডেটা `V-H11` বা `V-H31`-এ তাত্ক্ষণিক ব্লক হয়) |
| **GEM-02** | Gemini | সুইং পিভট ইনডেক্সিংয়ে লাইভ ক্যান্ডেলের প্রভাবে সাময়িক লুক-অ্যাহেড বা রিপেইন্ট ঝুঁকি | `src/neo_wilder/features/swings.py` | CONFIRMED: ক্লোজড বারের আগে পিভট চূড়ান্ত হওয়া নিষিদ্ধ | HIGH (P1) | CONFIRMED | ALREADY FIXED (`right_bars=1` কনফার্মেশন এবং প্রেফিক্স-ইনভ্যারিয়েন্স টেস্টে প্রমাণিত) |
| **GEM-03** | Gemini | CoinDCX পাবলিক এন্ডপয়েন্টে রেট লিমিট ও রিট্রাই থ্রোটলিং অনুপস্থিত (HTTP 429 ঝুঁকি) | `src/neo_wilder/data/rest_coindcx.py` | CONFIRMED: উচ্চ ভলাটিলিটিতে CoinDCX আইপি ব্যান করার ঝুঁকি ছিল | MEDIUM (P2) | CONFIRMED | ALREADY FIXED (`CoinDCXRateLimiter` টোকেন বাকেট ২ req/s ও এক্সপোনেনশিয়াল ব্যাকঅফ যুক্ত) |
| **GEM-04** | Gemini | দীর্ঘ সময় চললে সিস্টেমড সার্ভিসের স্ট্যান্ডার্ড আউটপুট লগ ডিস্ক পূর্ণ করতে পারে | `deploy/neo-wilder.service` | CONFIRMED: ওরাকল ১ জিবি ভিপিএসে ডিস্ক সুরক্ষা প্রয়োজন | LOW (P3) | CONFIRMED | ALREADY FIXED (`SystemMaxUse=200M` ও সার্ভিস কনফিগারেশন আপডেট) |

---

## ২. টেস্ট ফেইলিউর ও মনোটনিক বাগ বিশ্লেষণ (`test_execution.log`)

স্বাধীন অডিটরের রান করা `test_execution.log`-এ ৭৪টি টেস্টের মধ্যে ৪টি টেস্ট ফেইল করেছিল:
1. `tests/integration/test_risk_guard_integration.py::test_pipeline_blocks_candidate_under_extreme_funding` (Expected: `V-S04_ESCALATED`, Got: `V-H24`)
2. `tests/integration/test_risk_guard_integration.py::test_pipeline_blocks_composite_risk_even_if_score_100` (Expected: `V-H33_RISK_GUARD`, Got: `V-H24`)
3. `tests/unit/test_phase6_vetoes.py::test_veto_pipeline_clean_candidate_passes` (Expected: `True`, Got: `False` via `V-H24`)
4. `tests/unit/test_phase6_vetoes.py::test_soft_veto_escalation_btc_crash` (Expected: `V-S01`, Got: `V-H24`)

### রুট কজ (Root Cause)
`src/neo_wilder/vetoes/governor.py`-এর `is_symbol_locked()` মেথডে ছিল:
```python
last_time = self.state.symbol_last_signal_time.get(symbol, 0.0)
return (time.monotonic() - last_time) < self.cooldown_sec
```
যেসব মেশিনে বা কন্টেইনারে সিস্টেম বুট টাইম ১৮০০ সেকেন্ডের কম (যেমন ফ্রেশ সিআই/সিডি বা অডিট স্যান্ডবক্স), সেখানে `time.monotonic()`-এর মান ১৮০০-এর কম থাকে। ফলে `time.monotonic() - 0.0 < 1800` সর্বদা `True` রিটার্ন করত! এর ফলে টেস্ট স্যুটের প্রতিটি ক্যান্ডিডেটকে গভর্নর `V-H24 / V-H25` (সিম্বল কুলডাউন) দ্বারা শুরুতেই ব্লক করে দিচ্ছিল।

### সমাধান ও বর্তমান ফলাফল
`governor.py`-তে সিম্বল যদি পূর্বে সিগন্যাল পাবলিশ না করে থাকে, তবে তা তাৎক্ষণিকভাবে `False` (আনলকড) রিটার্ন করার শর্ত যুক্ত করা হয়েছে। এর ফলে ৪টি টেস্টই এখন সম্পূর্ণ সবুজ এবং সিস্টেমে কোনো ফলস ব্লকিং নেই।
মোট টেস্ট সংখ্যা ৭৪ থেকে বৃদ্ধি করে **৮৪টি** করা হয়েছে এবং **৮৪টির মধ্যে ৮৪টিই সফলভাবে উত্তীর্ণ (১০০% পাস রেট)**।
