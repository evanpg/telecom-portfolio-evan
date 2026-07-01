"""Synthetic subscriber pool with stable identities."""

from __future__ import annotations

import random
from dataclasses import dataclass

from .profiles import COUNTRIES, PERSONA_SERVICE_WEIGHTS


@dataclass(frozen=True)
class Subscriber:
  subscriber_id: str
  imsi: str
  ip_address: str
  persona: str
  home_country: str
  device_type: str
  cell_id: str


DEVICE_BY_PERSONA = {
  "heavy_streamer": ("Android", "iOS", "Smart TV"),
  "business_user": ("iOS", "Android", "Laptop"),
  "casual_mobile": ("Android", "iOS"),
  "gamer": ("Android", "PC", "PlayStation"),
  "router_home": ("Router", "Smart TV", "Android"),
}


def _random_ip(rng: random.Random) -> str:
  return ".".join(str(rng.randint(1, 254)) for _ in range(4))


def build_subscriber_pool(count: int, rng: random.Random) -> list[Subscriber]:
  personas = list(PERSONA_SERVICE_WEIGHTS.keys())
  pool: list[Subscriber] = []

  for i in range(count):
    persona = rng.choice(personas)
    sid = f"SUB{100000 + i:06d}"
    pool.append(
      Subscriber(
        subscriber_id=sid,
        imsi=f"74801{rng.randint(100000000, 999999999)}",
        ip_address=_random_ip(rng),
        persona=persona,
        home_country=rng.choice(COUNTRIES),
        device_type=rng.choice(DEVICE_BY_PERSONA[persona]),
        cell_id=f"CELL_{rng.randint(1, 120):03d}",
      )
    )
  return pool
