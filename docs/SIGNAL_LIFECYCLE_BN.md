# NEO-WILDER V4 — সিগন্যাল লাইফসাইকেল ও পাবলিকেশন পাইপলাইন (বাংলা)
## End-to-End Signal Generation, Gating & Delivery Lifecycle

---

## ১. ভূমিকা (Introduction)

এই নির্দেশিকায় বায়ন্যান্স থেকে একটি ১৫-মিনিটের ক্যান্ডেল রিসিভ হওয়া থেকে শুরু করে টেলিগ্রামে সিগন্যাল পাঠানো এবং পরবর্তীতে ট্রেডের ফলাফল ট্র্যাক করা পর্যন্ত প্রতিটি ধাপের পুঙ্খানুপুঙ্খ বিবরণ তুলে ধরা হলো।

---

## ২. সিগন্যাল তৈরি ও পাবলিকেশনের ২২টি ধাপ (22-Step Detailed Lifecycle)

```mermaid
sequenceDiagram
    autonumber
    participant BN as Binance WS & REST
    participant APP as NeoWilderApplication
    participant FEAT as Feature Engines
    participant S1 as S1 Sweep-Reclaim
    participant CDCX as CoinDCX Validator
    participant VETO as Veto Pipeline
    participant SCORE as Composite Scorer
    participant TG as Telegram Publisher
    participant DB as SQLite WAL Journal

    BN->>APP: 15m Candle Closes (e.g. BTCUSDT @ 69,500)
    APP->>DB: Record completed candle
    APP->>FEAT: Compute ATR, Swings, Pools, CVD, Volume Profile
    FEAT-->>APP: FeatureContext ready
    APP->>S1: Evaluate setup logic (E01, E03, E04)
    S1-->>APP: Candidate setup generated (Entry, SL, TP1, Net RR >= 1.50)
    APP->>CDCX: Query CoinDCX public quote (B-BTC_USDT)
    CDCX-->>APP: Quote: Price, Spread 0.01 bps, Depth $690k
    Note over APP,CDCX: Pass: Drift <= 0.35%, Spread <= 12 bps, Depth >= 20x
    APP->>VETO: Run 34 Hard & 15 Soft Vetoes
    VETO-->>APP: Hard Vetoes CLEARED; Soft Veto List computed
    APP->>SCORE: Score Candidate across 6 clusters
    SCORE-->>APP: Composite Score = 88/100 (Threshold >= 85.0)
    alt Mode == SIGNAL
        APP->>TG: Transmit Markdown Signal Alert
        TG-->>APP: Success (message_id = 123456)
        APP->>DB: Commit to SignalJournal & Governor Cooldown
    else Mode == SHADOW
        APP->>DB: Log Shadow Candidate silently (Zero TG Egress)
    end
    loop Each subsequent 15m candle
        BN->>APP: New 15m Candle
        APP->>DB: OutcomeResolver checks SL/TP hit (SL priority rule)
    end
```

---

## ৩. গুরুত্বপূর্ণ ধাপসমূহের কার্যপ্রণালী ও কোড রেফারেন্স (Technical Step Details)

### ১. ক্যান্ডেল সমাপ্তি ও ডেটা ভ্যালিডেশন (Steps 1–2)
- **কোড রেফারেন্স:** `src/neo_wilder/main.py: on_candle_close()`, `_process_candle_event()`
- বায়ন্যান্স ওয়েবসকেট থেকে যখন কোনো ১৫-মিনিটের বারের `is_closed == True` আসে, পাইপলাইন শুরু হয়।
- ডাটাবেস থেকে পূর্ববর্তী ১০০টি ক্যান্ডেল আনা হয়। ক্যান্ডেল সংখ্যা ২০-এর কম হলে গণনা শুরু হয় না।

### ২. ক্যান্ডিডেট জেনারেশন ও নেট R:R ফিল্টার (Steps 5–6)
- **কোড রেফারেন্স:** `src/neo_wilder/strategies/s1_sweep_reclaim.py`
- S1 স্ট্র্যাটেজি নিশ্চিত করে যে মূল্য পূর্ববর্তী লিকুইডিটি পুলের নিচে স্পাইক করে পুনরায় উপরে ক্লোজ হয়েছে।
- স্টপ লস ও টার্গেট নির্ধারণের পর CoinDCX-এর ০.১৩৫৪% রাউন্ড-ট্রিপ ফি ও স্লিপেজ বাদ দিয়ে নেট রিস্ক-রিওয়ার্ড রেশিও (Net R:R) মাপা হয়। যদি $\text{Net R:R} < ১.৫০$ হয়, তবে ক্যান্ডিডেট তাৎক্ষণিকভাবে পরিত্যক্ত হয়।

### ৩. CoinDCX এক্সিকিউশন গেট (Step 7)
- **কোড রেফারেন্স:** `src/neo_wilder/coindcx/validator.py`
- বায়ন্যান্স এবং CoinDCX-এর মূল্যের ব্যবধান মাপা হয়:
  $$\text{Drift} = \frac{|\text{CoinDCX Price} - \text{Reference Close}|}{\text{Reference Close}} \times 100\%$$
- যদি Drift $> ০.৩৫\%$ হয় (V-H32), বা স্প্রেড মেজর পেয়ারে $> ১২$ বেসিস পয়েন্ট হয় (V-H12), সিগন্যাল টেলিগ্রামে যায় না।

### ৪. ভেটো ও কোয়ালিটি স্কোরিং (Steps 8–9)
- **কোড রেফারেন্স:** `src/neo_wilder/vetoes/pipeline.py`, `src/neo_wilder/scoring/groups.py`
- ৩৪টি হার্ড ভেটোর কোনোটি ট্রিগার হলে ক্যান্ডিডেট বাতিল।
- কম্পোজিট স্কোরিংয়ে ০-১০০ স্কেলে স্কোর নির্ধারিত হয়। ৮৫.০ এর নিচে স্কোর পেলে সিগন্যাল পাবলিশ হয় না।

### ৫. টেলিগ্রাম এলার্ট ও নিরাপদ পাবলিকেশন (Step 11)
- **কোড রেফারেন্স:** `src/neo_wilder/publish/telegram.py`
- বার্তাটি টেলিগ্রামের অফিসিয়াল বট API-এর মাধ্যমে ৩ বার রিট্রাই সুবিধাসহ পাঠানো হয়।
- **গুরুত্বপূর্ণ নিরাপত্তা বৈশিষ্ট্য:** যদি কোনো কারণে টেলিগ্রামে বার্তা পাঠাতে ব্যর্থ হয় (নেটওয়ার্ক ড্রপ বা এপিআই এরর), তবে সিস্টেম সেটিকে সফল হিসেবে গণ্য করে না এবং গভর্নর কুলডাউন বা জার্নালে প্রকাশিত হিসেবে রেকর্ড করে না।

### ৬. ফলাফল ট্র্যাকিং ও রক্ষণশীল ইন্ট্রাবার নিয়ম (Steps 12–13)
- **কোড রেফারেন্স:** `src/neo_wilder/journal/outcomes.py`
- প্রকাশিত সিগন্যালের পর প্রতিটি পরবর্তী ক্যান্ডেলে মূল্য পরীক্ষা করা হয়:
  - **ইন্ট্রাবার অস্পষ্টতা নিয়ম (Conservative Intrabar Ambiguity Rule):** যদি একই ১৫ মিনিটের বারে স্টপ লস এবং টেক প্রফিট উভয়ই স্পর্শ করে, তবে কঠোর রক্ষণশীল নীতি অনুযায়ী সিস্টেম ধরে নেয় যে প্রথমে স্টপ লস স্পর্শ করেছে (`SL_HIT`)। এটি ওভার-অপ্টিমিস্টিক হিসেব রোধ করে।
- ট্রেডার যখন ম্যানুয়ালি CoinDCX-এ ট্রেড এক্সিকিউট করেন, তখন তিনি টেলিগ্রামে `/fill <signal_id> <price> <size>` কমান্ড পাঠালে ডাটাবেস তার আসল এন্ট্রি ট্র্যাক করে।
