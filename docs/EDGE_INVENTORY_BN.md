# NEO-WILDER V4 — এজ ইনভেন্টরি ও বিস্তারিত বিশ্লেষণ (বাংলা)
## Complete 32 Edge Inventory & Mathematical Specifications

---

## ১. ভূমিকা ও পরিসংখ্যান (Overview & Distribution)

**NEO-WILDER V4**-এর এজ রেজিস্ট্রিতে (`config/edge_registry.yaml`) সর্বমোট **৩২টি সুনির্দিষ্ট এজ** নিবন্ধিত রয়েছে। এই এজগুলো বিভিন্ন অর্থোগোনাল ক্লাস্টারে (Orthogonal Correlation Clusters) বিভক্ত, যা নিশ্চিত করে যে একই ধরনের তথ্য একাধিকবার স্কোরিংয়ে বাড়তি সুবিধা না পায়।

### ৩২টি এজের স্ট্যাটাস বণ্টন (Status Distribution):
- **ACTIVE (সক্রিয় এজ):** ১৩টি (সক্রিয় সিগন্যাল জেনারেশন ও কম্পোজিট স্কোরিংয়ে অংশগ্রহণ করে)
- **SHADOW (শ্যাডো এজ):** ১১টি (টেলিমেট্রি এবং শ্যাডো মোডে নিরীক্ষিত হয়; সক্রিয় স্কোরে ০ পয়েন্ট)
- **EXPERIMENTAL (পরীক্ষামূলক এজ):** ৫টি (গবেষণাগার ও স্যান্ডবক্সে সীমাবদ্ধ)
- **REJECT (বাতিলকৃত এজ):** ৩টি (১৫-মিনিটের টাইমফ্রেমে অনুপযুক্ত বা ডেটা সোর্স অপ্রমাণিত হওয়ায় প্রত্যাখ্যাত)

---

## ২. সম্পূর্ণ ৩২টি এজের রেজিস্ট্রি তালিকা (Complete Registry Table)

| এজ আইডি (ID) | এজের নাম (Name) | সোর্স ফাইল (Source File) | ক্লাস্টার (Cluster) | স্ট্যাটাস (Status) | উদ্দেশ্য ও ভূমিকা (Role) | রানটাইম কল (Runtime Call) |
|:---:|---|---|:---:|:---:|---|:---:|
| **E01** | Liquidity Sweep & Reclaim | `edges/e01_sweep_reclaim.py` | C3 | **ACTIVE** | ম্যান্ডাটরি সেটআপ এজ (S1) | হ্যাঁ (Main Pipeline) |
| **E02** | 4-Stage Sweep Confirmation | `edges/new_edges.py` | C3 | **SHADOW** | সুইপের ৪-ধাপ ভ্যালিডেশন | হ্যাঁ (Shadow Engine) |
| **E03** | Sweep Depth (ATR Norm) | `edges/e03_sweep_depth.py` | C3 | **ACTIVE** | সুইপ গভীরতা $\ge 0.1 \times \text{ATR}$ | হ্যাঁ (Main Pipeline) |
| **E04** | Liquidity Pools EQH/EQL | `edges/e04_liquidity_pools.py` | C3 | **ACTIVE** | ইকুয়াল হাই/লো ডিটেকশন | হ্যাঁ (Main Pipeline) |
| **E05** | Structure BOS & CHoCH | `edges/e05_structure.py` | C3 | **SHADOW** | মার্কেট স্ট্রাকচার শিফট | হ্যাঁ (Shadow Engine) |
| **E06** | Supply & Demand Zones | `edges/new_edges.py` | C3 | **SHADOW** | জোন কনফ্লুয়েন্স টেস্ট | হ্যাঁ (Shadow Engine) |
| **E07** | Volume Profile POC/VAH/VAL | `edges/e07_volume_profile.py` | C5 | **ACTIVE** | প্রাতিষ্ঠানিক টার্গেট লেভেল | হ্যাঁ (Main Pipeline) |
| **E08** | Anchored VWAP | `edges/new_edges.py` | C5 | **EXPERIMENTAL** | অ্যাঙ্কর পয়েন্ট থেকে গড় মূল্য | স্যান্ডবক্স |
| **E09** | Poor High / Poor Low | `edges/new_edges.py` | C5 | **EXPERIMENTAL** | অসম্পূর্ণ নিলাম শনাক্তকরণ | স্যান্ডবক্স |
| **E10** | Fair Value Gap (FVG) | `edges/new_edges.py` | C5 | **SHADOW** | ৩-বার ইমব্যালেন্স টেস্ট | হ্যাঁ (Shadow Engine) |
| **E11** | ATR Realised Volatility | `edges/e11_atr_volatility.py` | RISK | **ACTIVE** | ভলাটিলিটি নরম্যালাইজেশন | হ্যাঁ (Main Pipeline) |
| **E12** | Dynamic Stop-Loss Buffer | `edges/e12_dynamic_sl_buffer.py` | RISK | **ACTIVE** | ন্যূনতম ০.৬৫% বাফার প্রদান | হ্যাঁ (Main Pipeline) |
| **E13** | Liquidation Burst Z-Score | `edges/e13_liq_burst.py` | C1 | **SHADOW** | জোরপূর্বক লিকুইডেশন তীব্রতা | হ্যাঁ (Shadow Engine) |
| **E14** | Liquidation Cluster Proximity | `edges/new_edges.py` | C1 | **EXPERIMENTAL** | লিকুইডেশন ক্লাস্টার দূরত্ব | স্যান্ডবক্স |
| **E15** | CVD Turn | `edges/e15_cvd_turn.py` | C2 | **SHADOW** | ভলিউম ডেল্টা রিভার্সাল | হ্যাঁ (Shadow Engine) |
| **E16** | Order Book Imbalance (OBI) | `edges/e16_obi.py` | C2 | **SHADOW** | টপ-১০ বিড/আস্ক ভারসাম্যহীনতা | হ্যাঁ (Shadow Engine) |
| **E17** | Book Density Absorption | `edges/e17_absorption.py` | C2 | **SHADOW** | প্যাসিভ লিমিট অর্ডার শোষণ | হ্যাঁ (Shadow Engine) |
| **E18** | Microprice | `edges/new_edges.py` | NONE | **REJECT** | উচ্চ-ফ্রিকোয়েন্সি মাইক্রোপ্রাইস | প্রত্যাখ্যাত (Reject) |
| **E19** | Microbar Volume Clock | `edges/new_edges.py` | NONE | **REJECT** | ভলিউম ক্লক সাব-সেকেন্ড | প্রত্যাখ্যাত (Reject) |
| **E20** | Hawkes Trade Intensity | `edges/new_edges.py` | C1 | **SHADOW** | ক্লাস্টার্ড ট্রেড ফ্লো মডেল | হ্যাঁ (Shadow Engine) |
| **E21** | OI Exhaustion Reversal | `edges/e21_oi_exhaustion.py` | C4 | **SHADOW** | S2 ম্যান্ডাটরি সেটআপ এজ | হ্যাঁ (Shadow Engine) |
| **E22** | Spot-Led Basis Divergence | `edges/new_edges.py` | C4 | **EXPERIMENTAL** | স্পট/পার্প ডিসলোকেশন | স্যান্ডবক্স |
| **E23** | Funding Context | `edges/e23_funding_context.py` | C4 | **ACTIVE** | ফান্ডিং রেট পজিশনিং রিস্ক | হ্যাঁ (Main Pipeline) |
| **E24** | Mark-Index Divergence | `edges/e24_mark_index_div.py` | C4 | **ACTIVE** | স্পট ও ফিউচার্স মূল্যের বিচ্যুতি | হ্যাঁ (Main Pipeline) |
| **E25** | Variance Ratio Regime | `edges/new_edges.py` | C6 | **SHADOW** | মার্কেট মেমোরি / র্যান্ডম ওয়াক | হ্যাঁ (Shadow Engine) |
| **E26** | GEX & Gamma Flip | `edges/new_edges.py` | NONE | **REJECT** | অপশন গামা এক্সপোজার | প্রত্যাখ্যাত (Reject) |
| **E27** | Session Classification | `edges/new_edges.py` | C6 | **EXPERIMENTAL** | লন্ডন/নিউইয়র্ক সেশন ফিল্টার | স্যান্ডবক্স |
| **E28** | Signal Expiry Engine | `edges/e28_expiry_engine.py` | RISK | **ACTIVE** | সিগন্যালের সময়সীমা নির্ধারণ | হ্যাঁ (Main Pipeline) |
| **X01** | BTC Directional Conflict | `edges/new_edges.py` | V_S01 | **ACTIVE** | বিটকয়েন ট্রেন্ডের সাথে বিরোধ | হ্যাঁ (Soft Veto) |
| **X02** | Relative Volume Gate | `edges/new_edges.py` | FILTER | **ACTIVE** | ভলিউম ফিল্টার ($> 1.0\times$ গড়) | হ্যাঁ (Main Pipeline) |
| **X03** | CoinDCX Spread/Liquidity Gate | `edges/new_edges.py` | FILTER | **ACTIVE** | এক্সিকিউশন সক্ষমতা যাচাই | হ্যাঁ (CoinDCX Gate) |
| **X04** | Late Entry Suppression | `edges/new_edges.py` | FILTER | **ACTIVE** | এন্ট্রি জোন অতিক্রমণ প্রতিরোধ | হ্যাঁ (Soft Veto) |

---

## ৩. গুরুত্বপূর্ণ সক্রিয় এজসমূহের গাণিতিক বিশ্লেষণ (Active Edge Deep-Dive)

### ১. E01: Liquidity Sweep & Reclaim
- **ইনপুট:** ১৫ মিনিটের ক্যান্ডেল এবং `E04`-এর চিহ্নিত লিকুইডিটি পুল।
- **গণনা:**
  $$\text{Sweeped} = (\text{Low} < \text{Pool Price}) \quad \text{এবং} \quad (\text{Close} > \text{Pool Price})$$
- **আউটপুট:** `passed: bool`, `confidence: float` (০.৭৫ – ০.৯০)।

### ২. E03: Sweep Depth Normalised by ATR
- **ইনপুট:** সুইপ ক্যান্ডেল, পুল লেভেল, ১৪-পিরিয়ড ATR।
- **গণনা:**
  $$\text{Depth Ratio} = \frac{|\text{Pool Price} - \text{Low}|}{\text{ATR}}$$
  শর্ত: $\text{Depth Ratio} \ge 0.10$ (খুব অগভীর সুইপ ফিল্টার করতে)।

### ৩. E04: Liquidity Pools (EQH / EQL)
- **ইনপুট:** সুইং হাই এবং সুইং লো তালিকা।
- **গণনা:** দুটি ধারাবাহিক সুইং পয়েন্টের মূল্যের পার্থক্য যদি $0.15 \times \text{ATR}$-এর কম হয়, তবে সেটিকে ইকুয়াল হাই/লো লিকুইডিটি পুল হিসেবে চিহ্নিত করা হয়।

### ৪. E07: Volume Profile (POC, VAH, VAL)
- **ইনপুট:** সাম্প্রতিক ১০০টি ক্যান্ডেলের ভলিউম এবং প্রাইস রেঞ্জ।
- **গণনা:** প্রাইস রেঞ্জকে ৫০টি বিনে ভাগ করে সর্বাধিক ভলিউম বিনকে POC (Point of Control) এবং ৭০% ভলিউম ধারণকারী এলাকাকে Value Area (VAH/VAL) নির্ধারণ করা হয়।

### ৫. E11 ও E12: ATR Volatility & Dynamic Stop Buffer
- **ইনপুট:** ১৪-পিরিয়ড ওয়াইল্ডার ATR এবং এন্ট্রি প্রাইস।
- **গণনা:**
  $$\text{SL Distance} = \max(0.0065 \times \text{Entry}, 0.5 \times \text{ATR})$$
  এটি নিশ্চিত করে যে অত্যন্ত টাইট স্টপ লস দিয়ে স্প্রেড ও নয়েজে অকাল লিকুইডেশন না ঘটে।

### ৬. E23 ও E24: Funding & Mark-Index Risk
- **ইনপুট:** বায়ন্যান্স প্রিমিয়াম ইনডেক্স এবং ফান্ডিং রেট।
- **গণনা:**
  - যদি ফান্ডিং রেট $> +0.05\%$, লং পজিশনে অতিরিক্ত ক্রাউডিং নির্দেশ করে এবং সফট পেনাল্টি দেয়।
  - যদি $|\text{Mark Price} - \text{Index Price}| / \text{Index Price} > 0.5\%$, **V-H18** ট্রিগার হয়ে ট্রেড বন্ধ করে।
