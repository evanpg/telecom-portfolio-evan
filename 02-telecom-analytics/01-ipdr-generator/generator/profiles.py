"""Service profiles, apps, and subscriber personas."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ByteRange:
  low: int
  high: int


@dataclass(frozen=True)
class ServiceProfile:
  bytes_down: ByteRange
  bytes_up: ByteRange
  duration_sec: tuple[int, int]
  apps: tuple[str, ...]
  domains: tuple[str, ...]


SERVICE_PROFILES: dict[str, ServiceProfile] = {
  "streaming": ServiceProfile(
    bytes_down=ByteRange(5_000_000, 20_000_000),
    bytes_up=ByteRange(100_000, 500_000),
    duration_sec=(300, 3600),
    apps=("YouTube", "Netflix", "Disney+", "Twitch"),
    domains=("youtube.com", "netflix.com", "disneyplus.com", "twitch.tv"),
  ),
  "browsing": ServiceProfile(
    bytes_down=ByteRange(10_000, 500_000),
    bytes_up=ByteRange(5_000, 100_000),
    duration_sec=(5, 120),
    apps=("Chrome", "Safari", "Firefox"),
    domains=("google.com", "wikipedia.org", "reddit.com", "news.yahoo.com"),
  ),
  "voip": ServiceProfile(
    bytes_down=ByteRange(50_000, 200_000),
    bytes_up=ByteRange(50_000, 200_000),
    duration_sec=(60, 1800),
    apps=("WhatsApp", "Zoom", "Teams", "Skype"),
    domains=("whatsapp.com", "zoom.us", "teams.microsoft.com", "skype.com"),
  ),
  "gaming": ServiceProfile(
    bytes_down=ByteRange(100_000, 1_000_000),
    bytes_up=ByteRange(50_000, 500_000),
    duration_sec=(300, 7200),
    apps=("Fortnite", "Valorant", "League of Legends", "Minecraft"),
    domains=("epicgames.com", "riotgames.com", "minecraft.net", "steampowered.com"),
  ),
  "social": ServiceProfile(
    bytes_down=ByteRange(200_000, 2_000_000),
    bytes_up=ByteRange(50_000, 400_000),
    duration_sec=(30, 600),
    apps=("TikTok", "Instagram", "Facebook", "X"),
    domains=("tiktok.com", "instagram.com", "facebook.com", "x.com"),
  ),
}

PERSONA_SERVICE_WEIGHTS: dict[str, dict[str, float]] = {
  "heavy_streamer": {"streaming": 0.55, "social": 0.2, "browsing": 0.1, "voip": 0.05, "gaming": 0.1},
  "business_user": {"voip": 0.35, "browsing": 0.4, "streaming": 0.05, "social": 0.1, "gaming": 0.1},
  "casual_mobile": {"social": 0.3, "browsing": 0.35, "streaming": 0.2, "voip": 0.1, "gaming": 0.05},
  "gamer": {"gaming": 0.5, "streaming": 0.15, "voip": 0.15, "social": 0.1, "browsing": 0.1},
  "router_home": {"streaming": 0.4, "browsing": 0.25, "gaming": 0.2, "voip": 0.05, "social": 0.1},
}

COUNTRIES = ("PY", "AR", "BR", "UY", "CL")
NETWORK_ELEMENTS = ("PGW-01", "PGW-02", "SGW-01", "SGW-02", "BRAS-CORE-01")

# Hour (0-23) -> relative traffic weight
HOURLY_TRAFFIC_WEIGHT: dict[int, float] = {
  0: 0.3, 1: 0.2, 2: 0.15, 3: 0.1, 4: 0.1, 5: 0.15,
  6: 0.4, 7: 0.6, 8: 0.8, 9: 0.9, 10: 1.0, 11: 1.0,
  12: 1.1, 13: 1.0, 14: 0.95, 15: 0.9, 16: 0.95, 17: 1.0,
  18: 1.3, 19: 1.5, 20: 1.6, 21: 1.5, 22: 1.2, 23: 0.7,
}
