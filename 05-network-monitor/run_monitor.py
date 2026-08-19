#!/usr/bin/env python3
"""
Local Network Monitoring System — collect traffic, build IPDR records,
run analytics and anomaly detection.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from analytics.traffic_analytics import print_report, summarize
from anomalies.detector import detect_anomalies
from collector.bandwidth import BandwidthMonitor
from collector.ipdr_builder import IPDRBuilder
from collector.sniff import scapy_available
from storage.database import NetworkDatabase


def run_collector(
  duration: int | None,
  interval: float,
  use_scapy: bool,
  session_timeout: int,
  db_path: Path,
  quiet: bool = False,
) -> None:
  from collector.sniff import poll_connections, reverse_dns

  db = NetworkDatabase(db_path)
  builder = IPDRBuilder(session_timeout_sec=session_timeout)
  bw = BandwidthMonitor()
  dns_cache: dict[str, str | None] = {}
  builder.resolve_domain = lambda ip: reverse_dns(ip, dns_cache)

  mode = "scapy packet capture" if use_scapy else "psutil connection polling"
  if duration is None:
    print(f"\n  Live collection via {mode}")
  else:
    print(f"\n  Collecting for {duration}s via {mode}")
  print(f"  Interval: {interval}s | Session timeout: {session_timeout}s")
  print("  Press Ctrl+C to stop.\n")

  end = None if duration is None else time.time() + duration
  total_ipdr = 0

  try:
    while end is None or time.time() < end:
      sample = bw.sample(interval)
      db.insert_bandwidth(sample)
      if not quiet:
        print(
          f"  BW  up {sample.bytes_sent_per_sec:>8,} B/s | "
          f"down {sample.bytes_recv_per_sec:>8,} B/s"
        )

      if use_scapy:
        from collector.sniff import sniff_packets
        sniff_packets(builder, timeout=int(interval))
      else:
        seen = poll_connections(builder, dns_cache)
        if not quiet and seen:
          print(f"  Flows sampled: {seen} active connections")

      completed = builder.flush_expired()
      if completed:
        flagged = detect_anomalies(completed)
        db.insert_ipdr_batch(flagged)
        total_ipdr += len(flagged)
        if not quiet:
          print(f"  IPDR sessions flushed: {len(flagged)} (total {total_ipdr})")

  except KeyboardInterrupt:
    print("\n  Stopping collector...")

  remaining = builder.flush_all()
  if remaining:
    flagged = detect_anomalies(remaining)
    db.insert_ipdr_batch(flagged)
    total_ipdr += len(flagged)

  if duration is None:
    print(f"\n  Live collection stopped. {total_ipdr} IPDR records saved to {db_path}")
  else:
    print(f"\n  Collection complete. {total_ipdr} IPDR records saved to {db_path}")


def run_report(db_path: Path, limit: int) -> None:
  db = NetworkDatabase(db_path)
  rows = db.fetch_ipdr(limit)
  records = [dict(r) for r in rows]
  bw = db.fetch_bandwidth(limit)
  summary = summarize(records, bw)
  print_report(summary)

  anomalies = [r for r in records if r.get("anomaly", "normal") != "normal"]
  if anomalies:
    print("  Detected anomalies:")
    for r in anomalies[:10]:
      print(
        f"    [{r['anomaly']}] {r['src_ip']} -> {r['dst_ip']} "
        f"up={r['bytes_up']:,} down={r['bytes_down']:,}"
      )
    print("")


def run_bandwidth_only(duration: int, interval: float) -> None:
  bw = BandwidthMonitor()
  print(f"\n  Bandwidth monitor ({duration}s)\n")
  end = time.time() + duration
  try:
    while time.time() < end:
      s = bw.sample(interval)
      print(
        f"  Upload: {s.bytes_sent_per_sec:>8,} B/s | "
        f"Download: {s.bytes_recv_per_sec:>8,} B/s"
      )
  except KeyboardInterrupt:
    print("\n  Stopped.")


def main() -> int:
  parser = argparse.ArgumentParser(description="Local network monitoring (IPDR-style)")
  sub = parser.add_subparsers(dest="command")

  collect = sub.add_parser("collect", help="Collect traffic and build IPDR records")
  collect.add_argument("--duration", type=int, default=60, help="Seconds to collect")
  collect.add_argument("--interval", type=float, default=2.0, help="Sample interval")
  collect.add_argument("--timeout", type=int, default=30, help="Session timeout (sec)")
  collect.add_argument("--scapy", action="store_true", help="Use scapy packet capture")
  collect.add_argument("--db", type=Path, default=Path("data/network_monitor.db"))

  live = sub.add_parser("live", help="Run continuous live collection for the dashboard")
  live.add_argument("--interval", type=float, default=2.0, help="Sample interval")
  live.add_argument("--timeout", type=int, default=30, help="Session timeout (sec)")
  live.add_argument("--scapy", action="store_true", help="Use scapy packet capture")
  live.add_argument("--db", type=Path, default=Path("data/network_monitor.db"))
  live.add_argument("--quiet", action="store_true", help="Minimal console output")

  report = sub.add_parser("report", help="Show analytics from database")
  report.add_argument("--db", type=Path, default=Path("data/network_monitor.db"))
  report.add_argument("--limit", type=int, default=5000)

  bw = sub.add_parser("bandwidth", help="Bandwidth-only monitor")
  bw.add_argument("--duration", type=int, default=30)
  bw.add_argument("--interval", type=float, default=1.0)

  args = parser.parse_args()

  print("=" * 54)
  print("  Local Network Monitor — Telecom-Style IPDR Pipeline")
  print("=" * 54)

  if args.command == "collect":
    if args.scapy and not scapy_available():
      print("\n  scapy not installed — falling back to psutil connection polling.")
      print("  Install: pip install scapy  (+ Npcap on Windows)\n")
      args.scapy = False
    run_collector(args.duration, args.interval, args.scapy, args.timeout, args.db)
    run_report(args.db, args.limit if hasattr(args, "limit") else 5000)
    return 0

  if args.command == "live":
    if args.scapy and not scapy_available():
      print("\n  scapy not installed — falling back to psutil connection polling.")
      print("  Install: pip install scapy  (+ Npcap on Windows)\n")
      args.scapy = False
    run_collector(None, args.interval, args.scapy, args.timeout, args.db, quiet=args.quiet)
    return 0

  if args.command == "report":
    run_report(args.db, args.limit)
    return 0

  if args.command == "bandwidth":
    run_bandwidth_only(args.duration, args.interval)
    return 0

  parser.print_help()
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
