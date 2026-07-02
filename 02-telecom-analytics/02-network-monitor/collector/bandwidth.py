"""Bandwidth sampling via psutil."""

from __future__ import annotations

import time
from dataclasses import dataclass

try:
  import psutil
except ImportError as exc:
  raise ImportError("psutil is required. Install with: pip install psutil") from exc


@dataclass
class BandwidthSample:
  timestamp: float
  bytes_sent_per_sec: int
  bytes_recv_per_sec: int
  packets_sent_per_sec: int
  packets_recv_per_sec: int


class BandwidthMonitor:
  def __init__(self) -> None:
    self._last = psutil.net_io_counters()

  def sample(self, interval: float = 1.0) -> BandwidthSample:
    time.sleep(interval)
    current = psutil.net_io_counters()
    sent = current.bytes_sent - self._last.bytes_sent
    recv = current.bytes_recv - self._last.bytes_recv
    psent = current.packets_sent - self._last.packets_sent
    precv = current.packets_recv - self._last.packets_recv
    self._last = current
    return BandwidthSample(
      timestamp=time.time(),
      bytes_sent_per_sec=max(sent, 0),
      bytes_recv_per_sec=max(recv, 0),
      packets_sent_per_sec=max(psent, 0),
      packets_recv_per_sec=max(precv, 0),
    )

  @staticmethod
  def snapshot() -> dict[str, int]:
    counters = psutil.net_io_counters()
    return {
      "bytes_sent": counters.bytes_sent,
      "bytes_recv": counters.bytes_recv,
      "packets_sent": counters.packets_sent,
      "packets_recv": counters.packets_recv,
    }
