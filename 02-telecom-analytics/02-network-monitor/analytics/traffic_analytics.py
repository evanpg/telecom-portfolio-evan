"""Traffic analytics over collected IPDR records."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime


def _parse_hour(iso_time: str) -> int:
  try:
    return datetime.fromisoformat(iso_time.replace("Z", "+00:00")).hour
  except ValueError:
    return 0


def top_domains(records: list[dict], limit: int = 10) -> list[tuple[str, int]]:
  counts: Counter[str] = Counter()
  for r in records:
    domain = r.get("destination_domain") or r.get("dst_ip", "unknown")
    if domain:
      counts[domain] += r.get("bytes_down", 0) + r.get("bytes_up", 0)
  return counts.most_common(limit)


def top_apps(records: list[dict], limit: int = 10) -> list[tuple[str, int]]:
  counts: Counter[str] = Counter()
  for r in records:
    counts[r.get("app", "Unknown")] += 1
  return counts.most_common(limit)


def service_mix(records: list[dict]) -> dict[str, int]:
  counts: Counter[str] = Counter()
  for r in records:
    counts[r.get("service_type", "unknown")] += 1
  return dict(counts)


def upload_download_ratio(records: list[dict]) -> dict[str, float]:
  up = sum(r.get("bytes_up", 0) for r in records)
  down = sum(r.get("bytes_down", 0) for r in records)
  total = up + down or 1
  return {
    "bytes_up": up,
    "bytes_down": down,
    "upload_pct": round(100 * up / total, 2),
    "download_pct": round(100 * down / total, 2),
  }


def peak_hours(records: list[dict]) -> dict[int, int]:
  hours: dict[int, int] = defaultdict(int)
  for r in records:
    hours[_parse_hour(r.get("start_time", ""))] += 1
  return dict(sorted(hours.items()))


def summarize(records: list[dict], bandwidth_rows: list | None = None) -> dict:
  return {
    "total_sessions": len(records),
    "total_bytes_up": sum(r.get("bytes_up", 0) for r in records),
    "total_bytes_down": sum(r.get("bytes_down", 0) for r in records),
    "top_domains": top_domains(records, 5),
    "top_apps": top_apps(records, 5),
    "service_mix": service_mix(records),
    "traffic_ratio": upload_download_ratio(records),
    "peak_hours": peak_hours(records),
    "anomalies": sum(1 for r in records if r.get("anomaly", "normal") != "normal"),
    "bandwidth_samples": len(bandwidth_rows or []),
  }


def print_report(summary: dict) -> None:
  print("\n  Traffic Analytics Report")
  print("  " + "=" * 50)
  print(f"  Sessions:       {summary['total_sessions']:,}")
  print(f"  Upload:         {summary['total_bytes_up'] / 1e6:.2f} MB")
  print(f"  Download:       {summary['total_bytes_down'] / 1e6:.2f} MB")
  print(f"  Anomalies:      {summary['anomalies']:,}")
  ratio = summary["traffic_ratio"]
  print(f"  Up/Down ratio:  {ratio['upload_pct']}% / {ratio['download_pct']}%")

  print("\n  Top apps:")
  for app, count in summary["top_apps"]:
    print(f"    {app:<20} {count:>5} sessions")

  print("\n  Top destinations (by bytes):")
  for domain, bytes_total in summary["top_domains"]:
    print(f"    {domain:<30} {bytes_total / 1e6:>8.2f} MB")

  print("\n  Service mix:")
  for service, count in sorted(summary["service_mix"].items(), key=lambda x: -x[1]):
    print(f"    {service:<12} {count:>5}")
  print("")
