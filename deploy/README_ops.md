# NEO-WILDER V4 — Production Operations Manual

## 1. System Overview & Architecture

**NEO-WILDER V4** is an institutional-grade, causal crypto futures intelligence engine operating under a permanent **`SIGNAL_ONLY`** architecture.

- **Primary Research Venue:** Binance USD-M public WebSocket streams & REST snapshots.
- **Manual Execution Venue:** CoinDCX Public APIs (validation of price, spread, depth, and drift only).
- **Target Host Budget:** Single 1 GB RAM / 2 vCPU VPS (Debian 12 or Ubuntu 22.04/24.04 LTS).
- **Process Model:** Single asynchronous `asyncio` process, bounded ringbuffers, SQLite WAL single-writer loop.
- **Strict Security Rule:** **Zero exchange private keys, zero automated order placement, zero execution API credentials.**

---

## 2. Host Prerequisites

1. **Operating System:** Ubuntu 22.04 LTS / 24.04 LTS (x86_64 or aarch64).
2. **Python:** Python 3.11 or 3.12 with `python3-venv` and `python3-pip`.
3. **Clock Synchronization:** `chrony` or `systemd-timesyncd` configured to keep clock skew $< 100\text{ ms}$ (hard veto threshold is $1000\text{ ms}$ via `V-H07`).
4. **RAM & Swap:** 1 GB physical RAM + 1 GB swapfile.

```bash
# Enable Chrony for microsecond timekeeping
sudo apt-get update && sudo apt-get install -y chrony python3.11 python3.11-venv
sudo systemctl enable --now chrony
chronyc tracking
```

---

## 3. Dedicated Service User & Directories

```bash
# Create non-privileged system user
sudo adduser --system --group --home /opt/neo-wilder-v4 --shell /bin/false neowilder

# Create data, log, and configuration directories
sudo mkdir -p /var/lib/neo-wilder
sudo mkdir -p /var/log/neo-wilder
sudo mkdir -p /etc/neo-wilder

sudo chown -R neowilder:neowilder /var/lib/neo-wilder /var/log/neo-wilder /etc/neo-wilder
sudo chmod 0750 /var/lib/neo-wilder /var/log/neo-wilder /etc/neo-wilder
```

---

## 4. Application Installation

```bash
# Clone production repository (without research/ directory on VPS)
cd /opt
sudo git clone https://github.com/arunabhamaity148-cell/neo-wilder-v4-.git neo-wilder-v4
cd /opt/neo-wilder-v4

# Set ownership
sudo chown -R neowilder:neowilder /opt/neo-wilder-v4

# Create Python virtual environment as neowilder user
sudo -u neowilder python3.11 -m venv .venv
sudo -u neowilder /opt/neo-wilder-v4/.venv/bin/pip install --upgrade pip
sudo -u neowilder /opt/neo-wilder-v4/.venv/bin/pip install .
```

---

## 5. Environment Configuration

```bash
# Copy and secure environment file
sudo cp /opt/neo-wilder-v4/deploy/neo-wilder.env.example /etc/neo-wilder/neo-wilder.env
sudo chmod 0600 /etc/neo-wilder/neo-wilder.env
sudo chown neowilder:neowilder /etc/neo-wilder/neo-wilder.env

# Edit configuration with your Telegram Bot Token and Chat ID
sudo nano /etc/neo-wilder/neo-wilder.env
```

---

## 6. Systemd Service Activation

```bash
# Install service definition
sudo cp /opt/neo-wilder-v4/deploy/neo-wilder.service /etc/systemd/system/neo-wilder.service
sudo systemctl daemon-reload

# Enable on boot and start service
sudo systemctl enable neo-wilder
sudo systemctl start neo-wilder

# Verify status
sudo systemctl status neo-wilder
```

---

## 7. Real-Time Observability & Monitoring

### Live Logs
```bash
# Stream journal logs with microsecond timestamps
journalctl -u neo-wilder -f -o short-precise
```

### Memory & Resource Health
```bash
# Monitor RSS and cgroup memory constraints
systemctl status neo-wilder | grep Memory
```
The system operates under `MemoryHigh=350M` and `MemoryMax=400M`. The internal application health engine flags a critical warning at $220\text{ MB}$ RSS and asserts `V-H08` at $300\text{ MB}$.

---

## 8. Operator Manual Self-Reporting Workflow

When an approved setup is published to Telegram:
1. The operator reviews the setup geometry, reference price, CoinDCX price, and invalidation criteria.
2. The operator manually enters the trade on CoinDCX.
3. Immediately after execution, the operator sends the self-report command to the bot or records it:
   ```text
   /fill <signal_id> <fill_price> <size>
   ```
   *Example:* `/fill SIG-BTCUSDT-1730900000 68250.5 0.15`
4. Signals without a registered `/fill` within the entry window are automatically recorded as `MISSED` in the SQLite WAL journal.

---

## 9. Incident Response & Emergency Procedures

| Symptom / Event | Automated System Response | Operator Remediation |
|---|---|---|
| **Binance WebSocket disconnects > 5s** | Asserts `V-H05` (fail-closed); zero signals emitted | Auto-reconnect with exponential backoff ($1\text{s}$ to $30\text{s}$). If host network dead, check VPS gateway. |
| **Clock skew exceeds 1000 ms** | Asserts `V-H07`; blocks signal pipeline | Check Chrony status: `chronyc tracking` and force sync with `chronyc makestep`. |
| **Watchdog misses 3 consecutive beats** | Escalates to `EMERGENCY_HALT`; asserts `V-H09` / `V-H10` | Check CPU starvation or event loop lockup in `journalctl`. Restart service if persistent. |
| **CoinDCX price drift > 0.35%** | Asserts `V-H32`; suppresses publication | Normal cross-venue liquidity divergence. No manual action required. |
| **Emergency Operator Stop** | Set kill-switch in environment or stop service | Execute: `sudo systemctl stop neo-wilder` |
