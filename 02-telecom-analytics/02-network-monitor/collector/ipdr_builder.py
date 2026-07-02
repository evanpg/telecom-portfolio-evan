"""Flow tracking and IPDR session reconstruction."""

from __future__ import annotations

import socket
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

try:
  import psutil
except ImportError:
  psutil = None  # type: ignore

from enrichment.services import classify_domain, classify_port, protocol_name


def local_ip_addresses() -> set[str]:
  """Collect this host's addresses (similar to ipconfig / ifconfig)."""
  ips: set[str] = {"127.0.0.1", "::1"}

  if psutil is not None:
    try:
      for addrs in psutil.net_if_addrs().values():
        for addr in addrs:
          if addr.family == socket.AF_INET:
            ips.add(addr.address)
          elif addr.family == socket.AF_INET6 and not addr.address.startswith("fe80:"):
            ips.add(addr.address.split("%")[0])
    except (OSError, AttributeError):
      pass

  try:
    hostname = socket.gethostname()
    _, _, addrs = socket.gethostbyname_ex(hostname)
    ips.update(addrs)
  except OSError:
    pass
  try:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
      sock.connect(("8.8.8.8", 80))
      ips.add(sock.getsockname()[0])
  except OSError:
    pass
  return ips


@dataclass
class FlowKey:
  src_ip: str
  dst_ip: str
  protocol: str
  dst_port: int | None


@dataclass
class FlowState:
  key: FlowKey
  local_ip: str = ""
  remote_ip: str = ""
  outbound: bool = True
  src_port: int | None = None
  bytes_up: int = 0
  bytes_down: int = 0
  packet_count: int = 0
  first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
  last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
  domain: str | None = None

  def touch(self, when: datetime | None = None) -> None:
    self.last_seen = when or datetime.now(timezone.utc)


class IPDRBuilder:
  """Aggregate packets/connections into IPDR-like session records."""

  def __init__(
    self,
    subscriber_id: str = "local_user",
    device_type: str = "Laptop",
    network_element: str = "LOCAL-NIC",
    session_timeout_sec: int = 60,
    resolve_domain: Callable[[str], str | None] | None = None,
  ) -> None:
    self.subscriber_id = subscriber_id
    self.device_type = device_type
    self.network_element = network_element
    self.session_timeout_sec = session_timeout_sec
    self.resolve_domain = resolve_domain
    self.local_ips = local_ip_addresses()
    self.flows: dict[tuple, FlowState] = {}

  def _flow_id(self, key: FlowKey) -> tuple:
    return (key.src_ip, key.dst_ip, key.protocol, key.dst_port)

  def add_packet(
    self,
    src_ip: str,
    dst_ip: str,
    protocol: int | str,
    payload_len: int,
    *,
    src_port: int | None = None,
    dst_port: int | None = None,
    when: datetime | None = None,
  ) -> None:
    proto = protocol_name(protocol)
    now = when or datetime.now(timezone.utc)

    if src_ip in self.local_ips:
      key = FlowKey(src_ip, dst_ip, proto, dst_port)
      local_ip, remote_ip, outbound = src_ip, dst_ip, True
      is_upload = True
    elif dst_ip in self.local_ips:
      key = FlowKey(dst_ip, src_ip, proto, src_port)
      local_ip, remote_ip, outbound = dst_ip, src_ip, False
      is_upload = False
    else:
      key = FlowKey(src_ip, dst_ip, proto, dst_port)
      local_ip, remote_ip = src_ip, dst_ip
      outbound = src_ip in self.local_ips
      is_upload = outbound

    fid = self._flow_id(key)
    flow = self.flows.get(fid)
    if flow is None:
      flow = FlowState(
        key=key,
        local_ip=local_ip,
        remote_ip=remote_ip,
        outbound=outbound,
        src_port=src_port,
      )
      self.flows[fid] = flow

    if is_upload:
      flow.bytes_up += payload_len
    else:
      flow.bytes_down += payload_len
    flow.packet_count += 1
    flow.touch(now)
    if flow.src_port is None and src_port:
      flow.src_port = src_port

  def flush_expired(self) -> list[dict]:
    now = datetime.now(timezone.utc)
    completed: list[dict] = []
    expired_keys: list[tuple] = []

    for fid, flow in self.flows.items():
      age = (now - flow.last_seen).total_seconds()
      if age < self.session_timeout_sec:
        continue
      expired_keys.append(fid)
      completed.append(self._flow_to_ipdr(flow))

    for fid in expired_keys:
      del self.flows[fid]
    return completed

  def flush_all(self) -> list[dict]:
    records = [self._flow_to_ipdr(flow) for flow in self.flows.values()]
    self.flows.clear()
    return records

  def _flow_to_ipdr(self, flow: FlowState) -> dict:
    duration = max(int((flow.last_seen - flow.first_seen).total_seconds()), 1)
    port = flow.key.dst_port
    app, service = classify_port(port)

    domain = flow.domain
    if not domain and self.resolve_domain:
      domain = self.resolve_domain(flow.key.dst_ip)
    if domain:
      app, service = classify_domain(domain)

    if flow.outbound:
      src_ip, dst_ip = flow.local_ip, flow.remote_ip
    else:
      src_ip, dst_ip = flow.remote_ip, flow.local_ip

    return {
      "record_id": str(uuid.uuid4()),
      "subscriber_id": self.subscriber_id,
      "src_ip": src_ip,
      "dst_ip": dst_ip,
      "protocol": flow.key.protocol,
      "dst_port": port,
      "start_time": flow.first_seen.isoformat(),
      "end_time": flow.last_seen.isoformat(),
      "duration_sec": duration,
      "bytes_up": flow.bytes_up,
      "bytes_down": flow.bytes_down,
      "packets": flow.packet_count,
      "service_type": service,
      "app": app,
      "destination_domain": domain or "",
      "device_type": self.device_type,
      "network_element": self.network_element,
      "anomaly": "normal",
    }
