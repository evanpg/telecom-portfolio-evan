const charts = {};
let trafficMap = null;
let mapMarkers = [];
let pollTimer = null;
let isLiveActive = false;
let baseline = null;
let lastBaselineCompare = null;
let autoBaselineStatus = null;
let baselinePresets = [];
let selectedBaselinePreset = "current";
let anomalyFilter = "all";
let anomalyRoleFilter = "all";
let localDeviceIps = new Set();
let lastAnomalyDetails = null;

const ANOMALY_COLORS = {
  upload_spike: "#ef4444",
  bot_connections: "#f59e0b",
  micro_flow: "#a855f7",
  unknown_destination: "#6366f1",
};

const ANOMALY_META = {
  upload_spike: { label: "Upload Spike" },
  bot_connections: { label: "Bot Connections" },
  micro_flow: { label: "Micro Flow" },
  unknown_destination: { label: "Unknown Destination" },
};

const baselineBwVisible = {
  currentDown: true,
  baselineDown: true,
  currentUp: true,
  baselineUp: true,
};

const POLL_LIVE_MS = 2000;
const POLL_IDLE_MS = 30000;
const SESSION_WINDOW_SEC = 60;
const SESSION_BUCKET_SEC = 5;

const COUNTRY_NAMES = {
  US: "United States",
  GB: "United Kingdom",
  DE: "Germany",
  FR: "France",
  NL: "Netherlands",
  CA: "Canada",
  AU: "Australia",
  JP: "Japan",
  IN: "India",
  BR: "Brazil",
  SG: "Singapore",
  IE: "Ireland",
  SE: "Sweden",
  CH: "Switzerland",
  ES: "Spain",
  IT: "Italy",
  MX: "Mexico",
  AR: "Argentina",
  CL: "Chile",
  CN: "China",
  KR: "South Korea",
  HK: "Hong Kong",
  TW: "Taiwan",
  PL: "Poland",
  FI: "Finland",
  NO: "Norway",
  DK: "Denmark",
  BE: "Belgium",
  AT: "Austria",
  PT: "Portugal",
  RU: "Russia",
  UA: "Ukraine",
  ZA: "South Africa",
  AE: "UAE",
  IL: "Israel",
  NZ: "New Zealand",
};

function countryLabel(code) {
  return COUNTRY_NAMES[code] || code || "Unknown";
}

function fmtBytes(n) {
  if (n >= 1e9) return (n / 1e9).toFixed(2) + " GB";
  if (n >= 1e6) return (n / 1e6).toFixed(2) + " MB";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + " KB";
  return n + " B";
}

function fmtTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function fmtClock(unixSec) {
  return new Date(unixSec * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function fmtDuration(sec) {
  if (sec == null) return "—";
  if (sec < 60) return `${sec}s`;
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return s ? `${m}m ${s}s` : `${m}m`;
}

function fmtRate(n) {
  if (n == null) return "—";
  return fmtBytes(n) + "/s";
}

function anomalyLabel(type) {
  return type.replace(/_/g, " ");
}

function anomalyTag(type) {
  return `<span class="tag anomaly ${type}">${anomalyLabel(type)}</span>`;
}

function showAlert(msg) {
  const el = document.getElementById("alert");
  el.textContent = msg;
  el.classList.remove("hidden");
}

function hideAlert() {
  document.getElementById("alert").classList.add("hidden");
}

async function fetchJson(url) {
  const res = await fetch(url);
  const type = res.headers.get("content-type") || "";
  if (!type.includes("application/json")) {
    throw new Error(
      `${url} returned non-JSON (${res.status}). Restart the dashboard server (npm start).`
    );
  }
  return res.json();
}

function buildAnomalyDetailsFallback(records, dataLive = false, localIps = []) {
  const typeCounts = {};
  for (const r of records) {
    typeCounts[r.anomaly] = (typeCounts[r.anomaly] || 0) + 1;
  }
  const types = Object.entries(typeCounts)
    .sort((a, b) => b[1] - a[1])
    .map(([type, count]) => ({
      type,
      count,
      label: anomalyLabel(type),
      description: "",
    }));
  return {
    dataLive,
    total: records.length,
    types,
    timeline: { buckets: [] },
    records,
    localIps,
  };
}

function normalizeIp(ip) {
  if (!ip) return "";
  return String(ip).split("%")[0].toLowerCase();
}

function setLocalDeviceIps(ips) {
  localDeviceIps = new Set((ips || []).map(normalizeIp));
}

function isLocalDeviceIp(ip) {
  const normalized = normalizeIp(ip);
  return localDeviceIps.has(normalized);
}

function ipCell(ip) {
  const cls = isLocalDeviceIp(ip) ? ' class="local-ip"' : "";
  return `<td${cls}>${ip}</td>`;
}

function matchesAnomalyRole(record) {
  if (anomalyRoleFilter === "local_src") return isLocalDeviceIp(record.src_ip);
  if (anomalyRoleFilter === "local_dst") return isLocalDeviceIp(record.dst_ip);
  return true;
}

function filterAnomalyRecords(records) {
  return records.filter((r) => {
    if (!matchesAnomalyRole(r)) return false;
    if (anomalyFilter !== "all" && r.anomaly !== anomalyFilter) return false;
    return true;
  });
}

function buildAnomalyTypeCounts(records) {
  const typeCounts = {};
  for (const r of records) {
    typeCounts[r.anomaly] = (typeCounts[r.anomaly] || 0) + 1;
  }
  return Object.entries(typeCounts)
    .sort((a, b) => b[1] - a[1])
    .map(([type, count]) => ({
      type,
      count,
      label: ANOMALY_META[type]?.label || anomalyLabel(type),
      description: "",
    }));
}

async function fetchAnomalyDetails(dataLive = false) {
  let localIps = [];
  try {
    localIps = await fetchJson("/api/local-ips");
  } catch {
    localIps = [];
  }
  setLocalDeviceIps(localIps);

  try {
    const details = await fetchJson("/api/anomalies/details");
    if (!details.localIps?.length) details.localIps = localIps;
    setLocalDeviceIps(details.localIps);
    return details;
  } catch {
    const records = await fetchJson("/api/anomalies");
    return buildAnomalyDetailsFallback(records, dataLive, localIps);
  }
}

function upsertChart(id, type, labels, datasets, options = {}) {
  const ctx = document.getElementById(id);
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(ctx, {
    type,
    data: { labels, datasets },
    options: {
      responsive: true,
      animation: false,
      plugins: { legend: { labels: { color: "#8b9cb3" } } },
      scales: type === "doughnut" || type === "pie" ? {} : {
        x: { ticks: { color: "#8b9cb3", maxRotation: 45, autoSkip: true, maxTicksLimit: 12 }, grid: { color: "#2d3a4f" } },
        y: { ticks: { color: "#8b9cb3" }, grid: { color: "#2d3a4f" } },
      },
      ...options,
    },
  });
}

function updateOrCreateChart(id, type, labels, datasets, options = {}) {
  if (charts[id]) {
    charts[id].data.labels = labels;
    charts[id].data.datasets = datasets;
    charts[id].update("none");
    return;
  }
  upsertChart(id, type, labels, datasets, options);
}

function buildSessionChartLabels(windowSec = SESSION_WINDOW_SEC, bucketSec = SESSION_BUCKET_SEC) {
  const bucketCount = Math.floor(windowSec / bucketSec);
  return Array.from({ length: bucketCount }, (_, idx) => {
    const offsetSec = idx * bucketSec - windowSec;
    const abs = Math.abs(offsetSec);
    const m = Math.floor(abs / 60);
    const s = abs % 60;
    return `-${m}:${String(s).padStart(2, "0")}`;
  });
}

function alignSessionCounts(timeline, windowSec = SESSION_WINDOW_SEC, bucketSec = SESSION_BUCKET_SEC) {
  const labels = buildSessionChartLabels(windowSec, bucketSec);
  const byIdx = new Map((timeline?.buckets || []).map((b, idx) => [idx, b.count]));
  return labels.map((_, idx) => byIdx.get(idx) ?? 0);
}

const SESSION_CHART_OPTS = {
  scales: {
    x: {
      ticks: { color: "#8b9cb3", maxRotation: 0, autoSkip: true, maxTicksLimit: 12 },
      grid: { color: "#2d3a4f" },
    },
    y: {
      ticks: { color: "#8b9cb3", precision: 0 },
      grid: { color: "#2d3a4f" },
      beginAtZero: true,
    },
  },
};

function renderSessionTimelineChart(id, timeline, color = "#6366f1") {
  const windowSec = timeline?.windowSec ?? SESSION_WINDOW_SEC;
  const bucketSec = timeline?.bucketSec ?? SESSION_BUCKET_SEC;
  const labels = buildSessionChartLabels(windowSec, bucketSec);
  const counts = alignSessionCounts(timeline, windowSec, bucketSec);
  updateOrCreateChart(
    id,
    "bar",
    labels,
    [{ label: "Sessions", data: counts, backgroundColor: color }],
    SESSION_CHART_OPTS
  );
}

function updateLiveBadge(status) {
  const badge = document.getElementById("liveBadge");
  const subtitle = document.getElementById("subtitle");
  const footer = document.getElementById("footerText");
  const active = Boolean(status.collectorActive);
  const dataLive = Boolean(status.dataLive);

  isLiveActive = dataLive || status.live;
  badge.classList.toggle("hidden", !status.live && !active);
  badge.classList.toggle("stale", status.live && !active);
  badge.title = active
    ? "Collector active — updating every 2s"
    : status.live
      ? "Waiting for collector samples..."
      : "Live mode";

  if (dataLive) {
    subtitle.textContent = "Live monitor · trailing 5 minute window";
    footer.textContent = active
      ? `Live · last sample ${status.lastSampleAgeSec ?? "?"}s ago · refresh 2s`
      : "Live · waiting for fresh samples...";
    document.getElementById("lblSessions").textContent = "Sessions (5m)";
    document.getElementById("lblDown").textContent = "Download rate";
    document.getElementById("lblUp").textContent = "Upload rate";
  } else if (status.live && status.autoBaseline?.recording) {
    subtitle.textContent = "Live monitor · recording baseline snapshot...";
    footer.textContent = "Live mode · waiting for collector...";
    document.getElementById("lblSessions").textContent = "Sessions (5m)";
    document.getElementById("lblDown").textContent = "Download rate";
    document.getElementById("lblUp").textContent = "Upload rate";
  } else if (status.live) {
    subtitle.textContent = "Live monitor · comparing to recorded baseline";
    footer.textContent = "Live mode · waiting for collector...";
    document.getElementById("lblSessions").textContent = "Sessions (5m)";
    document.getElementById("lblDown").textContent = "Download rate";
    document.getElementById("lblUp").textContent = "Upload rate";
  } else {
    subtitle.textContent = "IPDR-style traffic analytics from local capture";
    footer.textContent = "Data from network_monitor.db · refresh 30s";
    document.getElementById("lblSessions").textContent = "Sessions";
    document.getElementById("lblDown").textContent = "Download";
    document.getElementById("lblUp").textContent = "Upload";
  }

  schedulePoll(isLiveActive ? POLL_LIVE_MS : POLL_IDLE_MS);
}

function schedulePoll(ms) {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(loadDashboard, ms);
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((btn) => {
    const active = btn.dataset.tab === name;
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", active ? "true" : "false");
  });
  document.getElementById("tab-overview").classList.toggle("hidden", name !== "overview");
  document.getElementById("tab-ports").classList.toggle("hidden", name !== "ports");
  document.getElementById("tab-map").classList.toggle("hidden", name !== "map");
  document.getElementById("tab-anomalies").classList.toggle("hidden", name !== "anomalies");
  document.getElementById("tab-baseline").classList.toggle("hidden", name !== "baseline");
  if (name === "map" && trafficMap) {
    setTimeout(() => trafficMap.invalidateSize(), 150);
  }
}

function setBaselineMeta() {
  const el = document.getElementById("baselineMeta");
  if (!el) return;
  if (autoBaselineStatus?.recording) {
    el.textContent = `Recording startup baseline (${autoBaselineStatus.secondsRemaining}s remaining)...`;
    return;
  }
  if (selectedBaselinePreset !== "current") {
    const preset =
      baselinePresets.find((entry) => entry.id === selectedBaselinePreset) ||
      (baseline?.presetLabel ? { label: baseline.presetLabel } : null);
    const label = preset?.label || selectedBaselinePreset;
    const windowSec = baseline?.windowSec ?? 180;
    el.textContent = `Comparing to prerecorded baseline: ${label} · window: ${windowSec}s`;
    return;
  }
  if (!baseline) {
    el.textContent = "Waiting for baseline data...";
    return;
  }
  const createdAt = baseline.createdAt ? new Date(baseline.createdAt).toLocaleString() : "—";
  const windowSec = baseline.windowSec ?? 180;
  const source = baseline.autoRecorded ? "auto-recorded" : "recorded snapshot";
  el.textContent = `Baseline (${source}): ${createdAt} · window: ${windowSec}s`;
}

function updateBaselineUI() {
  const btn = document.getElementById("recordBaselineBtn");
  const charts = document.getElementById("baselineCharts");
  const recording = Boolean(autoBaselineStatus?.recording);

  if (btn) {
    btn.classList.toggle("recording", recording);
    btn.disabled = recording;
    btn.textContent = recording
      ? `Recording... ${autoBaselineStatus.secondsRemaining}s`
      : "Record baseline";
  }

  charts?.classList.toggle("hidden", recording);
  setBaselineMeta();
}

function buildBaselineBandwidthDatasets(compare) {
  return [
    {
      key: "currentDown",
      label: "Current Down",
      data: compare.current.down,
      borderColor: "#3b82f6",
      tension: 0.25,
      hidden: !baselineBwVisible.currentDown,
    },
    {
      key: "baselineDown",
      label: "Baseline Down",
      data: compare.baseline.down,
      borderColor: "#93c5fd",
      borderDash: [6, 4],
      tension: 0.25,
      hidden: !baselineBwVisible.baselineDown,
    },
    {
      key: "currentUp",
      label: "Current Up",
      data: compare.current.up,
      borderColor: "#22c55e",
      tension: 0.25,
      hidden: !baselineBwVisible.currentUp,
    },
    {
      key: "baselineUp",
      label: "Baseline Up",
      data: compare.baseline.up,
      borderColor: "#86efac",
      borderDash: [6, 4],
      tension: 0.25,
      hidden: !baselineBwVisible.baselineUp,
    },
  ];
}

function syncBaselineBwCheckboxes() {
  document.querySelectorAll("#baselineBwToggles input[data-series]").forEach((input) => {
    const key = input.dataset.series;
    input.checked = baselineBwVisible[key] !== false;
  });
}

function applyBaselineBwVisibility() {
  const chart = charts.baselineBandwidthChart;
  if (!chart) return;
  chart.data.datasets.forEach((ds, idx) => {
    if (ds.key) chart.setDatasetVisibility(idx, baselineBwVisible[ds.key] !== false);
  });
  chart.update("none");
}

function renderBaselineCompare(current, bandwidthCompare) {
  if (!baseline || !bandwidthCompare) return;

  lastBaselineCompare = { current, bandwidthCompare };

  const curSess = current.sessionTimeline || {};
  const baseSess = baseline.sessionTimeline || {};
  const windowSec = curSess.windowSec ?? baseSess.windowSec ?? 180;
  const bucketSec = curSess.bucketSec ?? baseSess.bucketSec ?? 5;
  const sessionLabels = buildSessionChartLabels(windowSec, bucketSec);
  const curCounts = alignSessionCounts(curSess, windowSec, bucketSec);
  const baseCounts = alignSessionCounts(baseSess, windowSec, bucketSec);
  const baselineLabel =
    selectedBaselinePreset !== "current"
      ? baselinePresets.find((entry) => entry.id === selectedBaselinePreset)?.label ||
        baseline?.presetLabel ||
        "Baseline"
      : "Baseline";

  updateOrCreateChart(
    "baselineSessionsChart",
    "bar",
    sessionLabels,
    [
      {
        label: "Current",
        data: curCounts,
        backgroundColor: "rgba(99, 102, 241, 0.85)",
      },
      {
        label: baselineLabel,
        data: baseCounts,
        backgroundColor: "rgba(148, 163, 184, 0.55)",
      },
    ],
    {
      plugins: { legend: { position: "top" } },
      scales: {
        x: { ticks: { color: "#8b9cb3", maxRotation: 45, autoSkip: true, maxTicksLimit: 18 }, grid: { color: "#2d3a4f" } },
        y: { ticks: { color: "#8b9cb3", precision: 0 }, grid: { color: "#2d3a4f" }, beginAtZero: true },
      },
    }
  );

  updateOrCreateChart(
    "baselineBandwidthChart",
    "line",
    bandwidthCompare.labels,
    buildBaselineBandwidthDatasets(bandwidthCompare),
    {
      plugins: { legend: { position: "top" } },
      scales: {
        x: { ticks: { color: "#8b9cb3", maxRotation: 45, autoSkip: true, maxTicksLimit: 18 }, grid: { color: "#2d3a4f" } },
        y: { ticks: { color: "#8b9cb3" }, grid: { color: "#2d3a4f" } },
      },
    }
  );
  syncBaselineBwCheckboxes();
}

async function loadBaselinePresets() {
  let res = { presets: [] };
  try {
    res = await fetchJson("/api/baseline/presets");
  } catch {
    res = { presets: [] };
  }
  baselinePresets = res.presets || [];
  const select = document.getElementById("baselinePresetSelect");
  if (!select) return;

  const options = [
    `<option value="current">Current snapshot</option>`,
    ...baselinePresets.map(
      (preset) => `<option value="${preset.id}">${preset.label}</option>`
    ),
  ];
  select.innerHTML = options.join("");
  select.value = selectedBaselinePreset;
}

async function loadBaselineCompare() {
  const compareUrl =
    selectedBaselinePreset === "current"
      ? "/api/baseline/compare"
      : `/api/baseline/compare?preset=${encodeURIComponent(selectedBaselinePreset)}`;
  const res = await fetch(compareUrl).then((r) => r.json());
  baseline = res.baseline || baseline;
  autoBaselineStatus = res.autoBaseline || autoBaselineStatus;
  updateBaselineUI();

  if (!selectedBaselinePreset || selectedBaselinePreset === "current") {
    if (autoBaselineStatus?.recording || !res.current || !res.bandwidthCompare) return;
  } else if (!res.current || !res.bandwidthCompare) {
    return;
  }
  renderBaselineCompare(res.current, res.bandwidthCompare);
}

async function loadBaseline() {
  const res = await fetch("/api/baseline").then((r) => r.json());
  baseline = res.baseline || null;
  autoBaselineStatus = res.autoBaseline || null;
  updateBaselineUI();
}

async function recordBaseline() {
  const btn = document.getElementById("recordBaselineBtn");
  btn.classList.add("recording");
  btn.disabled = true;
  btn.textContent = "Recording...";

  try {
    const res = await fetch("/api/baseline", { method: "POST" }).then((r) => r.json());
    if (res.error) {
      showAlert(res.error);
      return;
    }
    baseline = res.baseline || null;
    autoBaselineStatus = res.autoBaseline || null;
    updateBaselineUI();
    await loadBaselineCompare();
  } finally {
    btn.classList.remove("recording");
    btn.disabled = false;
    btn.textContent = "Record baseline";
  }
}

function initMap() {
  if (trafficMap) return;
  trafficMap = L.map("trafficMap", { worldCopyJump: true }).setView([20, 0], 2);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; CARTO',
    subdomains: "abcd",
    maxZoom: 19,
  }).addTo(trafficMap);
}

function renderGeo(geo) {
  if (geo.error) return;

  initMap();
  mapMarkers.forEach((m) => trafficMap.removeLayer(m));
  mapMarkers = [];

  for (const p of geo.points) {
    const radius = Math.max(6, Math.min(22, Math.sqrt(p.total_bytes / 400)));
    const marker = L.circleMarker([p.lat, p.lon], {
      radius,
      fillColor: "#3b82f6",
      color: "#93c5fd",
      weight: 1,
      fillOpacity: 0.8,
    }).bindPopup(
      `<strong>${p.ip}</strong><br>` +
        `${p.label || countryLabel(p.country)}<br>` +
        `Sessions: ${p.sessions}<br>` +
        `Traffic: ${fmtBytes(p.total_bytes)}<br>` +
        `${p.apps ? "Apps: " + p.apps + "<br>" : ""}` +
        `${p.domains ? "Domains: " + p.domains : ""}`
    );
    marker.addTo(trafficMap);
    mapMarkers.push(marker);
  }

  if (geo.points.length) {
    const bounds = L.latLngBounds(geo.points.map((p) => [p.lat, p.lon]));
    trafficMap.fitBounds(bounds, { padding: [48, 48], maxZoom: 5 });
  } else {
    trafficMap.setView([20, 0], 2);
  }

  document.getElementById("geoCountriesBody").innerHTML = geo.countries.length
    ? geo.countries
        .map(
          (c) =>
            `<tr>
              <td>${countryLabel(c.country)}</td>
              <td>${c.ip_count}</td>
              <td>${c.sessions.toLocaleString()}</td>
              <td class="col-bytes">${fmtBytes(c.total_bytes)}</td>
            </tr>`
        )
        .join("")
    : `<tr><td colspan="4">No geolocated traffic yet</td></tr>`;

  document.getElementById("geoIpsBody").innerHTML = geo.points.length
    ? geo.points
        .slice(0, 40)
        .map(
          (p) =>
            `<tr>
              <td><strong>${p.ip}</strong></td>
              <td>${p.label || countryLabel(p.country)}</td>
              <td>${p.sessions.toLocaleString()}</td>
              <td class="col-bytes">${fmtBytes(p.total_bytes)}</td>
              <td>${p.apps || "—"}</td>
            </tr>`
        )
        .join("")
    : `<tr><td colspan="5">No external IPs with geolocation data</td></tr>`;

  if (geo.externalIpCount === 0) {
    showAlert("No external IPs found in captured sessions yet.");
  } else if (geo.mappedIpCount === 0) {
    showAlert(
      `Found ${geo.externalIpCount} external IP(s) but none could be geolocated.`
    );
  }
}

function renderPorts(ports, portSessions) {
  if (ports.error) return;

  const top = ports.slice(0, 15);
  upsertChart(
    "portsChart",
    "bar",
    top.map((p) => `${p.port} (${p.service})`),
    [{
      label: "Total traffic",
      data: top.map((p) => p.total_bytes),
      backgroundColor: "#6366f1",
    }],
    { indexAxis: "y" }
  );

  document.getElementById("portsBody").innerHTML = ports.length
    ? ports
        .map(
          (p) =>
            `<tr>
              <td><strong>${p.port}</strong></td>
              <td>${p.service}</td>
              <td>${p.protocols || "—"}</td>
              <td>${p.sessions.toLocaleString()}</td>
              <td class="col-bytes">${fmtBytes(p.bytes_up)}</td>
              <td class="col-bytes">${fmtBytes(p.bytes_down)}</td>
              <td class="col-bytes">${fmtBytes(p.total_bytes)}</td>
              <td>${(p.apps || "—").split(",").slice(0, 3).join(", ")}</td>
            </tr>`
        )
        .join("")
    : `<tr><td colspan="8">No port data yet</td></tr>`;

  document.getElementById("portSessionsBody").innerHTML = portSessions.length
    ? portSessions
        .map(
          (r) =>
            `<tr>
              <td><strong>${r.dst_port ?? "—"}</strong></td>
              <td>${fmtTime(r.end_time)}</td>
              <td>${r.src_ip}</td><td>${r.dst_ip}</td><td>${r.app || "—"}</td>
              <td class="col-bytes">${fmtBytes(r.bytes_up)}</td><td class="col-bytes">${fmtBytes(r.bytes_down)}</td>
              <td>${r.protocol || "—"}</td>
            </tr>`
        )
        .join("")
    : `<tr><td colspan="8">No sessions with port data</td></tr>`;
}

function renderAnomalyPreview(records) {
  const preview = records.slice(0, 5);
  document.getElementById("anomaliesPreviewBody").innerHTML = preview.length
    ? preview
        .map(
          (r) =>
            `<tr>
              <td>${anomalyTag(r.anomaly)}</td>
              <td>${r.src_ip}</td><td>${r.dst_ip}</td>
              <td class="col-bytes">${fmtBytes(r.bytes_up)}</td><td class="col-bytes">${fmtBytes(r.bytes_down)}</td>
              <td>${r.app || "—"}</td>
            </tr>`
        )
        .join("") +
      `<tr class="preview-more"><td colspan="6"><button type="button" class="link-btn" id="viewAllAnomalies">View all ${records.length} in Anomalies tab →</button></td></tr>`
    : `<tr><td colspan="6">No anomalies detected</td></tr>`;

  document.getElementById("viewAllAnomalies")?.addEventListener("click", () => switchTab("anomalies"));
}

function setAnomalyFilter(type) {
  anomalyFilter = type;
  document.querySelectorAll("#anomalyFilters button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.type === type);
  });
  if (lastAnomalyDetails) renderAnomalyDetails(lastAnomalyDetails);
}

function setAnomalyRoleFilter(role) {
  anomalyRoleFilter = role;
  document.querySelectorAll("#anomalyRoleFilters button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.role === role);
  });
  if (lastAnomalyDetails) renderAnomalyDetails(lastAnomalyDetails);
}

function renderAnomalyDetails(details) {
  lastAnomalyDetails = details;
  setLocalDeviceIps(details.localIps);

  const rolePool = details.records.filter((r) => matchesAnomalyRole(r));
  const filtered = filterAnomalyRecords(details.records);
  const typeStats = buildAnomalyTypeCounts(rolePool);

  const meta = document.getElementById("anomalyMeta");
  if (meta) {
    const windowText = details.dataLive
      ? `Trailing ${details.windowSec ?? 300}s window`
      : "Database snapshot";
    const localHint =
      localDeviceIps.size > 0
        ? ` · local IPs: ${[...localDeviceIps].slice(0, 3).join(", ")}${localDeviceIps.size > 3 ? "…" : ""}`
        : "";
    meta.textContent = `${windowText} · showing ${filtered.length} of ${details.total} flagged session${details.total === 1 ? "" : "s"}${localHint}`;
  }

  document.getElementById("anomalyTypeCards").innerHTML = typeStats.length
    ? typeStats
        .map(
          (t) =>
            `<div class="anomaly-type-card" title="${t.description}">
              <span class="label">${t.label}</span>
              <span class="value">${t.count.toLocaleString()}</span>
            </div>`
        )
        .join("")
    : `<div class="anomaly-type-card empty"><span class="label">No anomalies</span><span class="value">0</span></div>`;

  if (typeStats.length) {
    updateOrCreateChart(
      "anomalyTypeChart",
      "doughnut",
      typeStats.map((t) => t.label),
      [{
        data: typeStats.map((t) => t.count),
        backgroundColor: typeStats.map((t) => ANOMALY_COLORS[t.type] || "#64748b"),
      }]
    );
  }

  const roleOptions = [
    { role: "all", label: "All", count: details.records.length },
    {
      role: "local_src",
      label: "Local as source",
      count: details.records.filter((r) => isLocalDeviceIp(r.src_ip)).length,
    },
    {
      role: "local_dst",
      label: "Local as destination",
      count: details.records.filter((r) => isLocalDeviceIp(r.dst_ip)).length,
    },
  ];
  document.getElementById("anomalyRoleFilters").innerHTML = roleOptions
    .map(
      (opt) =>
        `<button type="button" class="filter-chip${anomalyRoleFilter === opt.role ? " active" : ""}" data-role="${opt.role}">${opt.label} (${opt.count})</button>`
    )
    .join("");

  document.querySelectorAll("#anomalyRoleFilters button").forEach((btn) => {
    btn.addEventListener("click", () => setAnomalyRoleFilter(btn.dataset.role));
  });

  const filterTypes = [{ type: "all", label: "All", count: rolePool.length }, ...typeStats];
  document.getElementById("anomalyFilters").innerHTML = filterTypes
    .map(
      (t) =>
        `<button type="button" class="filter-chip${anomalyFilter === t.type ? " active" : ""}" data-type="${t.type}">${t.label}${t.type === "all" ? "" : ` (${t.count})`}</button>`
    )
    .join("");

  document.querySelectorAll("#anomalyFilters button").forEach((btn) => {
    btn.addEventListener("click", () => setAnomalyFilter(btn.dataset.type));
  });

  document.getElementById("anomalyDetailsBody").innerHTML = filtered.length
    ? filtered
        .map(
          (r) =>
            `<tr>
              <td>${fmtTime(r.end_time)}</td>
              <td>${anomalyTag(r.anomaly)}</td>
              ${ipCell(r.src_ip)}
              ${ipCell(r.dst_ip)}
              <td>${r.dst_port ?? "—"}</td>
              <td>${r.app || "—"}</td>
              <td>${r.destination_domain || "—"}</td>
              <td>${fmtDuration(r.duration_sec)}</td>
              <td class="col-bytes">${fmtBytes(r.bytes_up)}</td><td class="col-bytes">${fmtBytes(r.bytes_down)}</td>
              <td>${r.packets ?? "—"}</td>
              <td>${r.protocol || "—"}</td>
            </tr>`
        )
        .join("")
    : `<tr><td colspan="12">No anomalies match this filter</td></tr>`;
}

async function loadDashboard() {
  hideAlert();
  try {
    const status = await fetchJson("/api/status");
    const bwUrl = status.dataLive ? "/api/bandwidth?window=300" : "/api/bandwidth?limit=120";
    const [summary, bandwidth, anomalyDetails, sessions, ports, portSessions, geo] = await Promise.all([
      fetchJson("/api/summary"),
      fetchJson(bwUrl),
      fetchAnomalyDetails(status.dataLive),
      fetchJson("/api/ipdr?limit=50"),
      fetchJson("/api/ports?limit=50"),
      fetchJson("/api/ports/sessions?limit=80"),
      fetchJson("/api/geo?limit=5000"),
    ]);

    updateLiveBadge(status);

    if (summary.error) {
      showAlert(summary.error);
      return;
    }

    document.getElementById("mSessions").textContent = summary.totalSessions.toLocaleString();

    if (summary.dataLive && summary.currentDownloadBps != null) {
      document.getElementById("mDown").textContent = fmtRate(summary.currentDownloadBps);
      document.getElementById("mUp").textContent = fmtRate(summary.currentUploadBps);
    } else {
      document.getElementById("mDown").textContent = fmtBytes(summary.totalBytesDown);
      document.getElementById("mUp").textContent = fmtBytes(summary.totalBytesUp);
    }

    document.getElementById("mAnomalies").textContent = (anomalyDetails.total ?? summary.anomalyCount).toLocaleString();

    if (bandwidth.length) {
      const labels = summary.dataLive
        ? bandwidth.map((b) => fmtClock(b.timestamp))
        : bandwidth.map((_, i) => i);
      updateOrCreateChart("bandwidthChart", "line", labels, [
        {
          label: "Download B/s",
          data: bandwidth.map((b) => b.bytes_recv_per_sec),
          borderColor: "#3b82f6",
          tension: 0.3,
        },
        {
          label: "Upload B/s",
          data: bandwidth.map((b) => b.bytes_sent_per_sec),
          borderColor: "#22c55e",
          tension: 0.3,
        },
      ]);
    }

    updateOrCreateChart(
      "appsChart",
      "bar",
      summary.topApps.map((a) => a.name),
      [{
        label: "Sessions",
        data: summary.topApps.map((a) => a.count),
        backgroundColor: "#3b82f6",
      }]
    );

    updateOrCreateChart(
      "serviceChart",
      "doughnut",
      summary.serviceMix.map((s) => s.name),
      [{
        data: summary.serviceMix.map((s) => s.count),
        backgroundColor: ["#3b82f6", "#22c55e", "#f59e0b", "#a855f7", "#ef4444"],
      }]
    );

    if (summary.sessionTimeline) {
      renderSessionTimelineChart("hoursChart", summary.sessionTimeline);
    }

    document.getElementById("domainsBody").innerHTML = summary.topDomains
      .map(
        (d) =>
          `<tr><td>${d.name}</td><td class="col-bytes">${fmtBytes(d.bytes)}</td></tr>`
      )
      .join("");

    renderAnomalyPreview(anomalyDetails.records || []);
    renderAnomalyDetails(anomalyDetails);

    document.getElementById("sessionsBody").innerHTML = sessions
      .map(
        (r) =>
          `<tr>
            <td>${fmtTime(r.end_time)}</td>
            <td>${r.src_ip}</td><td>${r.dst_ip}</td><td>${r.app || "—"}</td>
            <td class="col-bytes">${fmtBytes(r.bytes_up)}</td><td class="col-bytes">${fmtBytes(r.bytes_down)}</td>
            <td>${r.protocol || "—"}</td>
            <td><span class="tag ${r.anomaly === "normal" ? "normal" : "anomaly"}">${r.anomaly}</span></td>
          </tr>`
      )
      .join("");

    renderPorts(ports, portSessions);
    renderGeo(geo);
    await loadBaselineCompare();
  } catch (err) {
    showAlert("Failed to load dashboard: " + err.message);
  }
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

document.getElementById("refreshBtn").addEventListener("click", loadDashboard);
document.getElementById("recordBaselineBtn")?.addEventListener("click", recordBaseline);
document.getElementById("baselinePresetSelect")?.addEventListener("change", (event) => {
  selectedBaselinePreset = event.target.value || "current";
  updateBaselineUI();
  loadBaselineCompare().catch(() => {});
});
document.getElementById("anomalyMetricCard")?.addEventListener("click", () => switchTab("anomalies"));
document.querySelectorAll("#baselineBwToggles input[data-series]").forEach((input) => {
  input.addEventListener("change", () => {
    baselineBwVisible[input.dataset.series] = input.checked;
    applyBaselineBwVisibility();
  });
});
loadBaseline().catch(() => {});
loadBaselinePresets().catch(() => {});
loadDashboard();
