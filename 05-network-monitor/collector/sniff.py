"""Packet capture — scapy when available, psutil connections as fallback."""

from __future__ import annotations

import socket
from datetime import datetime, timezone
from typing import Callable

try:
  import psutil
except ImportError:
  psutil = None  # type: ignore

_scapy_checked = False
_scapy_available = False


def scapy_available() -> bool:
  global _scapy_checked, _scapy_available
  if not _scapy_checked:
    try:
      import scapy.all  # noqa: F401
      _scapy_available = True
    except ImportError:
      _scapy_available = False
    _scapy_checked = True
  return _scapy_available


def reverse_dns(ip: str, cache: dict[str, str | None]) -> str | None:
  if ip in cache:
    return cache[ip]
  if ip.startswith(("127.", "10.", "192.168.", "172.")):
    cache[ip] = None
    return None
  try:
    socket.setdefaulttimeout(0.5)
    host, _, _ = socket.gethostbyaddr(ip)
    cache[ip] = host
    return host
  except (OSError, socket.herror, socket.timeout):
    cache[ip] = None
    return None
  finally:
    socket.setdefaulttimeout(None)


def process_scapy_packet(packet, builder, dns_cache: dict[str, str | None]) -> None:
  from scapy.all import IP, TCP, UDP  # lazy import

  if not packet.haslayer(IP):
    return
  ip_layer = packet[IP]
  src = ip_layer.src
  dst = ip_layer.dst
  proto = ip_layer.proto
  payload_len = len(packet)
  src_port = dst_port = None

  if packet.haslayer(TCP):
    src_port = int(packet[TCP].sport)
    dst_port = int(packet[TCP].dport)
  elif packet.haslayer(UDP):
    src_port = int(packet[UDP].sport)
    dst_port = int(packet[UDP].dport)

  builder.add_packet(
    src, dst, proto, payload_len,
    src_port=src_port, dst_port=dst_port,
    when=datetime.now(timezone.utc),
  )

  remote = dst if src in builder.local_ips else src
  if remote not in dns_cache:
    reverse_dns(remote, dns_cache)


def sniff_packets(
  builder,
  *,
  count: int = 0,
  timeout: int | None = None,
  interface: str | None = None,
) -> None:
  if not scapy_available():
    raise RuntimeError(
      "scapy is not installed. Run: pip install scapy\n"
      "On Windows, also install Npcap: https://nmap.org/npcap/"
    )

  from scapy.all import sniff

  dns_cache: dict[str, str | None] = {}

  def _handler(packet) -> None:
    process_scapy_packet(packet, builder, dns_cache)

  sniff(
    prn=_handler,
    store=False,
    count=count,
    timeout=timeout,
    iface=interface,
  )


def poll_connections(builder, dns_cache: dict[str, str | None], max_conns: int = 50) -> int:
  """Sample active TCP/UDP connections via psutil."""
  if psutil is None:
    return 0

  seen = 0
  now = datetime.now(timezone.utc)
  try:
    connections = psutil.net_connections(kind="inet")
  except (psutil.AccessDenied, psutil.Error):
    return 0

  for conn in connections[:max_conns]:
    if not conn.raddr or not conn.laddr:
      continue
    if conn.status not in ("ESTABLISHED", "NONE", "SYN_SENT", "SYN_RECV"):
      continue

    src_ip = conn.laddr.ip
    dst_ip = conn.raddr.ip
    src_port = conn.laddr.port
    dst_port = conn.raddr.port
    proto = "TCP" if conn.type.name == "SOCK_STREAM" else "UDP"
    payload = 512

    builder.add_packet(
      src_ip, dst_ip, proto, payload,
      src_port=src_port, dst_port=dst_port,
      when=now,
    )
    seen += 1
  return seen
