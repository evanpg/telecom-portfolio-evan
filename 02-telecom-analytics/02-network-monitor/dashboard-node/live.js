/**
 * Start live collection + dashboard together.
 * Ctrl+C stops both processes.
 */

const { spawn } = require("child_process");
const path = require("path");

const ROOT = path.join(__dirname, "..");
const pythonCmd = process.platform === "win32" ? "python" : "python3";

const collector = spawn(
  pythonCmd,
  ["-u", "run_monitor.py", "live", "--interval", "2", "--quiet"],
  { cwd: ROOT, stdio: "inherit", env: process.env }
);

const DASHBOARD_PORT = process.env.DASHBOARD_PORT || "3000";

const server = spawn("node", ["server.js"], {
  cwd: __dirname,
  stdio: "inherit",
  env: { ...process.env, LIVE_MODE: "1", PORT: DASHBOARD_PORT },
});

function shutdown() {
  if (!collector.killed) collector.kill();
  if (!server.killed) server.kill();
  process.exit(0);
}

collector.on("exit", (code) => {
  if (code && code !== 0) console.error(`Collector exited with code ${code}`);
  shutdown();
});

server.on("exit", (code) => {
  if (code && code !== 0) console.error(`Dashboard exited with code ${code}`);
  shutdown();
});

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);

console.log("Live monitor starting (collector + dashboard)...");
console.log(`Open http://localhost:${DASHBOARD_PORT} when the dashboard is ready.\n`);
