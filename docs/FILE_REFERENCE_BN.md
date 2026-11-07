# NEO-WILDER V4 — ফাইল-বাই-ফাইল পূর্ণাঙ্গ গাইড (বাংলা)
## Complete Codebase File Reference for Beginners

---

## ১. ভূমিকা (Introduction)

এই নির্দেশিকাটি নতুন ব্যবহারকারী এবং বিগিনারদের জন্য তৈরি করা হয়েছে, যাতে প্রতিটি পাইথন মডিউল, কনফিগারেশন ফাইল এবং স্ক্রিপ্টের কাজ সহজে বোঝা যায়। কোনো ফাইল ভুলবশত পরিবর্তন করলে সিস্টেমে কী প্রভাব পড়তে পারে তাও প্রতিটি ফাইলে পরিষ্কারভাবে উল্লেখ করা হয়েছে।

---

## ২. রুট ও ডিপ্লয়মেন্ট ফাইলসমূহ (Root & Deployment Files)

### ১. `pyproject.toml`
- **পাথ:** `pyproject.toml`
- **কাজ:** প্রজেক্ট মেটাডেটা, ডিপেন্ডেন্সি তালিকা, বিল্ড সিস্টেম, টেস্ট এবং লিন্টারের কনফিগারেশন।
- **কেন রয়েছে:** পাইথন প্রজেক্টের আধুনিক স্ট্যান্ডার্ড প্যাকেজিং এবং প্যাকেজ ডিপেন্ডেন্সি নির্ধারণ করতে।
- **প্রধান সেকশন:** `[project]`, `[tool.pytest.ini_options]`, `[tool.ruff]`, `[tool.mypy]`।
- **ব্যবহার:** প্রোডাকশন এবং ডেভেলপমেন্ট উভয় ক্ষেত্রে।
- **সংশোধনে সতর্কতা:** ডিপেন্ডেন্সির ভার্সন পরিবর্তন করলে প্যাকেজ কনফ্লিক্ট বা নিরাপত্তা ত্রুটি দেখা দিতে পারে।

### ২. `requirements.txt`
- **পাথ:** `requirements.txt`
- **কাজ:** `pip-audit` দ্বারা অনুমোদিত ১৬টি ভার্নারেবিলিটি-মুক্ত পিনড প্যাকেজের তালিকা।
- **কেন রয়েছে:** ওরাকল ক্লাউড VPS-এ নিশ্চিত ও নিরাপদ ভার্চুয়াল এনভায়রনমেন্ট তৈরি করতে।
- **ব্যবহার:** প্রোডাকশন ইনস্টলেশনে (`pip install -r requirements.txt`)।

### ৩. `deploy/neo-wilder.service`
- **পাথ:** `deploy/neo-wilder.service`
- **কাজ:** লিনাক্স systemd সার্ভিস কনফিগারেশন ফাইল।
- **কেন রয়েছে:** সার্ভার রিবুট হলে বা প্রসেস ক্র্যাশ করলে স্বয়ংক্রিয়ভাবে বট চালু রাখা এবং মেমরি সর্বোচ্চ ৪০০ MB-তে সীমাবদ্ধ রাখা।
- **প্রধান প্যারামিটার:** `MemoryHigh=350M`, `MemoryMax=400M`, `Restart=always`, `EnvironmentFile=/etc/neo-wilder/neo-wilder.env`।
- **ব্যবহার:** ওরাকল VPS প্রোডাকশনে।

### ৪. `deploy/neo-wilder.env.example`
- **পাথ:** `deploy/neo-wilder.env.example`
- **কাজ:** প্রোডাকশন এনভায়রনমেন্ট ভ্যারিয়েবলের টেমপ্লেট।
- **কেন রয়েছে:** টেলিগ্রাম টোকেন, চ্যাট আইডি এবং রানটাইম মোড কনফিগার করতে।
- **প্রধান ভ্যারিয়েবল:** `NEO_WILDER_MODE=SIGNAL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`।
- **নিরাপত্তা নোট:** এটি একটি উদাহরণ ফাইল; আসল টোকেন কখনো গিট রিপোজিটরিতে পুশ করবেন না।

---

## ৩. কনফিগারেশন ডিরেক্টরি (`config/`)

### ১. `config/base.yaml`
- **পাথ:** `config/base.yaml`
- **কাজ:** সিস্টেমের মূল গ্লোবাল কনফিগারেশন। মেমরি লিমিট, পোর্টফোলিও হিট ক্যাপ (সর্বোচ্চ ২টি কনকারেন্ট ট্রেড, ৩% রিস্ক), CoinDCX ঘর্ষণ মডেল (০.১৩৫৪%) ইত্যাদি সংজ্ঞায়িত।
- **কলকারী:** `src/neo_wilder/config.py`।
- **সংশোধনে সতর্কতা:** `publish_threshold` ৮৫.০ এর নিচে নামালে নিম্নমানের সিগন্যাল টেলিগ্রামে চলে যেতে পারে।

### ২. `config/edge_registry.yaml`
- **পাথ:** `config/edge_registry.yaml`
- **কাজ:** ৩২টি ক্যানোনিকাল এজের সম্পূর্ণ মেটাডেটা রেজিস্ট্রি (E01-E28, X01-X04)।
- **কলকারী:** `src/neo_wilder/edges/registry.py`।

### ৩. `config/veto_registry.yaml`
- **পাথ:** `config/veto_registry.yaml`
- **কাজ:** ৪৯টি ভেটোর (৩৪টি Hard + ১৫টি Soft) কারণ ও তীব্রতা রেজিস্ট্রি।
- **কলকারী:** `src/neo_wilder/vetoes/pipeline.py`।

### ৪. `config/symbols.yaml`
- **পাথ:** `config/symbols.yaml`
- **কাজ:** নজরদারির জন্য নির্ধারিত ৮টি বায়ন্যান্স ক্রিপ্টো পেয়ারের তালিকা।

---

## ৪. সোর্স কোড কোর ডিরেক্টরি (`src/neo_wilder/`)

### ১. `src/neo_wilder/main.py`
- **পাথ:** `src/neo_wilder/main.py`
- **কাজ:** সম্পূর্ণ সিস্টেমের মাস্টার এন্ট্রি পয়েন্ট এবং কোঅর্ডিনেটর (`NeoWilderApplication`)।
- **প্রধান ক্লাস:** `NeoWilderApplication`
- **প্রধান ফাংশন:** `start()`, `on_candle_close()`, `_process_candle_event()`, `stop()`, `main()`।
- **ইনপুট:** বায়ন্যান্স মার্কেট ডেটা ও সিস্টেম ইভেন্ট।
- **আউটপুট:** যাচাইকৃত টেলিগ্রাম সিগন্যাল বা শ্যাডো লগ।
- **ব্যবহার:** প্রোডাকশনের প্রাণকেন্দ্র।
- **সংশোধনে সতর্কতা:** এটি পরিবর্তন করলে পাইপলাইনের ক্রম বা ইভেন্ট প্রসেসিং নষ্ট হতে পারে।

### ২. `src/neo_wilder/clock.py`
- **পাথ:** `src/neo_wilder/clock.py`
- **কাজ:** স্থানীয় সিস্টেম ঘড়ি এবং বায়ন্যান্স সার্ভার ঘড়ির সময় মিলিয়ে দেখা।
- **প্রধান ক্লাস:** `SystemClock`
- **ফাংশন:** `update_server_time()`, `now_ms()`, `skew_ms`।
- **ব্যবহার:** V-H07 ক্লক ডিসিঙ্ক ভেটো যাচাই করতে।

### ৩. `src/neo_wilder/config.py`
- **পাথ:** `src/neo_wilder/config.py`
- **কাজ:** YAML কনফিগারেশন ফাইল নিরাপদে লোড করা এবং টাইপ-সেফ ডেটাক্লাসে রূপান্তর করা।
- **প্রধান ক্লাস:** `AppConfig`, `SystemSettings`, `PortfolioSettings`।

---

## ৫. ডোমেন মডেল ও এনাম (`src/neo_wilder/domain/`)

### ১. `src/neo_wilder/domain/models.py`
- **পাথ:** `src/neo_wilder/domain/models.py`
- **কাজ:** সম্পূর্ণ সিস্টেমের ডেটা স্ট্রাকচার ডেটাক্লাস (`Candle`, `Trade`, `Candidate`, `CoinDCXQuote`, `EdgeResult` ইত্যাদি)।
- **ব্যবহার:** প্রতিটি মডিউলের মধ্যে ডেটা স্থানান্তরে ব্যবহৃত হয়।

### ২. `src/neo_wilder/domain/enums.py`
- **পাথ:** `src/neo_wilder/domain/enums.py`
- **কাজ:** অপরিবর্তনীয় ধ্রুবকসমূহ (`ExecutionMode`, `Direction`, `RegimeState`, `HardVetoReason` ইত্যাদি)।

---

## ৬. ডেটা কালেকশন ও স্টোরেজ (`src/neo_wilder/data/`)

### ১. `src/neo_wilder/data/ws_binance.py`
- **পাথ:** `src/neo_wilder/data/ws_binance.py`
- **কাজ:** বায়ন্যান্স ফিউচার্স লাইভ ওয়েবসকেট সংযোগ পরিচালনা ও স্বয়ংক্রিয় পুনরায় সংযোগ (Auto-Reconnect)।
- **প্রধান ক্লাস:** `BinanceWebSocketClient`
- **বাফার:** রিং বাফারে ক্যান্ডেল, ট্রেড এবং ডেপথ সীমাবদ্ধ রাখা হয়।

### ২. `src/neo_wilder/data/rest_binance.py`
- **পাথ:** `src/neo_wilder/data/rest_binance.py`
- **কাজ:** বায়ন্যান্স পাবলিক REST ক্লায়েন্ট (সার্ভার টাইম, ফান্ডিং রেট, ওপেন ইন্টারেস্ট)।

### ৩. `src/neo_wilder/data/rest_coindcx.py`
- **পাথ:** `src/neo_wilder/data/rest_coindcx.py`
- **কাজ:** CoinDCX পাবলিক REST ক্লায়েন্ট। রেট লিমিটিং এবং টোকেন বাকেট এনফোর্সমেন্ট।
- **সমাধানকৃত বাগ:** রিয়েল CoinDCX এপিআই থেকে প্রাপ্ত স্ট্রিং লিস্ট ও ডিকশনারি পার্সিং সঠিকভাবে সম্পাদন করে।

### ৪. `src/neo_wilder/data/store.py`
- **পাথ:** `src/neo_wilder/data/store.py`
- **কাজ:** SQLite WAL মোডে সিগন্যাল, ফিল এবং আউটকাম সংরক্ষণকারী ডেটা স্টোর।

---

## ৭. CoinDCX ইন্টিগ্রেশন (`src/neo_wilder/coindcx/`)

### ১. `src/neo_wilder/coindcx/universe.py`
- **পাথ:** `src/neo_wilder/coindcx/universe.py`
- **কাজ:** বায়ন্যান্স পেয়ারের সমতুল্য CoinDCX ফিউচার্স পেয়ার ম্যাপিং (যেমন `BTCUSDT` -> `B-BTC_USDT`)।
- **সমাধানকৃত বাগ:** `initialize_universe()` এখন রিয়েল CoinDCX API-এর `['B-BTC_USDT', ...]` স্ট্রিং তালিকা নিরাপদে পার্স করে।

### ২. `src/neo_wilder/coindcx/validator.py`
- **পাথ:** `src/neo_wilder/coindcx/validator.py`
- **কাজ:** সিগন্যাল পাবলিশ করার আগে CoinDCX-এর মূল্য বিচ্যুতি (Drift $\le 0.35\%$), স্প্রেড ($\le 12/25$ bps), এবং ডেপথ যাচাই করা।

---

## ৮. ফিচার ও এজ ইঞ্জিন (`src/neo_wilder/features/` ও `edges/`)

- `features/atr.py`: ওয়াইল্ডার্স ট্রু রেঞ্জ (ATR) হিসাব।
- `features/swings.py`: হাই/লো সুইং পয়েন্ট ডিটেকশন।
- `features/liquidity.py`: ইকুয়াল হাই/লো লিকুইডিটি পুল নির্ধারণ।
- `features/cvd.py`: কিউমুলেটিভ ভলিউম ডেল্টা গণনা।
- `features/obi.py`: অর্ডারবুক ইমব্যালেন্স পরিমাপ।
- `features/volume_profile.py`: ভলিউম প্রোফাইল POC এবং ভ্যালু এরিয়া হিসাব।
- `features/regime.py`: ট্রেন্ড বনাম রেঞ্জবাউন্ড মার্কেট রিজিমে শ্রেণিবিভাগ।
- `edges/runner.py`: ৩২টি এজ মূল্যায়নের সেন্ট্রাল রানার।
- `edges/e01_sweep_reclaim.py` থেকে `e28_expiry_engine.py`: পৃথক পৃথক এজের যুক্তির বাস্তবায়ন।

---

## ৯. স্ট্র্যাটেজি ও ভেটো (`src/neo_wilder/strategies/` ও `vetoes/`)

- `strategies/s1_sweep_reclaim.py`: প্রধান সক্রিয় লং সুইপ-রিক্লেইম স্ট্র্যাটেজি।
- `strategies/s2_oi_exhaustion.py`: ওপেন ইন্টারেস্ট এক্সহশন শ্যাডো স্ট্র্যাটেজি।
- `vetoes/pipeline.py`: ভেটো ইভ্যালুয়েশন সমন্বয়কারী মাস্টার পাইপলাইন।
- `vetoes/hard.py`: ৩৪টি হার্ড ভেটোর সরাসরি কোড লজিক।
- `vetoes/soft.py`: ১৫টি সফট ভেটো পেনাল্টি লজিক।
- `vetoes/governor.py`: পোর্টফোলিও রিস্ক এবং এস১-এস২ সংঘর্ষ লক নিয়ন্ত্রণ।

---

## ১০. পাবলিকেশন ও জার্নাল (`src/neo_wilder/publish/` ও `journal/`)

- `publish/schema.py`: অপরিবর্তনীয় ক্যানোনিকাল `Signal` ডেটাক্লাস।
- `publish/telegram.py`: টেলিগ্রাম এলার্ট ফরম্যাটার ও নিরাপদ সেন্ডার (টোকেন লগে প্রকাশ না করে মাস্কড চ্যাট আইডি লগ করে)।
- `journal/signals.py`: প্রকাশিত সিগন্যালের রেকর্ড সংরক্ষণ।
- `journal/fills.py`: ইউজারের পাঠানো `/fill` কমান্ড পার্সিং ও এক্সিকিউশন ট্র্যাকিং।
- `journal/outcomes.py`: ক্যান্ডেল ধরে ধরে স্টপ লস বা টেক প্রফিট স্পর্শ করলো কিনা তা স্বয়ংক্রিয় সমাধানকারী।
