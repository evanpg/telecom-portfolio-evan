"""Anomaly detection on IPDR-style session records."""

from __future__ import annotations

import statistics
from collections import Counter


def detect_anomalies(records: list[dict]) -> list[dict]:
  """Flag suspicious sessions; returns records with updated anomaly field."""
  if not records:
    return records

  upload_values = [r.get("bytes_up", 0) for r in records]
  down_values = [r.get("bytes_down", 0) for r in records]
  duration_values = [r.get("duration_sec", 0) for r in records]

  up_median = statistics.median(upload_values) or 1
  down_median = statistics.median(down_values) or 1
  dur_median = statistics.median(duration_values) or 1

  dst_counts = Counter(r.get("dst_ip") for r in records)

  flagged: list[dict] = []
  for record in records:
    r = dict(record)
    r["anomaly"] = "normal"
    up = r.get("bytes_up", 0)
    down = r.get("bytes_down", 0)
    dur = r.get("duration_sec", 0)
    dst = r.get("dst_ip", "")

    if up > up_median * 20 and up > down * 5:
      r["anomaly"] = "upload_spike"
    elif dst_counts[dst] > max(10, len(records) * 0.15):
      r["anomaly"] = "bot_connections"
    elif dur < dur_median * 0.05 and (up + down) < 1000:
      r["anomaly"] = "micro_flow"
    elif not r.get("destination_domain") and r.get("dst_port") not in (80, 443, 53):
      r["anomaly"] = "unknown_destination"

    flagged.append(r)
  return flagged
