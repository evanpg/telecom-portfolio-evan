# IPDR Generator

Synthetic **IP Detail Record (IPDR)** generator that mimics real telecom data traffic for analytics, billing, and fraud-detection portfolio projects.

An IPDR is the IP-based equivalent of a Call Detail Record (CDR) — it tracks how a subscriber or device consumes network services over a session.

## What It Generates

Each record models a completed IP session with fields operators typically use:

| Field | Description |
|-------|-------------|
| `subscriber_id` | Internal subscriber identifier |
| `imsi` | Mobile subscriber identity |
| `ip_address` | Assigned subscriber IP |
| `cell_id` | Radio / access cell |
| `start_time` / `end_time` | Session boundaries |
| `duration_sec` | Session length |
| `bytes_up` / `bytes_down` | Upload / download volume |
| `service_type` | streaming, browsing, voip, gaming, social |
| `app` | Application (YouTube, Zoom, etc.) |
| `destination_ip` / `destination_domain` | Remote endpoint |
| `country` | Subscriber country |
| `device_type` | Android, iOS, Router, etc. |
| `network_element` | PGW / SGW / BRAS generating the record |
| `anomaly` | normal or fraud pattern label |

## Realistic Behavior (not random rows)

- **Service profiles** — byte volume and duration match service type (streaming = high download, long sessions)
- **Subscriber personas** — heavy streamer, business user, gamer, casual mobile, home router
- **Time-of-day patterns** — evening peak traffic weighting
- **Anomaly injection (~5%)** — data exfiltration, SIM box fraud, impossible travel, bot traffic

## Quick Start

```powershell
cd D:\08.coding\telecom-portfolio-evan\02-telecom-analytics\01-ipdr-generator
python generate_ipdr.py
```

Default output: `data/ipdr_simulated.csv` + `data/ipdr_simulated.json` (10,000 records).

### Options

```powershell
# Custom volume and seed
python generate_ipdr.py -n 50000 --seed 123 -o data/ipdr_50k.csv

# More subscribers, higher anomaly rate
python generate_ipdr.py -n 20000 --subscribers 2000 --anomaly-rate 0.08

# Live traffic stream (one record per second)
python generate_ipdr.py --live --interval 1
python generate_ipdr.py --live --interval 0.5 --live-count 100 -o data/ipdr_live.csv
```

## Example Record

```json
{
  "subscriber_id": "SUB100042",
  "imsi": "748014218376592",
  "ip_address": "10.14.88.201",
  "cell_id": "CELL_034",
  "start_time": "2026-06-30T20:15:00+00:00",
  "end_time": "2026-06-30T20:42:00+00:00",
  "duration_sec": 1620,
  "bytes_up": 312400,
  "bytes_down": 14820000,
  "service_type": "streaming",
  "app": "Netflix",
  "destination_ip": "203.0.113.44",
  "destination_domain": "netflix.com",
  "country": "PY",
  "device_type": "Smart TV",
  "network_element": "PGW-01",
  "anomaly": "normal"
}
```

## Anomaly Types

| Label | Pattern |
|-------|---------|
| `data_exfiltration` | Massive upload spike, minimal download |
| `sim_box_fraud` | Short repetitive VoIP sessions |
| `impossible_travel` | Same subscriber, different country/cell |
| `bot_traffic` | Tiny identical rapid sessions |

## Project Structure

```
01-ipdr-generator/
├── README.md
├── generate_ipdr.py          # CLI (batch + live stream)
├── generator/
│   ├── schema.py             # IPDR record model
│   ├── profiles.py           # Service + persona definitions
│   ├── subscribers.py        # Subscriber pool
│   ├── anomalies.py          # Fraud pattern injection
│   └── ipdr_generator.py     # Session generator engine
└── data/                     # Generated output (created on run)
```

## Use Cases (Portfolio)

| Use case | How this data helps |
|----------|---------------------|
| Billing analytics | Bytes × duration by subscriber |
| Traffic engineering | Peak hour / service mix |
| Fraud detection | Labeled anomalies for ML models |
| Network monitoring | Volume trends by cell and PGW |

## IPDR vs CDR

| Feature | IPDR | CDR |
|---------|------|-----|
| Network | Data (IP) | Voice / SMS |
| Granularity | Session / flow | Call-level |
| Use case | Internet usage | Voice billing |

## Requirements

- Python 3.9+ (stdlib only — no pip install needed)

## Next Steps

- Feed `data/ipdr_simulated.csv` into `04-fraud-or-anomaly-detection`
- Build Streamlit / Power BI dashboards on top of generated data
- Extend with Kafka streaming for a real-time pipeline demo

## Skills Demonstrated

- Telecom domain modeling (IPDR / CDR concepts)
- Realistic synthetic data design
- Subscriber behavior simulation
- Anomaly-rich datasets for analytics and fraud ML
