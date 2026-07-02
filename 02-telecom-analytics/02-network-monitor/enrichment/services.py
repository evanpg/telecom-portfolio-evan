"""Port and protocol enrichment for IPDR records."""

from __future__ import annotations

WELL_KNOWN_PORTS: dict[int, tuple[str, str]] = {
  53: ("DNS", "dns"),
  80: ("HTTP", "browsing"),
  443: ("HTTPS", "browsing"),
  5228: ("Google", "browsing"),
  1935: ("RTMP", "streaming"),
  3478: ("STUN", "voip"),
  5060: ("SIP", "voip"),
  27015: ("Steam", "gaming"),
  19302: ("Discord", "social"),
}

DOMAIN_HINTS: dict[str, tuple[str, str]] = {
  "google": ("Google", "browsing"),
  "youtube": ("YouTube", "streaming"),
  "netflix": ("Netflix", "streaming"),
  "facebook": ("Facebook", "social"),
  "instagram": ("Instagram", "social"),
  "whatsapp": ("WhatsApp", "voip"),
  "zoom": ("Zoom", "voip"),
  "microsoft": ("Microsoft", "browsing"),
  "amazon": ("Amazon", "browsing"),
  "cloudflare": ("Cloudflare", "browsing"),
  "apple": ("Apple", "browsing"),
  "tiktok": ("TikTok", "social"),
  "discord": ("Discord", "social"),
  "twitch": ("Twitch", "streaming"),
}


def protocol_name(proto: int | str) -> str:
  mapping = {6: "TCP", 17: "UDP", 1: "ICMP"}
  if isinstance(proto, str):
    return proto.upper()
  return mapping.get(proto, str(proto))


def classify_port(port: int | None) -> tuple[str, str]:
  if port and port in WELL_KNOWN_PORTS:
    return WELL_KNOWN_PORTS[port]
  if port and port == 443:
    return ("HTTPS", "browsing")
  return ("Unknown", "browsing")


def classify_domain(domain: str | None) -> tuple[str, str]:
  if not domain:
    return ("Unknown", "browsing")
  lower = domain.lower()
  for hint, (app, service) in DOMAIN_HINTS.items():
    if hint in lower:
      return (app, service)
  return (domain.split(".")[0].title(), "browsing")
