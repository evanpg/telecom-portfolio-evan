"""SQLite storage for IPDR records and bandwidth samples."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "data" / "network_monitor.db"

IPDR_DDL = """
CREATE TABLE IF NOT EXISTS ipdr_records (
    record_id TEXT PRIMARY KEY,
    subscriber_id TEXT NOT NULL,
    src_ip TEXT NOT NULL,
    dst_ip TEXT NOT NULL,
    protocol TEXT,
    dst_port INTEGER,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    duration_sec INTEGER,
    bytes_up INTEGER,
    bytes_down INTEGER,
    packets INTEGER,
    service_type TEXT,
    app TEXT,
    destination_domain TEXT,
    device_type TEXT,
    network_element TEXT,
    anomaly TEXT DEFAULT 'normal',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bandwidth_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    bytes_sent_per_sec INTEGER,
    bytes_recv_per_sec INTEGER,
    packets_sent_per_sec INTEGER,
    packets_recv_per_sec INTEGER
);
"""


class NetworkDatabase:
  def __init__(self, path: Path | str = DEFAULT_DB) -> None:
    self.path = Path(path)
    self.path.parent.mkdir(parents=True, exist_ok=True)
    self._init_db()

  def _connect(self) -> sqlite3.Connection:
    conn = sqlite3.connect(self.path)
    conn.row_factory = sqlite3.Row
    return conn

  def _init_db(self) -> None:
    with self._connect() as conn:
      conn.executescript(IPDR_DDL)

  def insert_ipdr(self, record: dict) -> None:
    with self._connect() as conn:
      conn.execute(
        """
        INSERT OR REPLACE INTO ipdr_records (
            record_id, subscriber_id, src_ip, dst_ip, protocol, dst_port,
            start_time, end_time, duration_sec, bytes_up, bytes_down, packets,
            service_type, app, destination_domain, device_type, network_element, anomaly
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
          record["record_id"],
          record["subscriber_id"],
          record["src_ip"],
          record["dst_ip"],
          record.get("protocol"),
          record.get("dst_port"),
          record["start_time"],
          record["end_time"],
          record["duration_sec"],
          record["bytes_up"],
          record["bytes_down"],
          record.get("packets", 0),
          record["service_type"],
          record["app"],
          record.get("destination_domain", ""),
          record["device_type"],
          record["network_element"],
          record.get("anomaly", "normal"),
        ),
      )

  def insert_ipdr_batch(self, records: list[dict]) -> int:
    for record in records:
      self.insert_ipdr(record)
    return len(records)

  def insert_bandwidth(self, sample) -> None:
    with self._connect() as conn:
      conn.execute(
        """
        INSERT INTO bandwidth_samples
        (timestamp, bytes_sent_per_sec, bytes_recv_per_sec, packets_sent_per_sec, packets_recv_per_sec)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
          sample.timestamp,
          sample.bytes_sent_per_sec,
          sample.bytes_recv_per_sec,
          sample.packets_sent_per_sec,
          sample.packets_recv_per_sec,
        ),
      )

  def fetch_ipdr(self, limit: int = 1000) -> list[sqlite3.Row]:
    with self._connect() as conn:
      return conn.execute(
        "SELECT * FROM ipdr_records ORDER BY end_time DESC LIMIT ?",
        (limit,),
      ).fetchall()

  def fetch_bandwidth(self, limit: int = 500) -> list[sqlite3.Row]:
    with self._connect() as conn:
      return conn.execute(
        "SELECT * FROM bandwidth_samples ORDER BY timestamp DESC LIMIT ?",
        (limit,),
      ).fetchall()

  def update_anomaly(self, record_id: str, anomaly: str) -> None:
    with self._connect() as conn:
      conn.execute(
        "UPDATE ipdr_records SET anomaly = ? WHERE record_id = ?",
        (anomaly, record_id),
      )
