# Local Network Monitoring System (Telecom-Style)

Captures **real traffic** from your machine, reconstructs **IPDR-like session records**, runs **analytics**, and flags **anomalies** — connecting live network data to telecom analytics workflows.

## Architecture

```
[Packet / Connection Capture] → [IPDR Builder] → [SQLite] → [Analytics + Dashboard]
     psutil + scapy              session flows      storage     Node.js / Streamlit
```

## What It Monitors

| Metric | Source |
|--------|--------|
| Bytes sent / received per second | `psutil.net_io_counters()` |
| Active connections | `psutil.net_connections()` |
| Flow-level data (src/dst IP, port, protocol) | scapy sniff or connection polling |
| Session duration & byte counts | `IPDRBuilder` flow aggregation |

## Quick Start

```powershell
cd D:\08.coding\telecom-portfolio-evan\02-telecom-analytics\02-network-monitor
pip install -r requirements.txt
python run_monitor.py collect --duration 60
python run_monitor.py report
```

### Bandwidth only

```powershell
python run_monitor.py bandwidth --duration 30
```

### Packet capture (requires scapy + Npcap on Windows)

```powershell
python run_monitor.py collect --duration 120 --scapy
```

Run terminal **as Administrator** for full packet/connection visibility on Windows.

### Live monitor (default)

```powershell
cd dashboard-node
npm install
npm start
```

This starts **live collection + dashboard** together. Open **http://localhost:3000**.

- Charts refresh every **2 seconds** with a trailing **5-minute** window
- A **30-second startup baseline** is auto-recorded, then shown on the **Baseline Compare** tab
- Manual re-record anytime with **Record baseline**

Dashboard only (no collector):

```powershell
npm run dashboard
```

### Dashboard (Streamlit — optional)

```powershell
streamlit run dashboard/app.py
```

## IPDR Record (from real traffic)

```json
{
  "record_id": "uuid",
  "subscriber_id": "local_user",
  "src_ip": "192.168.1.105",
  "dst_ip": "142.250.74.78",
  "protocol": "TCP",
  "dst_port": 443,
  "start_time": "2026-06-30T20:00:01+00:00",
  "end_time": "2026-06-30T20:00:45+00:00",
  "duration_sec": 44,
  "bytes_up": 12400,
  "bytes_down": 458000,
  "service_type": "browsing",
  "app": "Google",
  "destination_domain": "google.com",
  "anomaly": "normal"
}
```

## Anomaly Detection

| Flag | Trigger |
|------|---------|
| `upload_spike` | Upload >> median (possible exfiltration) |
| `bot_connections` | Same destination IP excessive sessions |
| `micro_flow` | Tiny rapid flows |
| `unknown_destination` | No DNS + non-standard port |

## Project Structure

```
02-network-monitor/
├── run_monitor.py              # CLI: collect, live, report, bandwidth
├── collector/
│   ├── bandwidth.py            # psutil bandwidth sampling
│   ├── sniff.py                # scapy + psutil fallback
│   └── ipdr_builder.py         # Flow → IPDR session reconstruction
├── enrichment/
│   └── services.py             # Port/domain → app/service mapping
├── storage/
│   └── database.py             # SQLite persistence
├── analytics/
│   └── traffic_analytics.py    # Top domains, peak hours, ratios
├── anomalies/
│   └── detector.py             # Rule-based anomaly flags
├── dashboard/
│   └── app.py                  # Streamlit dashboard (optional)
├── dashboard-node/
│   ├── server.js               # Express API + static UI
│   ├── package.json
│   └── public/                 # Browser dashboard (HTML/Chart.js)
├── data/
│   └── network_monitor.db      # Created on collect
└── requirements.txt
```

## Connection to IPDR Generator

| Project | Data source |
|---------|-------------|
| [01-ipdr-generator](../01-ipdr-generator/) | Synthetic telecom traffic |
| **02-network-monitor** | **Real local machine traffic** |

Same IPDR concepts — sessions, bytes, apps, anomalies — applied to live capture.

## CV Line

> Built a local network monitoring system that captures packet-level traffic and transforms it into IPDR-style records. Implemented session reconstruction, traffic analytics, and anomaly detection on real network data.

## Requirements

- Python 3.9+
- Node.js 18+ (for browser dashboard)
- `pip install -r requirements.txt`
- **Npcap** (Windows) for scapy: https://nmap.org/npcap/

## Skills Demonstrated

- Real-time network metrics (psutil)
- Flow/session reconstruction
- IPDR-style record design
- SQLite data pipeline
- Traffic analytics and anomaly detection
- Streamlit operational dashboard
