# NEO-WILDER V4 — ওরাকল VPS ডিপ্লয়মেন্ট ও আপডেট গাইড (বাংলা)
## Beginner-Friendly Oracle Cloud Ubuntu VPS Deployment Guide

---

## ১. সার্ভার স্পেসিফিকেশন ও প্রস্তুতি (Prerequisites)

এই সিস্টেমটি ওরাকল ক্লাউড (Oracle Cloud Infrastructure - OCI) এর অলওয়েজ ফ্রি-টিয়ার ভার্চুয়াল সার্ভারের জন্য নিখুঁতভাবে অপ্টিমাইজ করা হয়েছে:
- **অপারেটিং সিস্টেম:** Ubuntu 22.04 LTS (x86_64 বা aarch64)
- **রিসোর্স:** ১ জিবি র‍্যাম, ২ ভিকোর (vCPU), ২ জিবি সোয়াপ মেমরি (Swap)
- **পাইথন ভার্সন:** Python 3.11+
- **মোড:** `SIGNAL` (টেলিগ্রাম এলার্ট) অথবা `SHADOW` (নীরব পর্যবেক্ষণ)

---

## ২. ধাপে ধাপে নতুন ইনস্টলেশন নির্দেশিকা (Step-by-Step Installation)

### ধাপ ১: SSH দিয়ে সার্ভারে লগইন করা
আপনার কম্পিউটার টার্মিনাল বা PowerShell থেকে কমান্ড দিন:
```bash
ssh -i /path/to/your-private-key.key ubuntu@YOUR_SERVER_PUBLIC_IP
```

### ধাপ ২: উবুন্টু আপডেট ও প্রয়োজনীয় সফটওয়্যার ইনস্টল
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3.11-dev git build-essential sqlite3
```

### ধাপ ৩: সোয়াপ মেমরি যাচাই ও কনফিগারেশন (যদি না থাকে)
১ জিবি র‍্যামে মেমরির চাপ কমাতে ২ জিবি সোয়াপ থাকা আবশ্যক:
```bash
# সোয়াপ চেক
free -h

# সোয়াপ না থাকলে তৈরি করার নিয়ম:
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### ধাপ ৪: ডেডিকেটেড সিস্টেম ইউজার ও ফোল্ডার তৈরি
সুরক্ষার স্বার্থে বটটি `root` ইউজারে চলবে না; এর জন্য `neowilder` নামে একটি আলাদা সিস্টেম ইউজার তৈরি করতে হবে:
```bash
sudo useradd -r -s /bin/false neowilder
sudo mkdir -p /opt/neo-wilder-v4
sudo mkdir -p /var/lib/neo-wilder
sudo mkdir -p /var/log/neo-wilder
sudo mkdir -p /etc/neo-wilder

# পারমিশন সেট করুন
sudo chown -R neowilder:neowilder /var/lib/neo-wilder /var/log/neo-wilder /etc/neo-wilder
```

### ধাপ ৫: গিটহাব রিপোজিটরি ক্লোন করা
```bash
sudo git clone https://github.com/arunabhamaity148-cell/neo-wilder-v4-.git /opt/neo-wilder-v4
sudo chown -R ubuntu:ubuntu /opt/neo-wilder-v4
```

### ধাপ ৬: পাইথন ভার্চুয়াল এনভায়রনমেন্ট ও ডিপেন্ডেন্সি ইনস্টল
```bash
cd /opt/neo-wilder-v4
python3.11 -m venv .venv
source .venv/bin/activate

# পাইপ আপগ্রেড ও ডিপেন্ডেন্সি ইনস্টলেশন
pip install --upgrade pip
pip install -r requirements.txt
```

### ধাপ ৭: এনভায়রনমেন্ট ফাইল কনফিগারেশন
```bash
sudo cp deploy/neo-wilder.env.example /etc/neo-wilder/neo-wilder.env
sudo chmod 600 /etc/neo-wilder/neo-wilder.env
sudo chown neowilder:neowilder /etc/neo-wilder/neo-wilder.env

# ফাইলটি এডিট করে আপনার টেলিগ্রাম বট টোকেন ও চ্যাট আইডি বসান:
sudo nano /etc/neo-wilder/neo-wilder.env
```
ফাইলে নিচের ভ্যারিয়েবলগুলো সঠিকভাবে বসান:
```ini
NEO_WILDER_MODE=SIGNAL
NEO_WILDER_ENV=production
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
TELEGRAM_CHAT_ID=-1001234567890
DB_PATH=/var/lib/neo-wilder/neo_wilder_journal.db
LOG_LEVEL=INFO
```
*(সংরক্ষণ করে বের হতে `Ctrl+O`, তারপর `Enter`, তারপর `Ctrl+X` চাপুন)*

### ধাপ ৮: systemd সার্ভিস ইনস্টল ও স্টার্ট করা
```bash
# সার্ভিস ফাইল কপি
sudo cp deploy/neo-wilder.service /etc/systemd/system/neo-wilder.service

# সিস্টেম ড্যামন রিলোড
sudo systemctl daemon-reload

# বুট টাইমে অটোমেটিক চালুর জন্য এনাবল করা
sudo systemctl enable neo-wilder

# সার্ভিস চালু করা
sudo systemctl start neo-wilder
```

### ধাপ ৯: স্ট্যাটাস ও লাইভ লগ যাচাই
```bash
# স্ট্যাটাস চেক
sudo systemctl status neo-wilder

# লাইভ চলমান লগ দেখতে
sudo journalctl -u neo-wilder -f
```
লগে যদি নিচের বার্তাগুলো দেখতে পান, তবে বুঝবেন সিস্টেম সম্পূর্ণ নিখুঁতভাবে চলছে:
- `Synchronized with Binance time. Skew: ...`
- `Initialized CoinDCX universe: ... symbols active.`
- `Binance WebSocket stream connected successfully.`
- `NEO-WILDER V4 initialization complete. Monitoring 8 symbols.`

---

## ৩. চলমান কোড আপডেট করার নিয়ম (Updating Existing Deployment)

যখনই গিটহাবে কোনো নতুন ফিক্স বা বাগ সমাধান আসবে, তখন VPS-এ আপডেট দেওয়ার সহজ কমান্ড:

```bash
# ১. ফোল্ডারে প্রবেশ করুন
cd /opt/neo-wilder-v4

# ২. সাময়িকভাবে সার্ভিস বন্ধ করুন
sudo systemctl stop neo-wilder

# ৩. সর্বশেষ কোড গিট থেকে পুল করুন
git pull origin main

# ৪. ভার্চুয়াল এনভায়রনমেন্টে নতুন প্যাকেজ থাকলে আপডেট করুন
source .venv/bin/activate
pip install -r requirements.txt

# ৫. সার্ভিস পুনরায় চালু করুন
sudo systemctl start neo-wilder

# ৬. লগ চেক করুন
sudo journalctl -u neo-wilder -n 50 --no-pager
```
