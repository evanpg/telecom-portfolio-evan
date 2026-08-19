/**
 * Network Monitor — Node.js dashboard API + static UI server.
 * Reads IPDR records and bandwidth samples from SQLite.
 */

const path = require("path");
const fs = require("fs");
const os = require("os");
const express = require("express");
const Database = require("better-sqlite3");
const geoip = require("geoip-lite");

const PORT = process.env.PORT || 3000;
const DB_PATH =
  process.env.DB_PATH ||
  path.join(__dirname, "..", "data", "network_monitor.db");

const SESSION_BUCKET_SEC = 5;
const SESSION_WINDOW_SEC = 60;
const LIVE_MODE = process.env.LIVE_MODE === "1";
const LIVE_WINDOW_SEC = Number(process.env.LIVE_WINDOW_SEC) || 300;
const LIVE_STALE_SEC = Number(process.env.LIVE_STALE_SEC) || 15;
const AUTO_BASELINE_SEC = Number(process.env.AUTO_BASELINE_SEC) || 180;
const BASELINE_BUCKET_SEC = 5;
const SERVER_START_MS = Date.now();

const BASELINE_PATH =
  process.env.BASELINE_PATH || path.join(__dirname, "data", "baseline.json");
const {
  PRESET_BASELINES,
  ensurePresetBaselines,
  readPresetBaseline,
} = require("./preset-baselines");

const ANOMALY_META = {
  upload_spike: {
    label: "Upload Spike",
    description: "Upload exceeds 20× the median and is 5× greater than download.",
  },
  bot_connections: {
    label: "Bot Connections",
    description: "Unusually high number of sessions to the same destination IP.",
  },
  micro_flow: {
    label: "Micro Flow",
    description: "Very short session with minimal bytes transferred.",
  },
  unknown_destination: {
    label: "Unknown Destination",
    description: "No resolved domain on a non-standard port (not 80, 443, or 53).",
  },
};

const PORT_SERVICES = {
  53: "DNS",
  80: "HTTP",
  443: "HTTPS",
  1935: "RTMP",
  3478: "STUN",
  5060: "SIP",
  5228: "Google",
  19302: "Discord",
  27015: "Steam",
};

function portService(port) {
  if (port == null) return "Unknown";
  return PORT_SERVICES[port] || "Unknown";
}

function isPrivateIp(ip) {
  if (!ip || ip === "::1" || ip.startsWith("fe80:") || ip.startsWith("fc") || ip.startsWith("fd")) {
    return true;
  }
  const parts = ip.split(".").map(Number);
  if (parts.length !== 4 || parts.some((n) => Number.isNaN(n))) return true;
  const [a, b] = parts;
  if (a === 10) return true;
  if (a === 127) return true;
  if (a === 169 && b === 254) return true;
  if (a === 172 && b >= 16 && b <= 31) return true;
  if (a === 192 && b === 168) return true;
  return false;
}

let localDeviceIps = null;

function getLocalDeviceIps() {
  if (localDeviceIps) return localDeviceIps;
  const ips = new Set(["127.0.0.1", "::1"]);
  for (const addrs of Object.values(os.networkInterfaces())) {
    if (!addrs) continue;
    for (const addr of addrs) {
      if (!addr.address) continue;
      const ip = addr.address.split("%")[0];
      ips.add(ip);
      if (addr.family === "IPv4") ips.add(ip.toLowerCase());
    }
  }
  localDeviceIps = ips;
  return ips;
}

function isLocalDeviceIpOnServer(ip) {
  if (!ip) return false;
  const normalized = ip.split("%")[0].toLowerCase();
  const ips = getLocalDeviceIps();
  return ips.has(ip) || ips.has(normalized) || [...ips].some(
    (local) => local.toLowerCase() === normalized
  );
}

function isFlaggedAnomaly(record) {
  return record.anomaly && record.anomaly !== "normal";
}

function lookupGeo(ip) {
  const geo = geoip.lookup(ip);
  if (!geo?.ll) return null;
  const lat = geo.ll[0];
  const lon = geo.ll[1];
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  const country = geo.country && geo.country !== "??" ? geo.country : "";
  if (!country) return null;
  return {
    lat,
    lon,
    country,
    region: geo.region || "",
    city: geo.city || "",
  };
}

function buildGeoTraffic(records) {
  const byIp = {};
  let unresolved = 0;

  for (const r of records) {
    const ips = [
      { ip: r.dst_ip, role: "destination" },
      { ip: r.src_ip, role: "source" },
    ];
    for (const { ip, role } of ips) {
      if (isPrivateIp(ip)) continue;
      if (!byIp[ip]) {
        byIp[ip] = {
          ip,
          roles: new Set(),
          sessions: 0,
          bytes_up: 0,
          bytes_down: 0,
          total_bytes: 0,
          apps: new Set(),
          domains: new Set(),
        };
      }
      const entry = byIp[ip];
      entry.roles.add(role);
      entry.sessions += 1;
      entry.bytes_up += r.bytes_up || 0;
      entry.bytes_down += r.bytes_down || 0;
      entry.total_bytes += (r.bytes_up || 0) + (r.bytes_down || 0);
      if (r.app) entry.apps.add(r.app);
      if (r.destination_domain) entry.domains.add(r.destination_domain);
    }
  }

  const points = [];
  const countryMap = {};

  for (const entry of Object.values(byIp)) {
    const geo = lookupGeo(entry.ip);
    if (!geo) {
      unresolved += 1;
      continue;
    }
    const point = {
      ip: entry.ip,
      lat: geo.lat,
      lon: geo.lon,
      country: geo.country,
      region: geo.region,
      city: geo.city,
      roles: [...entry.roles],
      sessions: entry.sessions,
      bytes_up: entry.bytes_up,
      bytes_down: entry.bytes_down,
      total_bytes: entry.total_bytes,
      apps: [...entry.apps].slice(0, 5).join(", "),
      domains: [...entry.domains].slice(0, 3).join(", "),
      label: [geo.city, geo.region, geo.country].filter(Boolean).join(", "),
    };
    points.push(point);

    if (!countryMap[geo.country]) {
      countryMap[geo.country] = {
        country: geo.country,
        sessions: 0,
        total_bytes: 0,
        ip_count: 0,
      };
    }
    countryMap[geo.country].sessions += entry.sessions;
    countryMap[geo.country].total_bytes += entry.total_bytes;
    countryMap[geo.country].ip_count += 1;
  }

  points.sort((a, b) => b.total_bytes - a.total_bytes);
  const countries = Object.values(countryMap).sort(
    (a, b) => b.total_bytes - a.total_bytes
  );

  return {
    points,
    countries,
    unresolved,
    externalIpCount: Object.keys(byIp).length,
    mappedIpCount: points.length,
  };
}

const app = express();

function readBaseline() {
  try {
    const raw = fs.readFileSync(BASELINE_PATH, "utf-8");
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function writeBaseline(baseline) {
  fs.mkdirSync(path.dirname(BASELINE_PATH), { recursive: true });
  fs.writeFileSync(BASELINE_PATH, JSON.stringify(baseline, null, 2));
}

function openDb() {
  try {
    return new Database(DB_PATH, { readonly: true, fileMustExist: true });
  } catch (err) {
    return null;
  }
}

function fetchIpdrRecent(db, windowSec = LIVE_WINDOW_SEC) {
  const since = new Date(Date.now() - windowSec * 1000).toISOString();
  return db
    .prepare(
      `SELECT * FROM ipdr_records WHERE end_time >= ? ORDER BY end_time DESC`
    )
    .all(since);
}

function fetchIpdrByStartWindow(db, windowStartMs, windowEndMs) {
  const since = new Date(windowStartMs).toISOString();
  const until = new Date(windowEndMs).toISOString();
  return db
    .prepare(
      `SELECT * FROM ipdr_records WHERE start_time >= ? AND start_time < ? ORDER BY start_time ASC`
    )
    .all(since, until);
}

function getSnappedLiveWindow(windowSec, bucketSec = SESSION_BUCKET_SEC) {
  const windowEndMs = snapWindowEndMs(Date.now(), bucketSec);
  const windowStartMs = windowEndMs - windowSec * 1000;
  return { windowEndMs, windowStartMs, windowSec, bucketSec };
}

function fetchBandwidthRecent(db, windowSec = LIVE_WINDOW_SEC) {
  const since = Date.now() / 1000 - windowSec;
  return db
    .prepare(
      `SELECT * FROM bandwidth_samples WHERE timestamp >= ? ORDER BY timestamp ASC`
    )
    .all(since);
}

function fetchIpdrInRange(db, startMs, endMs) {
  const since = new Date(startMs).toISOString();
  const until = new Date(endMs).toISOString();
  return db
    .prepare(
      `SELECT * FROM ipdr_records WHERE end_time >= ? AND end_time < ? ORDER BY end_time ASC`
    )
    .all(since, until);
}

function fetchBandwidthInRange(db, startSec, endSec) {
  return db
    .prepare(
      `SELECT * FROM bandwidth_samples WHERE timestamp >= ? AND timestamp < ? ORDER BY timestamp ASC`
    )
    .all(startSec, endSec);
}

function latestBandwidthSample(db) {
  return db
    .prepare(
      `SELECT * FROM bandwidth_samples ORDER BY timestamp DESC LIMIT 1`
    )
    .get();
}

function fetchIpdr(db, limit = 5000) {
  return db
    .prepare(
      `SELECT * FROM ipdr_records ORDER BY end_time DESC LIMIT ?`
    )
    .all(limit);
}

function fetchBandwidth(db, limit = 500) {
  return db
    .prepare(
      `SELECT * FROM bandwidth_samples ORDER BY timestamp ASC LIMIT ?`
    )
    .all(limit);
}

function snapWindowEndMs(windowEndMs, bucketSec) {
  const bucketMs = bucketSec * 1000;
  return Math.floor(windowEndMs / bucketMs) * bucketMs;
}

function buildBandwidthTrail(samples, windowSec, windowEndMs) {
  const endMs = windowEndMs;
  const startSec = endMs / 1000 - windowSec;
  return samples
    .filter((s) => s.timestamp >= startSec && s.timestamp <= endMs / 1000)
    .sort((a, b) => a.timestamp - b.timestamp)
    .map((s) => {
      const offsetSec = s.timestamp - startSec;
      return {
        timestamp: s.timestamp,
        offsetSec,
        label: `-${Math.max(0, Math.round(windowSec - offsetSec))}s`,
        bytes_recv_per_sec: s.bytes_recv_per_sec,
        bytes_sent_per_sec: s.bytes_sent_per_sec,
      };
    });
}

function buildBandwidthCompare(currentSamples, baselineSamples, windowSec) {
  const slotSec = 2;
  const currentEndMs = snapWindowEndMs(Date.now(), slotSec);
  const currentTrail = buildBandwidthTrail(currentSamples, windowSec, currentEndMs);

  const baselineEndMs =
    baselineSamples.length > 0
      ? baselineSamples[baselineSamples.length - 1].timestamp * 1000
      : SERVER_START_MS + windowSec * 1000;
  const baselineTrail = buildBandwidthTrail(baselineSamples, windowSec, baselineEndMs);

  const slots = [];
  for (let offset = 0; offset <= windowSec; offset += slotSec) {
    slots.push(offset);
  }

  const labels = slots.map((offset) => `-${windowSec - offset}s`);

  function pickAt(trail, offsetSec, field) {
    const match = trail.find((p) => Math.abs(p.offsetSec - offsetSec) <= slotSec / 2);
    return match ? match[field] : null;
  }

  return {
    labels,
    windowSec,
    current: {
      down: slots.map((o) => pickAt(currentTrail, o, "bytes_recv_per_sec")),
      up: slots.map((o) => pickAt(currentTrail, o, "bytes_sent_per_sec")),
    },
    baseline: {
      down: slots.map((o) => pickAt(baselineTrail, o, "bytes_recv_per_sec")),
      up: slots.map((o) => pickAt(baselineTrail, o, "bytes_sent_per_sec")),
    },
  };
}

function buildSessionTimeline(records, options = {}) {
  const opts = typeof options === "boolean" ? { live: options } : options;
  const {
    live = false,
    windowSec = SESSION_WINDOW_SEC,
    bucketSec = SESSION_BUCKET_SEC,
    windowEndMs: fixedEnd = null,
    windowStartMs: fixedStart = null,
    labelMode = "trailing",
  } = opts;

  const bucketMs = bucketSec * 1000;
  const windowMs = windowSec * 1000;
  const bucketCount = Math.floor(windowSec / bucketSec);

  let windowEndMs = fixedEnd ?? Date.now();
  if (live && !fixedEnd) {
    windowEndMs = snapWindowEndMs(windowEndMs, bucketSec);
  } else if (!fixedEnd && !live) {
    for (const r of records) {
      try {
        const t = new Date(r.end_time || r.start_time).getTime();
        if (Number.isFinite(t) && t > windowEndMs) windowEndMs = t;
      } catch (_) {
        /* skip bad timestamps */
      }
    }
  }

  const windowStartMs = fixedStart ?? windowEndMs - windowMs;
  const counts = Array(bucketCount).fill(0);

  for (const r of records) {
    try {
      const startMs = new Date(r.start_time).getTime();
      if (!Number.isFinite(startMs)) continue;
      if (startMs < windowStartMs || startMs >= windowEndMs) continue;
      const idx = Math.floor((startMs - windowStartMs) / bucketMs);
      if (idx >= 0 && idx < bucketCount) counts[idx] += 1;
    } catch (_) {
      /* skip bad timestamps */
    }
  }

  const buckets = counts.map((count, idx) => {
    if (labelMode === "fromStart") {
      const from = idx * bucketSec;
      const to = (idx + 1) * bucketSec;
      return { label: `${from}-${to}s`, count, offsetSec: from };
    }
    const offsetSec = idx * bucketSec - windowSec;
    const abs = Math.abs(offsetSec);
    const m = Math.floor(abs / 60);
    const s = abs % 60;
    const label = `-${m}:${String(s).padStart(2, "0")}`;
    return { label, count, offsetSec };
  });

  return {
    buckets,
    bucketSec,
    windowSec,
    windowEnd: new Date(windowEndMs).toISOString(),
  };
}

function buildAnomalyDetails(db, dataLive) {
  const limit = 500;
  let records;
  let windowSec = null;
  let windowEnd = null;

  if (dataLive) {
    const win = getSnappedLiveWindow(LIVE_WINDOW_SEC);
    records = fetchIpdrByStartWindow(db, win.windowStartMs, win.windowEndMs);
    windowSec = win.windowSec;
    windowEnd = new Date(win.windowEndMs).toISOString();
  } else {
    records = fetchIpdr(db, 5000);
  }

  const anomalies = records
    .filter((r) => isFlaggedAnomaly(r))
    .sort((a, b) => new Date(b.end_time) - new Date(a.end_time))
    .slice(0, limit);

  const typeCounts = {};
  for (const r of anomalies) {
    typeCounts[r.anomaly] = (typeCounts[r.anomaly] || 0) + 1;
  }

  const types = Object.entries(typeCounts)
    .sort((a, b) => b[1] - a[1])
    .map(([type, count]) => ({
      type,
      count,
      label: ANOMALY_META[type]?.label || type,
      description: ANOMALY_META[type]?.description || "",
    }));

  const timeline = buildSessionTimeline(anomalies, { live: false });

  return {
    windowSec,
    windowEnd,
    total: anomalies.length,
    types,
    timeline,
    records: anomalies,
    localIps: [...getLocalDeviceIps()],
  };
}

function buildSummary(records, bandwidth, latestBw = null, dataLive = false, sessionTimelineOpts = null) {
  const totalUp = records.reduce((s, r) => s + (r.bytes_up || 0), 0);
  const totalDown = records.reduce((s, r) => s + (r.bytes_down || 0), 0);
  const total = totalUp + totalDown || 1;
  const anomalies = records.filter((r) => isFlaggedAnomaly(r));

  const appCounts = {};
  const serviceCounts = {};
  const domainBytes = {};

  for (const r of records) {
    appCounts[r.app || "Unknown"] = (appCounts[r.app || "Unknown"] || 0) + 1;
    serviceCounts[r.service_type || "unknown"] =
      (serviceCounts[r.service_type || "unknown"] || 0) + 1;
    const domain = r.destination_domain || r.dst_ip || "unknown";
    domainBytes[domain] =
      (domainBytes[domain] || 0) + (r.bytes_up || 0) + (r.bytes_down || 0);
  }

  const topApps = Object.entries(appCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([name, count]) => ({ name, count }));

  const topDomains = Object.entries(domainBytes)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([name, bytes]) => ({ name, bytes }));

  const serviceMix = Object.entries(serviceCounts)
    .sort((a, b) => b[1] - a[1])
    .map(([name, count]) => ({ name, count }));

  const sessionTimeline = sessionTimelineOpts
    ? buildSessionTimeline(records, sessionTimelineOpts)
    : buildSessionTimeline(records, { live: dataLive });

  return {
    live: LIVE_MODE,
    windowSec: LIVE_MODE ? LIVE_WINDOW_SEC : null,
    totalSessions: records.length,
    totalBytesUp: totalUp,
    totalBytesDown: totalDown,
    uploadPct: Math.round((100 * totalUp) / total),
    downloadPct: Math.round((100 * totalDown) / total),
    anomalyCount: anomalies.length,
    bandwidthSamples: bandwidth.length,
    currentUploadBps: latestBw?.bytes_sent_per_sec ?? null,
    currentDownloadBps: latestBw?.bytes_recv_per_sec ?? null,
    topApps,
    topDomains,
    serviceMix,
    sessionTimeline,
  };
}

function isCollectorActive(db) {
  const latest = latestBandwidthSample(db);
  if (!latest) return false;
  return Date.now() / 1000 - latest.timestamp <= LIVE_STALE_SEC;
}

function useLiveWindow(db) {
  return LIVE_MODE || isCollectorActive(db);
}

function getLiveStatus(db) {
  if (!db) {
    return {
      live: LIVE_MODE,
      dbExists: false,
      collectorActive: false,
      dataLive: false,
      autoBaseline: getAutoBaselineStatus(),
    };
  }
  const latest = latestBandwidthSample(db);
  const ageSec = latest ? Date.now() / 1000 - latest.timestamp : null;
  const collectorActive = ageSec !== null && ageSec <= LIVE_STALE_SEC;
  return {
    live: LIVE_MODE,
    dbExists: true,
    collectorActive,
    dataLive: LIVE_MODE || collectorActive,
    lastSampleAgeSec: ageSec !== null ? Math.round(ageSec * 10) / 10 : null,
    serverTime: Date.now(),
    autoBaseline: getAutoBaselineStatus(),
  };
}

let autoBaselineState = {
  enabled: LIVE_MODE,
  recording: false,
  ready: false,
};

function getAutoBaselineStatus() {
  const existing = readBaseline();
  if (!autoBaselineState.enabled) {
    return {
      enabled: false,
      recording: false,
      ready: Boolean(existing),
      secondsRemaining: 0,
      windowSec: existing?.windowSec || AUTO_BASELINE_SEC,
    };
  }
  const elapsed = (Date.now() - SERVER_START_MS) / 1000;
  const remaining = Math.max(0, AUTO_BASELINE_SEC - elapsed);
  const recording = autoBaselineState.recording && remaining > 0;
  return {
    enabled: true,
    recording,
    ready: autoBaselineState.ready || Boolean(existing),
    secondsRemaining: recording ? Math.ceil(remaining) : 0,
    windowSec: existing?.windowSec || AUTO_BASELINE_SEC,
  };
}

function buildBaselineSnapshot(records, bandwidth, latestBw, windowSec, sessionTimeline) {
  const summary = buildSummary(records, bandwidth, latestBw, true);
  summary.sessionTimeline = sessionTimeline;
  return {
    createdAt: new Date().toISOString(),
    windowSec,
    summary,
    bandwidth,
    sessionTimeline,
  };
}

function captureAutoBaseline() {
  const db = openDb();
  if (!db) {
    autoBaselineState.recording = false;
    return false;
  }

  const endMs = SERVER_START_MS + AUTO_BASELINE_SEC * 1000;
  const records = fetchIpdrInRange(db, SERVER_START_MS, endMs);
  const bandwidth = fetchBandwidthInRange(db, SERVER_START_MS / 1000, endMs / 1000);
  const latestBw = latestBandwidthSample(db);
  const sessionTimeline = buildSessionTimeline(records, {
    windowSec: AUTO_BASELINE_SEC,
    bucketSec: BASELINE_BUCKET_SEC,
    windowEndMs: endMs,
    windowStartMs: SERVER_START_MS,
    labelMode: "trailing",
  });
  db.close();

  const baseline = buildBaselineSnapshot(
    records,
    bandwidth,
    latestBw,
    AUTO_BASELINE_SEC,
    sessionTimeline
  );
  baseline.autoRecorded = true;
  writeBaseline(baseline);
  autoBaselineState.recording = false;
  autoBaselineState.ready = true;
  console.log(`  Auto baseline recorded (${AUTO_BASELINE_SEC}s startup window)`);
  return true;
}

function startAutoBaseline() {
  if (!LIVE_MODE) return;
  const existing = readBaseline();
  if (existing) {
    autoBaselineState = { enabled: true, recording: false, ready: true };
    const when = existing.createdAt ? new Date(existing.createdAt).toLocaleString() : "saved file";
    console.log(`  Baseline: using recorded snapshot (${when})`);
    return;
  }
  autoBaselineState = { enabled: true, recording: true, ready: false };
  console.log(`  No baseline snapshot found — recording ${AUTO_BASELINE_SEC}s startup window`);
  setTimeout(captureAutoBaseline, AUTO_BASELINE_SEC * 1000);
}

function buildCurrentCompareSnapshot(db, windowSec = AUTO_BASELINE_SEC) {
  const { windowEndMs, windowStartMs, bucketSec } = getSnappedLiveWindow(
    windowSec,
    BASELINE_BUCKET_SEC
  );
  const records = fetchIpdrByStartWindow(db, windowStartMs, windowEndMs);
  const bandwidth = fetchBandwidthRecent(db, windowSec);
  const latestBw = latestBandwidthSample(db);
  const sessionTimelineOpts = {
    windowSec,
    bucketSec,
    windowEndMs,
    windowStartMs,
  };
  const sessionTimeline = buildSessionTimeline(records, sessionTimelineOpts);
  const summary = buildSummary(records, bandwidth, latestBw, true, sessionTimelineOpts);
  summary.sessionTimeline = sessionTimeline;
  return { summary, bandwidth, sessionTimeline };
}

app.get("/api/health", (_req, res) => {
  const db = openDb();
  res.json({
    ok: true,
    dbPath: DB_PATH,
    dbExists: Boolean(db),
    liveMode: LIVE_MODE,
  });
  db?.close();
});

app.get("/api/baseline", (_req, res) => {
  res.json({
    baseline: readBaseline(),
    autoBaseline: getAutoBaselineStatus(),
  });
});

app.get("/api/baseline/presets", (_req, res) => {
  ensurePresetBaselines(undefined, AUTO_BASELINE_SEC, BASELINE_BUCKET_SEC);
  res.json({
    presets: PRESET_BASELINES.map(({ id, label }) => ({ id, label })),
  });
});

app.get("/api/baseline/compare", (req, res) => {
  const presetId = typeof req.query.preset === "string" ? req.query.preset : "";
  const autoBaseline = getAutoBaselineStatus();
  let baseline = null;

  if (presetId) {
    baseline = readPresetBaseline(presetId);
    if (!baseline) {
      return res.status(404).json({ error: "Preset baseline not found", presetId });
    }
  } else {
    baseline = readBaseline();
    if (!baseline || autoBaseline.recording) {
      return res.json({ baseline, autoBaseline, current: null, presetId: null });
    }
  }

  const db = openDb();
  if (!db) {
    return res.json({ baseline, autoBaseline, current: null, presetId: presetId || null });
  }
  const compareWindowSec = baseline.windowSec || AUTO_BASELINE_SEC;
  const current = buildCurrentCompareSnapshot(db, compareWindowSec);
  const bandwidthCompare = buildBandwidthCompare(
    fetchBandwidthRecent(db, compareWindowSec),
    baseline.bandwidth || [],
    compareWindowSec
  );
  db.close();
  res.json({
    baseline,
    autoBaseline,
    current,
    bandwidthCompare,
    presetId: presetId || null,
    presetLabel: baseline.presetLabel || null,
  });
});

app.post("/api/baseline", (_req, res) => {
  const db = openDb();
  if (!db) {
    return res.status(404).json({
      error: "Database not found. Start the collector first.",
    });
  }

  const windowSec = LIVE_MODE ? AUTO_BASELINE_SEC : LIVE_WINDOW_SEC;
  const records = fetchIpdrRecent(db, windowSec);
  const bandwidth = fetchBandwidthRecent(db, windowSec);
  const latestBw = latestBandwidthSample(db);
  const sessionTimeline = buildSessionTimeline(records, {
    live: true,
    windowSec,
    bucketSec: LIVE_MODE ? BASELINE_BUCKET_SEC : SESSION_BUCKET_SEC,
    windowEndMs: snapWindowEndMs(Date.now(), LIVE_MODE ? BASELINE_BUCKET_SEC : SESSION_BUCKET_SEC),
  });
  const status = getLiveStatus(db);
  db.close();

  const baseline = buildBaselineSnapshot(
    records,
    bandwidth,
    latestBw,
    windowSec,
    sessionTimeline
  );
  autoBaselineState.recording = false;
  autoBaselineState.ready = true;

  writeBaseline(baseline);
  res.json({ ok: true, baseline, autoBaseline: getAutoBaselineStatus(), ...status });
});

app.get("/api/status", (_req, res) => {
  const db = openDb();
  const status = getLiveStatus(db);
  db?.close();
  res.json(status);
});

app.get("/api/summary", (_req, res) => {
  const db = openDb();
  if (!db) {
    return res.status(404).json({
      error: LIVE_MODE
        ? "Database not found. Waiting for collector..."
        : "Database not found. Run: python run_monitor.py collect --duration 60",
    });
  }
  const dataLive = useLiveWindow(db);
  let records;
  let sessionTimelineOpts = null;
  if (dataLive) {
    const liveWin = getSnappedLiveWindow(LIVE_WINDOW_SEC);
    records = fetchIpdrByStartWindow(db, liveWin.windowStartMs, liveWin.windowEndMs);
    const sessionWin = getSnappedLiveWindow(SESSION_WINDOW_SEC);
    sessionTimelineOpts = {
      windowSec: sessionWin.windowSec,
      bucketSec: sessionWin.bucketSec,
      windowEndMs: sessionWin.windowEndMs,
      windowStartMs: sessionWin.windowStartMs,
    };
  } else {
    records = fetchIpdr(db);
  }
  const bandwidth = dataLive ? fetchBandwidthRecent(db) : fetchBandwidth(db);
  const latestBw = latestBandwidthSample(db);
  const status = getLiveStatus(db);
  const summary = buildSummary(records, bandwidth, latestBw, dataLive, sessionTimelineOpts);
  db.close();
  res.json({ ...summary, dataLive, ...status });
});

app.get("/api/ipdr", (req, res) => {
  const db = openDb();
  if (!db) return res.status(404).json({ error: "Database not found" });
  const limit = Math.min(Number(req.query.limit) || 100, 5000);
  const rows = fetchIpdr(db, limit);
  db.close();
  res.json(rows);
});

app.get("/api/anomalies", (_req, res) => {
  const db = openDb();
  if (!db) return res.status(404).json({ error: "Database not found" });
  const rows = db
    .prepare(
      `SELECT * FROM ipdr_records WHERE anomaly != 'normal' ORDER BY end_time DESC LIMIT 200`
    )
    .all();
  db.close();
  res.json(rows);
});

app.get("/api/local-ips", (_req, res) => {
  res.json([...getLocalDeviceIps()].sort());
});

app.get("/api/anomalies/details", (_req, res) => {
  const db = openDb();
  if (!db) return res.status(404).json({ error: "Database not found" });
  const dataLive = useLiveWindow(db);
  const details = buildAnomalyDetails(db, dataLive);
  db.close();
  res.json({ dataLive, ...details });
});

app.get("/api/bandwidth", (req, res) => {
  const db = openDb();
  if (!db) return res.status(404).json({ error: "Database not found" });
  const windowSec = Number(req.query.window) || 0;
  let rows;
  if (windowSec > 0 || useLiveWindow(db)) {
    rows = fetchBandwidthRecent(db, windowSec > 0 ? windowSec : LIVE_WINDOW_SEC);
  } else {
    const limit = Math.min(Number(req.query.limit) || 200, 2000);
    rows = fetchBandwidth(db, limit);
  }
  db.close();
  res.json(rows);
});

app.get("/api/ports", (req, res) => {
  const db = openDb();
  if (!db) return res.status(404).json({ error: "Database not found" });
  const limit = Math.min(Number(req.query.limit) || 100, 500);
  const rows = db
    .prepare(
      `SELECT
         dst_port AS port,
         COUNT(*) AS sessions,
         SUM(bytes_up) AS bytes_up,
         SUM(bytes_down) AS bytes_down,
         SUM(bytes_up + bytes_down) AS total_bytes,
         GROUP_CONCAT(DISTINCT protocol) AS protocols,
         GROUP_CONCAT(DISTINCT app) AS apps
       FROM ipdr_records
       WHERE dst_port IS NOT NULL
       GROUP BY dst_port
       ORDER BY total_bytes DESC
       LIMIT ?`
    )
    .all(limit)
    .map((row) => ({
      ...row,
      service: portService(row.port),
    }));
  db.close();
  res.json(rows);
});

app.get("/api/ports/sessions", (req, res) => {
  const db = openDb();
  if (!db) return res.status(404).json({ error: "Database not found" });
  const port = Number(req.query.port);
  const limit = Math.min(Number(req.query.limit) || 100, 500);
  let rows;
  if (Number.isFinite(port) && port > 0) {
    rows = db
      .prepare(
        `SELECT * FROM ipdr_records
         WHERE dst_port = ?
         ORDER BY end_time DESC
         LIMIT ?`
      )
      .all(port, limit);
  } else {
    rows = db
      .prepare(
        `SELECT * FROM ipdr_records
         WHERE dst_port IS NOT NULL
         ORDER BY dst_port ASC, end_time DESC
         LIMIT ?`
      )
      .all(limit);
  }
  db.close();
  res.json(rows);
});

app.get("/api/geo", (req, res) => {
  const db = openDb();
  if (!db) return res.status(404).json({ error: "Database not found" });
  const records = useLiveWindow(db)
    ? fetchIpdrRecent(db)
    : fetchIpdr(db, Math.min(Number(req.query.limit) || 5000, 10000));
  db.close();
  res.json(buildGeoTraffic(records));
});

app.use(express.static(path.join(__dirname, "public")));

const server = app.listen(PORT, () => {
  ensurePresetBaselines(undefined, AUTO_BASELINE_SEC, BASELINE_BUCKET_SEC);
  console.log("=".repeat(50));
  console.log(`  Network Monitor Dashboard (Node.js)${LIVE_MODE ? " — LIVE" : ""}`);
  console.log("=".repeat(50));
  console.log(`  Open: http://localhost:${PORT}`);
  console.log(`  DB:   ${DB_PATH}`);
  if (LIVE_MODE) {
    console.log(`  Window: trailing ${LIVE_WINDOW_SEC}s · poll every 2s`);
    console.log(`  Auto baseline: use saved snapshot, or record ${AUTO_BASELINE_SEC}s if none`);
    startAutoBaseline();
  }
  console.log("");
});

server.on("error", (err) => {
  if (err.code === "EADDRINUSE") {
    console.error(`\n  Port ${PORT} is already in use.`);
    console.error("  Stop the existing dashboard (Ctrl+C in its terminal), then run npm start again.");
    console.error(`  Or find the process: netstat -ano | findstr :${PORT}\n`);
  }
  process.exit(1);
});
