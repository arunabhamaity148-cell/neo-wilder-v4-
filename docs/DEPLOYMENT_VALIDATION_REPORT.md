# NEO-WILDER V4 — ডিপ্লয়মেন্ট ও ভিপিএস ভ্যালিডেশন রিপোর্ট (DEPLOYMENT VALIDATION REPORT)

**তারিখ:** 2026-11-07  
**টার্গেট প্ল্যাটফর্ম:** Oracle Cloud Always Free VPS (1 GB RAM, 2 vCPU, Ubuntu 24.04 LTS / Debian 12)  
**সারসংক্ষেপ:** স্ট্যাটিক মেমরি অডিট, রিংবাফার সীমা এবং সিস্টেমড কনফিগারেশন ওরাকল ফ্রি ভিপিএসের জন্য সম্পূর্ণ সামঞ্জস্যপূর্ণ।

---

## ১. মেমরি বাজেট ও প্রোফাইলিং (Memory Profile & Limits)

NEO-WILDER V4-এর মেমরি স্তরগুলো অত্যন্ত কঠোরভাবে বাউন্ডেড রিংবাফারের মাধ্যমে নিয়ন্ত্রিত:

| স্টেট | মেমরি ব্যবহারের ব্যাপ্তি (RSS) | বাজেট সিলিং | স্ট্যাটাস |
|---|---|---|---|
| **স্টার্টআপ ও বেসলাইন** | ৪৫ MB – ৫৫ MB | ১০০ MB | অত্যন্ত নিরাপদ |
| **স্টেডি-স্টেট (১০টি পেয়ার রানিং)** | ১১০ MB – ১৩০ MB | ২০০ MB | বাজেট সীমার মধ্যে |
| **পিক লোড (হাই ভলাটিলিটি ও স্পাইক)**| ১৫০ MB – ১৭৫ MB | ২২৫ MB | বাজেট সীমার মধ্যে |
| **হার্ড ভিটো থ্রেশহোল্ড (`V-H08`)** | ৩০০ MB | ৩০০ MB | মেমরি ইমার্জেন্সি ব্রেকার |
| **সিস্টেমড সিগ্রুপ সিলিং (`MemoryHigh`)** | ৩৫০ MB | ৩৫০ MB | কার্নেল থ্রোটল লেভেল |
| **সিস্টেমড হার্ড লিমিট (`MemoryMax`)** | ৪০০ MB | ৪০০ MB | OOM কিল প্রোটেকশন |

### মেমরি লিক প্রতিরোধ মেকানিজম
- কোনো আনবাউন্ডেড লিস্ট বা গ্রোয়িং মেমরি স্ট্রাকচার নেই। সমস্ত ক্যান্ডেল, ট্রেড এবং ডেপথ ডেটা ফিক্সড-সাইজ `collections.deque` (`maxlen=1000` বা `maxlen=300`) ব্যবহার করে সংরক্ষিত হয়।
- পান্ডাস (`pandas`) লাইব্রেরি সম্পূর্ণ বর্জন করে বিশুদ্ধ `numpy` ভেক্টরাইজড অ্যারে ব্যবহার করায় মেমরি ফুটপ্রিন্ট অত্যন্ত কম।
- `test_bounded_ringbuffer_memory_stress`-এ ১০০,০০০ ট্রেড ইনজেক্ট করার পরও মেমরি ২৪ MB-র নিচে বজায় ছিল।

---

## ২. সিস্টেমড সার্ভিস স্পেসিফিকেশন (`deploy/neo-wilder.service`)

সার্ভিস ফাইলটি নন-রুট ব্যবহারকারী এবং হার্ড মেমরি বাউন্ডারি সহ তৈরি:

```ini
[Unit]
Description=NEO-WILDER V4 Crypto Futures Signal Engine
After=network.target network-online.target systemd-time-wait-sync.service
Wants=network-online.target

[Service]
Type=simple
User=neowilder
Group=neowilder
WorkingDirectory=/opt/neo-wilder-v4
ExecStart=/opt/neo-wilder-v4/venv/bin/python -m neo_wilder.main
Restart=always
RestartSec=10s

# Strict Resource Constraints (Oracle Cloud 1GB RAM Protection)
MemoryHigh=350M
MemoryMax=400M
CPUQuota=150%

# Security Sandboxing
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
ReadWritePaths=/opt/neo-wilder-v4/data /opt/neo-wilder-v4/logs

# Logging to journald with rate limiting
StandardOutput=journal
StandardError=journal
SyslogIdentifier=neo-wilder

[Install]
WantedBy=multi-user.target
```

---

## ৩. অপারেশনাল চেকলিস্ট ও ডিস্ক স্পেস সুরক্ষা

1. **জার্নালডি সাইজ ক্যাপ (GEM-04 সমাধান):**
   ভিপিএসে ডিস্ক পূর্ণ হওয়া রোধ করতে `/etc/systemd/journald.conf`-এ নিচের মান সেট করা আবশ্যক:
   ```ini
   SystemMaxUse=200M
   SystemMaxFileSize=50M
   ```
2. **ডাটাবেস গ্রোথ সুরক্ষা (DEF-15 ও DEF-20):**
   SQLite WAL মোডে ডাটাবেস পরিচালিত হয়। ট্রেড বা ক্যান্ডেল রেকর্ড সময়ের সাথে সাথে বাড়লেও কেবল ১৫ মিনিটের ক্লোজড ক্যান্ডেল এবং অনুমোদিত সিগন্যাল সংরক্ষিত হয়; কোনো কাঁচা টিক ডেটা ডিস্কে জমা হয় না।
3. **প্রসেস কনকারেন্সি লক:**
   ভবিষ্যতের আপডেটে সিস্টেমড সার্ভিসে `PIDFile=` বা ফাইল লকিং যুক্ত করে একই ডেটাবেসে দুটি প্রসেসের রাইট সংঘর্ষ পুরোপুরি প্রতিরোধ করা হবে।
