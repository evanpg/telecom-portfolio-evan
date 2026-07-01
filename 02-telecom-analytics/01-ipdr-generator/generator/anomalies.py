"""Anomaly injection for fraud-detection-ready IPDR data."""

from __future__ import annotations

import random
from datetime import timedelta

from .schema import IPDRRecord


def inject_anomaly(record: IPDRRecord, rng: random.Random) -> IPDRRecord:
  """Apply a random fraud pattern to the record."""
  anomaly_type = rng.choice(
    ["data_exfiltration", "sim_box_fraud", "impossible_travel", "bot_traffic"]
  )

  if anomaly_type == "data_exfiltration":
    record.bytes_up = int(record.bytes_up * rng.uniform(40, 80))
    record.bytes_down = int(record.bytes_down * 0.1)
    record.service_type = "browsing"
    record.app = "Unknown"
    record.destination_domain = "suspicious-upload.example"
    record.anomaly = "data_exfiltration"

  elif anomaly_type == "sim_box_fraud":
    record.service_type = "voip"
    record.app = "Skype"
    record.destination_domain = "voip-gateway.fraud.net"
    record.duration_sec = rng.randint(15, 45)
    record.bytes_up = rng.randint(80_000, 150_000)
    record.bytes_down = rng.randint(80_000, 150_000)
    record.anomaly = "sim_box_fraud"

  elif anomaly_type == "impossible_travel":
    countries = ["PY", "AR", "BR", "UY", "CL", "US", "ES"]
    record.country = rng.choice([c for c in countries if c != record.country])
    record.cell_id = f"CELL_{rng.randint(200, 250):03d}"
    record.anomaly = "impossible_travel"

  elif anomaly_type == "bot_traffic":
    record.duration_sec = rng.randint(1, 3)
    record.bytes_down = rng.randint(500, 2000)
    record.bytes_up = rng.randint(500, 2000)
    record.service_type = "browsing"
    record.app = "Bot"
    record.destination_domain = "cdn.botnet.example"
    record.anomaly = "bot_traffic"

  record.end_time = record.start_time + timedelta(seconds=record.duration_sec)
  return record
