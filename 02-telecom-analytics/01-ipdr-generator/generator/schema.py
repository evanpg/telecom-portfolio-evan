"""IPDR record schema."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass
class IPDRRecord:
  subscriber_id: str
  imsi: str
  ip_address: str
  cell_id: str
  start_time: datetime
  end_time: datetime
  duration_sec: int
  bytes_up: int
  bytes_down: int
  service_type: str
  app: str
  destination_ip: str
  destination_domain: str
  country: str
  device_type: str
  network_element: str
  anomaly: str = "normal"

  def to_dict(self) -> dict:
    row = asdict(self)
    row["start_time"] = self.start_time.isoformat()
    row["end_time"] = self.end_time.isoformat()
    return row
