"""Core IPDR session generator with realistic traffic patterns."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from .anomalies import inject_anomaly
from .profiles import (
  HOURLY_TRAFFIC_WEIGHT,
  NETWORK_ELEMENTS,
  PERSONA_SERVICE_WEIGHTS,
  SERVICE_PROFILES,
)
from .schema import IPDRRecord
from .subscribers import Subscriber, _random_ip, build_subscriber_pool


def _weighted_choice(weights: dict[str, float], rng: random.Random) -> str:
  items = list(weights.keys())
  probs = [weights[k] for k in items]
  return rng.choices(items, weights=probs, k=1)[0]


def _pick_start_time(window_hours: int, rng: random.Random) -> datetime:
  """Bias session starts toward peak hours using hourly weights."""
  base = datetime.now(timezone.utc) - timedelta(hours=window_hours)
  offset_sec = rng.randint(0, window_hours * 3600)
  candidate = base + timedelta(seconds=offset_sec)
  weight = HOURLY_TRAFFIC_WEIGHT.get(candidate.hour, 1.0)
  if rng.random() > weight / 1.6:
    candidate += timedelta(hours=rng.randint(18, 21) - candidate.hour)
  return candidate.replace(microsecond=0)


class IPDRGenerator:
  def __init__(
    self,
    *,
    subscriber_count: int = 500,
    anomaly_rate: float = 0.05,
    seed: int | None = None,
  ) -> None:
    self.rng = random.Random(seed)
    self.anomaly_rate = anomaly_rate
    self.subscribers = build_subscriber_pool(subscriber_count, self.rng)
    self._subscriber_index = 0

  def _next_subscriber(self) -> Subscriber:
    sub = self.subscribers[self._subscriber_index % len(self.subscribers)]
    self._subscriber_index += 1
    return sub

  def generate_session(
    self,
    subscriber: Subscriber | None = None,
    *,
    window_hours: int = 24,
  ) -> IPDRRecord:
    sub = subscriber or self._next_subscriber()
    service = _weighted_choice(PERSONA_SERVICE_WEIGHTS[sub.persona], self.rng)
    profile = SERVICE_PROFILES[service]
    app_idx = self.rng.randrange(len(profile.apps))

    duration = self.rng.randint(*profile.duration_sec)
    start = _pick_start_time(window_hours, self.rng)
    end = start + timedelta(seconds=duration)

    bytes_down = int(self.rng.uniform(profile.bytes_down.low, profile.bytes_down.high))
    bytes_up = int(self.rng.uniform(profile.bytes_up.low, profile.bytes_up.high))

    record = IPDRRecord(
      subscriber_id=sub.subscriber_id,
      imsi=sub.imsi,
      ip_address=sub.ip_address,
      cell_id=sub.cell_id,
      start_time=start,
      end_time=end,
      duration_sec=duration,
      bytes_up=bytes_up,
      bytes_down=bytes_down,
      service_type=service,
      app=profile.apps[app_idx],
      destination_ip=_random_ip(self.rng),
      destination_domain=profile.domains[app_idx],
      country=sub.home_country,
      device_type=sub.device_type,
      network_element=self.rng.choice(NETWORK_ELEMENTS),
    )

    if self.rng.random() < self.anomaly_rate:
      record = inject_anomaly(record, self.rng)

    return record

  def generate_batch(self, count: int, *, window_hours: int = 24) -> list[IPDRRecord]:
    return [self.generate_session(window_hours=window_hours) for _ in range(count)]


def generate_batch(
  count: int = 10_000,
  *,
  subscriber_count: int = 500,
  seed: int | None = 42,
  window_hours: int = 24,
) -> list[IPDRRecord]:
  gen = IPDRGenerator(subscriber_count=subscriber_count, seed=seed)
  return gen.generate_batch(count, window_hours=window_hours)
