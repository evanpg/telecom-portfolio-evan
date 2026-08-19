"""Streamlit dashboard for network monitor data."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
  import streamlit as st
except ImportError:
  raise SystemExit("Install streamlit: pip install streamlit")

from analytics.traffic_analytics import summarize, top_domains, top_apps
from storage.database import NetworkDatabase

st.set_page_config(page_title="Network Monitor", layout="wide")
st.title("Local Network Monitor — IPDR Dashboard")

db_path = ROOT / "data" / "network_monitor.db"
if not db_path.exists():
  st.warning("No data yet. Run: python run_monitor.py collect --duration 60")
  st.stop()

db = NetworkDatabase(db_path)
records = [dict(r) for r in db.fetch_ipdr(5000)]
bw_rows = db.fetch_bandwidth(500)
summary = summarize(records, bw_rows)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Sessions", summary["total_sessions"])
c2.metric("Download (MB)", f"{summary['total_bytes_down'] / 1e6:.1f}")
c3.metric("Upload (MB)", f"{summary['total_bytes_up'] / 1e6:.1f}")
c4.metric("Anomalies", summary["anomalies"])

st.subheader("Upload vs Download")
ratio = summary["traffic_ratio"]
st.progress(ratio["download_pct"] / 100, text=f"Download {ratio['download_pct']}%")
st.progress(ratio["upload_pct"] / 100, text=f"Upload {ratio['upload_pct']}%")

col1, col2 = st.columns(2)
with col1:
  st.subheader("Top Apps")
  st.table({app: count for app, count in top_apps(records, 10)})
with col2:
  st.subheader("Top Domains (bytes)")
  st.table({d: f"{b / 1e6:.2f} MB" for d, b in top_domains(records, 10)})

st.subheader("Recent IPDR Sessions")
st.dataframe(records[:50], use_container_width=True)

anomalies = [r for r in records if r.get("anomaly", "normal") != "normal"]
if anomalies:
  st.subheader("Anomalies")
  st.dataframe(anomalies[:20], use_container_width=True)
