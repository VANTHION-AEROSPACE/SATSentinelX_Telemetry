import fs from "node:fs";
import vm from "node:vm";

const ids = [
  "port-select", "settings-port-select", "refresh-ports", "connect", "disconnect", "connection-status",
  "last-message", "uptime", "temperature-value", "temperature-time", "humidity-value",
  "humidity-time", "pressure-value", "pressure-time", "valid-records", "invalid-records",
  "sequence-errors", "data-gaps", "session-duration", "total-records", "start-logging",
  "stop-logging", "download", "clear-records", "messages-list", "temperature-chart",
  "humidity-chart", "pressure-chart", "temperature-empty", "humidity-empty", "pressure-empty",
  "records-body", "log-records-body", "log-clear", "session-indicator", "session-status",
  "session-page-duration", "session-total-records", "session-valid-records", "session-start",
  "session-stop", "session-download", "session-integrity", "chart-window", "auto-refresh",
  "settings-refresh-ports"
  ,"source-label", "replay-source", "replay-speed", "replay-play", "replay-pause", "replay-reset", "replay-progress",
  "incident-empty", "incident-details", "evidence-download", "incident-id", "incident-classification", "incident-onset", "incident-threshold",
  "incident-config", "incident-channels", "incident-records"
];

class Element {
  constructor(id) {
    this.id = id; this.value = ""; this.disabled = false; this.title = ""; this.innerHTML = "";
    this.textContent = ""; this.checked = false; this.onclick = null; this.onchange = null;
    this.clientWidth = 400; this.clientHeight = 165; this.style = {};
    this.className = ""; this.href = ""; this.download = ""; this.clicked = false;
    this.classList = {toggle: (name, enabled) => { this.className = enabled ? name : ""; }};
  }
  click() { this.clicked = true; }
  querySelector(selector) { return selector === "strong" ? this.statusStrong : this.statusSmall; }
  getContext() { return {setTransform() {}, clearRect() {}, beginPath() {}, moveTo() {}, lineTo() {}, stroke() {}, fillText() {}, font: "", strokeStyle: "", fillStyle: "", lineWidth: 1}; }
}

const elements = Object.fromEntries(ids.map(id => [id, new Element(id)]));
const createdAnchors = [];
elements["connection-status"].statusStrong = new Element("status-strong");
elements["connection-status"].statusSmall = new Element("status-small");
const nav = ["dashboard-view", "log-view", "session-view", "incident-view", "settings-view"].map(view => ({dataset: {view}, onclick: null, addEventListener(type, handler) { if (type === "click") this.onclick = handler; }, classList: {toggle() {}}}));
const panels = ["dashboard-view", "log-view", "session-view", "incident-view", "settings-view"].map(id => ({id, classList: {toggle(name, enabled) { this.active = enabled; }}}));
for (const panel of panels) elements[panel.id] = panel;
const ports = [{device: "COM9", description: "Synthetic serial", hwid: "synthetic"}];
const record = {seq: 7, device_time_ms: 700, temperature_c: 24.5, sensor_valid: true, sensor_status: "measurement_verified", sequence_status: "first", host_received_utc: "2026-01-01T00:00:00Z", host_received_monotonic_s: 1};
const backend = {status: "disconnected", status_detail: "No device connected", logging: false};
const calls = [];
const storage = new Map();
const location = {_hash: "", href: "", get hash() { return this._hash; }, set hash(value) { this._hash = value ? (value.startsWith("#") ? value : `#${value}`) : ""; }};
const windowObject = {location, devicePixelRatio: 1, addEventListener() {}};

const documentObject = {
  getElementById(id) { return elements[id]; },
  createElement() { return new Element("option"); },
  querySelectorAll(selector) { return selector === ".nav-item" ? nav : panels; }
};

function statePayload() {
  return {status: backend.status, status_detail: backend.status_detail, logging: backend.logging,
    last_message_age_s: null, uptime_s: 1, records: [record], chart: [{temperature_c: 24.5, humidity_pct: null, pressure_hpa: null}],
    stats: {valid_records: 1, invalid_records: 0, sequence_anomalies: 0, data_gaps: 0, session_duration_s: 1, total_records: 1, logged_records: 1}, replay: null, source_type: "live_serial", incident: {incident_id: "synthetic-thermal-rise-001", detector: {id: "synthetic_temperature_threshold_v1", version: "1.0", threshold_c: 26, rule: "temperature_c > threshold_c"}, classification: "synthetic_threshold_breach", onset_device_time_ms: 4000, affected_channels: ["temperature_c"], baseline_median_c: 22, record_refs: [{seq: 8, device_time_ms: 4000, temperature_c: 30}]},
    messages: []};
}

async function fetchMock(path, options = {}) {
  calls.push({path, method: options.method || "GET"});
  if (path === "/api/ports") return {ok: true, async json() { return {ports}; }};
  if (path === "/api/state") return {ok: true, async json() { return statePayload(); }};
  if (path === "/api/session/export") return {ok: true, async json() { return {}; }};
  if (path === "/api/evidence/export") return {ok: true, async text() { return JSON.stringify(statePayload().incident); }};
  if (options.method === "POST") {
    if (path === "/api/connect") { backend.status = "connected"; backend.status_detail = "Receiving telemetry"; }
    if (path === "/api/disconnect") { backend.status = "disconnected"; backend.status_detail = "No device connected"; }
    if (path === "/api/session/start") backend.logging = true;
    if (path === "/api/session/stop") backend.logging = false;
    return {ok: true, async json() { return {ok: true, detail: "ok"}; }};
  }
  throw new Error(`Unexpected request: ${path}`);
}

const context = {
  window: windowObject, document: documentObject, localStorage: {getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, String(value))},
  fetch: fetchMock, setInterval() {}, setTimeout(callback) { callback(); }, Blob: class Blob { constructor(parts, options) { this.parts = parts; this.options = options; } }, URL: {createObjectURL() { return "blob:synthetic"; }, revokeObjectURL() {}}, alert(message) { throw new Error(`Unexpected alert: ${message}`)}, console
};
context.document.createElement = (tag) => { const element = new Element(tag); if (tag === "a") createdAnchors.push(element); return element; };
vm.runInNewContext(fs.readFileSync(new URL("../dashboard/app.js", import.meta.url), "utf8"), context);
await new Promise(resolve => setTimeout(resolve, 20));

if (!elements["connect"].disabled) throw new Error("Connect should start disabled without a selected port");
elements["port-select"].value = "COM9";
elements["port-select"].onchange();
if (elements["connect"].disabled) throw new Error("Selecting a port did not enable Connect");
await elements["connect"].onclick();
if (!calls.some(call => call.path === "/api/connect" && call.method === "POST")) throw new Error("Connect request was not sent");
await elements["start-logging"].onclick();
await elements["stop-logging"].onclick();
if (!calls.some(call => call.path === "/api/session/start" && call.method === "POST")) throw new Error("Start logging request was not sent");
if (!calls.some(call => call.path === "/api/session/stop" && call.method === "POST")) throw new Error("Stop logging request was not sent");
await elements["disconnect"].onclick();
if (!calls.some(call => call.path === "/api/disconnect" && call.method === "POST")) throw new Error("Disconnect request was not sent");
elements["clear-records"].onclick();
if (!elements["records-body"].innerHTML.includes("No telemetry data")) throw new Error("Clear display did not clear visible records");
elements["download"].onclick();
if (windowObject.location.href !== "/api/session/export") throw new Error("Download did not target the export endpoint");
nav[1].onclick();
if (!panels[1].classList.active || windowObject.location.hash !== "#log-view") throw new Error("Navigation did not activate Telemetry Log");
elements["chart-window"].value = "60"; elements["chart-window"].onchange({target: elements["chart-window"]});
if (storage.get("satsentinel.chartWindow") !== "60") throw new Error("Chart window preference was not saved");
elements["auto-refresh"].checked = false; elements["auto-refresh"].onchange({target: elements["auto-refresh"]});
if (storage.get("satsentinel.autoRefresh") !== "false") throw new Error("Auto-refresh preference was not saved");
await elements["settings-refresh-ports"].onclick();
if (!calls.some(call => call.path === "/api/ports")) throw new Error("Settings port refresh was not sent");
await elements["evidence-download"].onclick();
if (!createdAnchors.some(anchor => anchor.download === "SATSentinelX_Incident_synthetic-thermal-rise-001.json" && anchor.href === "blob:synthetic" && anchor.clicked)) throw new Error("Evidence download did not create a named Blob download");
console.log("frontend controls: PASS");
