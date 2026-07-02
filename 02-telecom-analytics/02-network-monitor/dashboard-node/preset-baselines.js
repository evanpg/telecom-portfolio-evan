const fs = require("fs");
const path = require("path");

const PRESET_BASELINES = [
  { id: "peak-hours", label: "Peak Hours", filename: "peak-hours.json" },
  { id: "off-peak-hours", label: "Off-Peak Hours", filename: "off-peak-hours.json" },
  { id: "vacation", label: "Vacation", filename: "vacation.json" },
];

const PRESET_PROFILES = {
  "peak-hours": peakHoursProfile,
  "off-peak-hours": offPeakHoursProfile,
  vacation: vacationProfile,
};

function wave(t, period, amplitude = 1) {
  return amplitude * (0.5 + 0.5 * Math.sin((t / period) * Math.PI * 2));
}

function jitter(base, t, spread = 0.12) {
  const n = Math.sin(t * 0.41) * Math.cos(t * 0.17);
  return Math.max(0, Math.round(base * (1 + n * spread)));
}

function peakHoursProfile(t, windowSec) {
  const rush = 0.55 + 0.45 * wave(t, windowSec / 2);
  const spike = t > windowSec * 0.42 && t < windowSec * 0.58 ? 1.75 : 1;
  return {
    up: jitter(28000 * rush * spike, t, 0.18),
    down: jitter(135000 * rush * spike, t, 0.18),
  };
}

function offPeakHoursProfile(t, windowSec) {
  const drift = 0.75 + 0.25 * wave(t, 90);
  return {
    up: jitter(9000 * drift, t, 0.14),
    down: jitter(28000 * drift, t, 0.14),
  };
}

function vacationProfile(t) {
  const burst = t % 72 < 8 ? 1.6 : 1;
  return {
    up: jitter(1400 * burst, t, 0.22),
    down: jitter(4500 * burst, t, 0.22),
  };
}

function sessionCountForPreset(presetId, index, bucketCount) {
  const progress = index / Math.max(1, bucketCount - 1);
  if (presetId === "peak-hours") {
    const peak = progress > 0.25 && progress < 0.8 ? 4 : 1;
    return Math.max(0, Math.round(peak + Math.sin(index * 0.9) * 2));
  }
  if (presetId === "off-peak-hours") {
    return Math.max(0, Math.round(1 + Math.sin(index * 0.55)));
  }
  return index % 11 === 0 ? 1 : 0;
}

function formatTrailingLabel(offsetSec) {
  if (offsetSec === 0) return "0s";
  const abs = Math.abs(offsetSec);
  const mins = Math.floor(abs / 60);
  const secs = abs % 60;
  return `-${mins}:${String(secs).padStart(2, "0")}`;
}

function buildPresetSessionTimeline(presetId, windowSec, bucketSec) {
  const bucketCount = Math.floor(windowSec / bucketSec);
  const buckets = [];
  for (let i = 0; i < bucketCount; i++) {
    const offsetSec = -windowSec + i * bucketSec;
    buckets.push({
      label: formatTrailingLabel(offsetSec),
      count: sessionCountForPreset(presetId, i, bucketCount),
      offsetSec,
    });
  }
  return {
    buckets,
    bucketSec,
    windowSec,
    windowEnd: new Date().toISOString(),
  };
}

function buildPresetBandwidth(presetId, windowSec) {
  const profile = PRESET_PROFILES[presetId];
  const samples = [];
  const baseTs = Date.now() / 1000 - windowSec;
  for (let t = 0; t <= windowSec; t += 2) {
    const { up, down } = profile(t, windowSec);
    samples.push({
      timestamp: baseTs + t,
      bytes_sent_per_sec: up,
      bytes_recv_per_sec: down,
      packets_sent_per_sec: Math.max(1, Math.round(up / 480)),
      packets_recv_per_sec: Math.max(1, Math.round(down / 480)),
    });
  }
  return samples;
}

function buildPresetSnapshot(preset, windowSec, bucketSec) {
  const bandwidth = buildPresetBandwidth(preset.id, windowSec);
  const sessionTimeline = buildPresetSessionTimeline(preset.id, windowSec, bucketSec);
  const avgUp =
    bandwidth.reduce((sum, row) => sum + row.bytes_sent_per_sec, 0) / bandwidth.length;
  const avgDown =
    bandwidth.reduce((sum, row) => sum + row.bytes_recv_per_sec, 0) / bandwidth.length;

  return {
    createdAt: new Date().toISOString(),
    windowSec,
    presetId: preset.id,
    presetLabel: preset.label,
    isPreset: true,
    summary: {
      live: false,
      windowSec,
      totalSessions: sessionTimeline.buckets.reduce((sum, b) => sum + b.count, 0),
      currentUploadBps: Math.round(avgUp),
      currentDownloadBps: Math.round(avgDown),
      sessionTimeline,
    },
    bandwidth,
    sessionTimeline,
  };
}

function getPresetsDir(presetsDir) {
  return presetsDir || path.join(__dirname, "data", "baselines");
}

function ensurePresetBaselines(presetsDir, windowSec = 180, bucketSec = 5) {
  const dir = getPresetsDir(presetsDir);
  fs.mkdirSync(dir, { recursive: true });

  for (const preset of PRESET_BASELINES) {
    const filePath = path.join(dir, preset.filename);
    if (fs.existsSync(filePath)) continue;
    const snapshot = buildPresetSnapshot(preset, windowSec, bucketSec);
    fs.writeFileSync(filePath, JSON.stringify(snapshot, null, 2));
  }
}

function readPresetBaseline(presetId, presetsDir) {
  const preset = PRESET_BASELINES.find((entry) => entry.id === presetId);
  if (!preset) return null;

  const filePath = path.join(getPresetsDir(presetsDir), preset.filename);
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf-8"));
  } catch {
    ensurePresetBaselines(presetsDir);
    try {
      return JSON.parse(fs.readFileSync(filePath, "utf-8"));
    } catch {
      return null;
    }
  }
}

module.exports = {
  PRESET_BASELINES,
  ensurePresetBaselines,
  readPresetBaseline,
};
