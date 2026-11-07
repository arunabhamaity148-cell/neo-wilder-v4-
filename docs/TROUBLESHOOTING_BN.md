# NEO-WILDER V4 — সমস্যা সমাধান ও ট্রাবলশুটিং গাইড (বাংলা)
## Real Troubleshooting Scenarios, Diagnoses & Solutions

---

## ১. ভূমিকা (Introduction)

এই নির্দেশিকায় বাস্তব ডিপ্লয়মেন্ট ও সার্ভার অপারেশনের সময় যেসব সাধারণ ও জটিল ত্রুটি দেখা দিতে পারে, সেগুলোর কারণ এবং কমান্ডসহ সহজ সমাধান প্রদান করা হয়েছে।

---

## ২. দ্রুত সমস্যা সমাধান টেবিল (Quick Diagnostic Matrix)

| লক্ষণ (Symptoms) | সম্ভাব্য কারণ (Root Cause) | ডায়াগনস্টিক কমান্ড (Diagnostic Command) | সমাধান (Solution) |
|---|---|---|---|
| `'str' object has no attribute 'get'` | CoinDCX এপিআই স্ট্রিং তালিকা রিটার্ন করেছে | `sudo journalctl -u neo-wilder \| grep CoinDCX` | আপডেট কোড পুল করুন (`git pull origin main`) |
| `Telegram credentials not configured` | `/etc/neo-wilder/neo-wilder.env` ফাইলে টোকেন নেই | `sudo cat /etc/neo-wilder/neo-wilder.env` | ফাইলে সঠিক বটের টোকেন ও চ্যাট আইডি বসান |
| `V-H07 CLOCK_DESYNC` | লোকাল সার্ভারের সাথে বায়ন্যান্স টাইমের পার্থক্য $> ১০০০$ms | `chronyc tracking` বা `timedatectl status` | `sudo systemctl restart systemd-timesyncd` |
| `Permission denied: /var/lib/...` | ডাটাবেস ফোল্ডারে `neowilder` ইউজারের পারমিশন নেই | `ls -la /var/lib/neo-wilder` | `sudo chown -R neowilder:neowilder /var/lib/neo-wilder` |
| `Service failed with result 'oom-kill'` | মেমরি ৪০০ মেগাবাইট ছাড়িয়ে গেছে | `sudo dmesg \| grep -i oom` | সোয়াপ মেমরি চেক করুন; আনলকড ক্যাশ রিমুভ করুন |
| `V-H05 WS_DISCONNECTED` | বায়ন্যান্স ওয়েবসকেট নেটওয়ার্ক ড্রপ | `ping fstream.binance.com` | নেটওয়ার্ক চেক করুন; বট স্বয়ংক্রিয় পুনরায় যুক্ত হবে |
| `ModuleNotFoundError` | সার্ভিস ভুল পাইথন ব্যবহার করছে | `which python` / সার্ভিস ফাইল এক্সিকিউটেবল চেক | `.venv/bin/python` পাথ নিশ্চিত করুন |

---

## ৩. প্রধান সমস্যাসমূহের বিস্তারিত বিশ্লেষণ ও সমাধান (Deep-Dive)

### সমস্যা ১: CoinDCX এপিআই পার্সার এরর (`'str' object has no attribute 'get'`)
- **বাস্তব লগ মেসেজ:**
  `Could not query CoinDCX instruments: 'str' object has no attribute 'get'. Falling back to default list.`
- **কারণ:**
  CoinDCX-এর `/exchange/v1/derivatives/futures/data/active_instruments` এন্ডপয়েন্টটি কোনো অবজেক্টের তালিকা রিটার্ন করে না; এটি সরাসরি স্ট্রিং পেয়ারের একটি ফ্ল্যাট তালিকা প্রদান করে (যেমন: `["B-BTC_USDT", "B-ETH_USDT", ...]`)। পূর্বের কোড ধরে নিয়েছিল প্রতিটি আইটেম একটি ডিকশনারি এবং তাতে `.get("pair")` কল করেছিল।
- **সমাধান:**
  বর্তমান ভার্সনে `SymbolUniverseManager` এবং `CoinDCXPublicClient` আপডেট করা হয়েছে। এটি এখন ইনপুট স্ট্রিং হলে সরাসরি পেয়ার হিসেবে গ্রহণ করে এবং ডিকশনারি হলেও সমর্থন করে।
  **ফিক্স পেতে:**
  ```bash
  cd /opt/neo-wilder-v4
  git pull origin main
  sudo systemctl restart neo-wilder
  ```

---

### সমস্যা ২: সার্ভার সময় অমিল (Clock Desynchronization / V-H07)
- **বাস্তব লগ মেসেজ:**
  `VETO_TRIGGERED: Candidate blocked by V-H07 (CLOCK_DESYNC)`
- **কারণ:**
  বায়ন্যান্স ফিউচার্স পাবলিক সার্ভারের সাথে আপনার সার্ভারের সময়ের ব্যবধান ১ সেকেন্ডের বেশি হলে ট্রেডের ক্রোনোলজি রক্ষা করতে সিস্টেম সিগন্যাল বাতিল করে।
- **সমাধান:**
  উবুন্টু সার্ভারে নেটওয়ার্ক টাইম প্রটোকল (NTP) সিনক্রোনাইজেশন চালু করুন:
  ```bash
  sudo apt install -y systemd-timesyncd
  sudo timedatectl set-ntp true
  sudo systemctl restart systemd-timesyncd
  timedatectl status
  ```

---

### সমস্যা ৩: টেলিগ্রাম বার্তা না আসা (Telegram Delivery Failure)
- **লক্ষণ:**
  বট চলছে, সিগন্যাল তৈরি হচ্ছে, কিন্তু টেলিগ্রাম চ্যানেলে কোনো এলার্ট আসছে না।
- **ডায়াগনসিস:**
  1. সার্ভিস লগে দেখুন কোনো এরর আছে কিনা:
     ```bash
     sudo journalctl -u neo-wilder -n 100 --no-pager | grep Telegram
     ```
  2. সাধারণ কারণসমূহ:
     - বটের টোকেন ভুল বা চ্যাট আইডি ভুল।
     - প্রাইভেট চ্যানেলে বটটিকে **Administrator** হিসেবে অ্যাড করা হয়নি বা মেসেজ পাঠানোর পারমিশন দেওয়া হয়নি।
     - চ্যাট আইডির শুরুতে মাইনাস (`-`) চিহ্ন বাদ পড়েছে (সুপারগ্রুপ ও চ্যানেলে সাধারণত `-100` দিয়ে শুরু হয়)।
- **টেস্টিং কমান্ড (সার্ভার থেকে সরাসরি টেস্ট করা):**
  ```bash
  curl -s -X POST "https://api.telegram.org/bot<YOUR_TOKEN>/sendMessage" \
       -d "chat_id=<YOUR_CHAT_ID>" \
       -d "text=Manual VPS test successful"
  ```

---

### সমস্যা ৪: মেমরি সংকট বা সার্ভিস ক্র্যাশ (Out of Memory / OOM Kill)
- **লক্ষণ:**
  `sudo systemctl status neo-wilder` দিলে দেখায় `status=137` বা `signal=KILL`।
- **কারণ:**
  সার্ভারে অন্যান্য ভারী প্রসেস চলায় বা সোয়াপ না থাকায় systemd সার্ভিসটি ৪০০ মেগাবাইটের হার্ড লিমিট পার করায় লিনাক্স কার্নেল বটটি বন্ধ করে দেয়।
- **সমাধান:**
  1. সোয়াপ ফাইল আছে কিনা পরীক্ষা করুন (`free -h`)। না থাকলে ২ জিবি সোয়াপ তৈরি করুন।
  2. অপ্রয়োজনীয় মেমরি গ্রাসী সার্ভিস বন্ধ করুন।
  3. `neo-wilder.service`-এর রিসোর্স লিমিট ডিফল্টে ঠিক আছে কিনা দেখুন (`MemoryHigh=350M`, `MemoryMax=400M`)।
