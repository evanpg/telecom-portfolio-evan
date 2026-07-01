#!/usr/bin/env python3
"""
IPDR Generator — synthetic telecom IP Detail Records.

Generates realistic session-level traffic with subscriber personas,
time-of-day patterns, and injected anomalies for analytics / fraud demos.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generator import IPDRGenerator

CSV_FIELDS = [
  "subscriber_id",
  "imsi",
  "ip_address",
  "cell_id",
  "start_time",
  "end_time",
  "duration_sec",
  "bytes_up",
  "bytes_down",
  "service_type",
  "app",
  "destination_ip",
  "destination_domain",
  "country",
  "device_type",
  "network_element",
  "anomaly",
]


def write_csv(records: list, path: Path) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  with path.open("w", newline="", encoding="utf-8") as fh:
    writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for record in records:
      writer.writerow(record.to_dict())


def write_json(records: list, path: Path) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  with path.open("w", encoding="utf-8") as fh:
    json.dump([r.to_dict() for r in records], fh, indent=2)


def print_summary(records: list) -> None:
  total = len(records)
  anomalies = sum(1 for r in records if r.anomaly != "normal")
  by_service: dict[str, int] = {}
  bytes_down = 0
  for r in records:
    by_service[r.service_type] = by_service.get(r.service_type, 0) + 1
    bytes_down += r.bytes_down

  print("\n  Generation Summary")
  print("  " + "-" * 40)
  print(f"  Records:        {total:,}")
  print(f"  Anomalies:      {anomalies:,} ({100 * anomalies / total:.1f}%)")
  print(f"  Total download: {bytes_down / 1e9:.2f} GB")
  print("\n  By service type:")
  for service, count in sorted(by_service.items(), key=lambda x: -x[1]):
    print(f"    {service:<12} {count:>6,} ({100 * count / total:.1f}%)")
  print("")


def run_live(gen: IPDRGenerator, interval: float, count: int | None, output: Path | None) -> None:
  print(f"\n  Live IPDR stream (every {interval}s). Ctrl+C to stop.\n")
  fh = None
  writer = None
  if output:
    output.parent.mkdir(parents=True, exist_ok=True)
    fh = output.open("w", newline="", encoding="utf-8")
    writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
    writer.writeheader()

  emitted = 0
  try:
    while count is None or emitted < count:
      record = gen.generate_session()
      line = json.dumps(record.to_dict())
      print(line, flush=True)
      if writer:
        writer.writerow(record.to_dict())
        fh.flush()
      emitted += 1
      time.sleep(interval)
  except KeyboardInterrupt:
    print("\n  Stream stopped.")
  finally:
    if fh:
      fh.close()
    print(f"  Emitted {emitted:,} records.")


def main() -> int:
  parser = argparse.ArgumentParser(description="Generate synthetic IPDR traffic records")
  parser.add_argument("-n", "--count", type=int, default=10_000, help="Number of records (batch mode)")
  parser.add_argument("-s", "--subscribers", type=int, default=500, help="Unique subscribers in pool")
  parser.add_argument("--seed", type=int, default=42, help="Random seed")
  parser.add_argument("--hours", type=int, default=24, help="Time window for session starts")
  parser.add_argument("--anomaly-rate", type=float, default=0.05, help="Anomaly injection rate")
  parser.add_argument("-o", "--output", type=Path, help="Output file (.csv or .json)")
  parser.add_argument("--live", action="store_true", help="Stream records in real time")
  parser.add_argument("--interval", type=float, default=1.0, help="Seconds between live records")
  parser.add_argument("--live-count", type=int, help="Max records in live mode (default: unlimited)")
  args = parser.parse_args()

  gen = IPDRGenerator(
    subscriber_count=args.subscribers,
    anomaly_rate=args.anomaly_rate,
    seed=args.seed,
  )

  print("=" * 50)
  print("  IPDR Generator — Telecom Traffic Simulator")
  print("=" * 50)

  if args.live:
    run_live(gen, args.interval, args.live_count, args.output)
    return 0

  records = gen.generate_batch(args.count, window_hours=args.hours)
  print_summary(records)

  out = args.output or Path("data/ipdr_simulated.csv")
  if out.suffix.lower() == ".json":
    write_json(records, out)
  else:
    write_json(records, out.with_suffix(".json"))
    write_csv(records, out)

  print(f"  Saved: {out}")
  print(f"  Saved: {out.with_suffix('.json')}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
