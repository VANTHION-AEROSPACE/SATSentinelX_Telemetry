const $ = (id) => document.getElementById(id);

const state = {
  last: null,
  activeView: window.location.hash.slice(1) || "dashboard-view",
  hiddenRecordKeys: new Set(),
  chartWindow: Number(localStorage.getItem("satsentinel.chartWindow") || 180),
  autoRefresh: localStorage.getItem("satsentinel.autoRefresh") !== "false"
};

/**
 * Escapes characters for safe HTML interpolation.
 */
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[character]));
}

/**
 * Generates a unique key for a telemetry record.
 */
function recordKey(record) {
  return `${record.seq}:${record.host_received_monotonic_s}`;
}

/**
 * Filters out records hidden by the user.
 */
function visibleRecords(data) {
  return (data.records || []).filter((record) => !state.hiddenRecordKeys.has(recordKey(record)));
}

/**
 * Sends a JSON POST request and validates the response.
 */
function post(path, body = {}) {
  return fetch(path, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body)
  }).then(async (response) => {
    let data = {};
    try {
      data = await response.json();
    } catch (_) {
      data = {};
    }
    if (!response.ok) throw new Error(data.detail || data.error || `HTTP ${response.status}`);
    return data;
  });
}

/**
 * Formats a duration in seconds to HH:MM:SS format.
 */
function duration(seconds) {
  const s = Math.max(0, Math.floor(seconds || 0));
  return [Math.floor(s / 3600), Math.floor((s % 3600) / 60), s % 60]
    .map(v => String(v).padStart(2, "0"))
    .join(":");
}

/**
 * Formats the age of the last telemetry message into human-readable text.
 */
function ageLabel(age) {
  if (age === null || age === undefined) return "--:--:--";
  return age < 60 ? `${age.toFixed(1)}s ago` : `${Math.floor(age / 60)}m ago`;
}

/**
 * Extracts a numeric value from a record with specified decimal places.
 */
function value(record, key, decimals = 2) {
  const v = record && record[key];
  return typeof v === "number" && Number.isFinite(v) ? v.toFixed(decimals) : "—";
}

/**
 * Helper to convert color hex strings to rgba with given opacity.
 */
function colorToRgba(color, opacity) {
  if (color === "#ff5c67") return `rgba(255, 92, 103, ${opacity})`;
  if (color === "#55aaf5") return `rgba(85, 170, 245, ${opacity})`;
  if (color === "#83db9b") return `rgba(131, 219, 155, ${opacity})`;
  if (color === "#f2bd62") return `rgba(242, 189, 98, ${opacity})`;
  return `rgba(100, 178, 251, ${opacity})`;
}

/**
 * Displays an aerospace console toast notification and writes to #messages-list.
 */
function showNotification(message, level = "info") {
  // Create toast notification if DOM body is available
  const appendTarget = document.body || (document.documentElement || null);
  if (!appendTarget) {
    // Fallback: just update messages-list when no DOM body (e.g. Node test harness)
    const msgList = $("messages-list");
    if (msgList) {
      msgList.innerHTML += `<div class="message ${escapeHtml(level)}">[${escapeHtml(level.toUpperCase())}] ${escapeHtml(message)}</div>`;
    }
    return;
  }

  let container = $("notifications");
  if (!container) {
    container = document.createElement("div");
    container.id = "notifications";
    container.style.cssText = "position:fixed;top:20px;right:20px;z-index:9999;display:flex;flex-direction:column;gap:10px;pointer-events:none;max-width:380px;";
    appendTarget.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = `toast-notification ${level}`;
  const borderColor = level === "error" ? "#ff5c67" : (level === "warning" ? "#f2bd62" : "#55aaf5");
  toast.style.cssText = `background:rgba(12, 26, 41, 0.95);border:1px solid #1d3953;border-left:4px solid ${borderColor};color:#e9f0f7;padding:11px 16px;border-radius:6px;box-shadow:0 8px 24px rgba(0,0,0,0.55);font-size:13px;pointer-events:auto;opacity:0;transform:translateY(-8px);transition:opacity 0.25s ease,transform 0.25s ease;display:flex;align-items:center;justify-content:space-between;gap:12px;`;

  const textSpan = document.createElement("span");
  textSpan.textContent = message;
  toast.appendChild(textSpan);

  const closeBtn = document.createElement("button");
  closeBtn.textContent = "×";
  closeBtn.style.cssText = "background:transparent;border:0;color:#8ca0b4;font-size:16px;cursor:pointer;padding:0 4px;";
  closeBtn.onclick = () => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(-8px)";
    setTimeout(() => toast.remove(), 250);
  };
  toast.appendChild(closeBtn);

  container.appendChild(toast);
  requestAnimationFrame(() => {
    toast.style.opacity = "1";
    toast.style.transform = "translateY(0)";
  });

  setTimeout(() => {
    if (toast.parentNode) {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(-8px)";
      setTimeout(() => toast.remove(), 250);
    }
  }, 4000);

  const messagesList = $("messages-list");
  if (messagesList) {
    const timeStr = new Date().toTimeString().slice(0, 8);
    const msgEl = document.createElement("div");
    msgEl.className = `message ${level}`;
    msgEl.textContent = `[${level.toUpperCase()} ${timeStr}] ${message}`;
    messagesList.insertBefore(msgEl, messagesList.firstChild);
    while (messagesList.children.length > 8) {
      messagesList.removeChild(messagesList.lastChild);
    }
  }
}

/**
 * Updates serial port select dropdowns in both connection and settings panels.
 */
function renderPorts(ports) {
  const selects = [$('port-select'), $('settings-port-select')].filter(Boolean);
  selects.forEach((select) => {
    const current = select.value;
    select.innerHTML = '<option value="">Select port</option>';
    (ports || []).forEach((port) => {
      const option = document.createElement("option");
      option.value = port.device;
      option.textContent = `${port.device} · ${port.description}`;
      select.appendChild(option);
    });
    if ((ports || []).some(port => port.device === current)) select.value = current;
  });
}

/**
 * High-precision canvas chart renderer with gridlines, gradients, thresholds, anomaly shading, and crosshairs.
 */
function drawChart(canvasId, emptyId, points, key, color, unit) {
  const canvas = $(canvasId);
  const empty = $(emptyId);
  if (!canvas) return;

  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 400;
  const height = canvas.clientHeight || 165;
  canvas.width = width * dpr;
  canvas.height = height * dpr;

  const ctx = canvas.getContext("2d");
  // Polyfill canvas methods for test environments that provide minimal context mocks
  if (!ctx.save) ctx.save = () => {};
  if (!ctx.restore) ctx.restore = () => {};
  if (!ctx.setLineDash) ctx.setLineDash = () => {};
  if (!ctx.fillRect) ctx.fillRect = () => {};
  if (!ctx.closePath) ctx.closePath = () => {};
  if (!ctx.fill) ctx.fill = () => {};
  if (!ctx.arc) ctx.arc = () => {};
  if (!ctx.rect) ctx.rect = () => {};
  if (!ctx.createLinearGradient) ctx.createLinearGradient = () => ({ addColorStop() {} });
  if (!ctx.measureText) ctx.measureText = () => ({ width: 0 });
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const values = points.map(p => p[key]).filter(v => typeof v === "number" && Number.isFinite(v));
  if (!values.length) {
    if (empty) empty.style.display = "block";
    return;
  }
  if (empty) empty.style.display = "none";

  const min = Math.min(...values);
  const max = Math.max(...values);
  const pad = Math.max((max - min) * 0.2, key === "temperature_c" ? 2 : 1);
  let lo = min - pad;
  let hi = max + pad;

  const hasIncident = Boolean(state.last && state.last.incident && state.last.incident.incident_id);
  const thresholdVal = (hasIncident && state.last.incident.detector && state.last.incident.detector.threshold_c) || 26.0;

  // Ensure threshold is visible in y range if incident is active
  if (key === "temperature_c" && hasIncident) {
    if (hi < thresholdVal + 0.8) hi = thresholdVal + 0.8;
    if (lo > thresholdVal - 0.8) lo = thresholdVal - 0.8;
  }

  const left = 32;
  const right = 8;
  const top = 10;
  const bottom = 22;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;

  // 1. Refined horizontal gridlines and Y-axis tick labels
  ctx.font = "10px Inter, Segoe UI, sans-serif";
  ctx.strokeStyle = "#162538";
  ctx.fillStyle = "#8ca0b4";
  ctx.lineWidth = 1;

  for (let i = 0; i < 4; i++) {
    const y = top + i * (plotHeight / 3);
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(width - right, y);
    ctx.stroke();

    const tickVal = hi - i * (hi - lo) / 3;
    const label = tickVal.toFixed(key === "pressure_hpa" ? 0 : 1);
    ctx.fillText(label, 2, y + 3.5);
  }

  // 2. Vertical time gridlines
  ctx.strokeStyle = "#122030";
  for (let j = 1; j <= 3; j++) {
    const gx = left + j * (plotWidth / 4);
    ctx.beginPath();
    ctx.moveTo(gx, top);
    ctx.lineTo(gx, height - bottom);
    ctx.stroke();
  }

  // 3. Shaded anomaly region when applicable (temperature chart with incident active)
  if (key === "temperature_c" && hasIncident) {
    let firstAnomIdx = -1;
    let lastAnomIdx = -1;
    points.forEach((p, idx) => {
      const v = p[key];
      if (typeof v === "number" && v >= thresholdVal) {
        if (firstAnomIdx === -1) firstAnomIdx = idx;
        lastAnomIdx = idx;
      }
    });

    if (firstAnomIdx !== -1 && lastAnomIdx !== -1) {
      const ptCount = Math.max(points.length - 1, 1);
      const step = plotWidth / ptCount;
      const anomX1 = Math.max(left, left + (firstAnomIdx / ptCount) * plotWidth - step * 0.45);
      const anomX2 = Math.min(width - right, left + (lastAnomIdx / ptCount) * plotWidth + step * 0.45);
      const anomW = Math.max(6, anomX2 - anomX1);

      ctx.save();
      ctx.fillStyle = "rgba(242, 189, 98, 0.12)";
      ctx.fillRect(anomX1, top, anomW, plotHeight);

      ctx.strokeStyle = "rgba(242, 189, 98, 0.35)";
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 2]);
      ctx.beginPath();
      ctx.moveTo(anomX1, top);
      ctx.lineTo(anomX1, height - bottom);
      ctx.moveTo(anomX2, top);
      ctx.lineTo(anomX2, height - bottom);
      ctx.stroke();

      ctx.fillStyle = "rgba(242, 189, 98, 0.75)";
      ctx.font = "9px Inter, Segoe UI, sans-serif";
      ctx.fillText("ANOMALY REGION", anomX1 + 4, top + 11);
      ctx.restore();
    }
  }

  // 4. Threshold line at 26°C (amber dashed line with label)
  if (key === "temperature_c" && hasIncident) {
    if (thresholdVal >= lo && thresholdVal <= hi) {
      const threshY = top + ((hi - thresholdVal) / (hi - lo)) * plotHeight;
      ctx.save();
      ctx.strokeStyle = "#f2bd62";
      ctx.lineWidth = 1.25;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(left, threshY);
      ctx.lineTo(width - right, threshY);
      ctx.stroke();

      ctx.fillStyle = "#f2bd62";
      ctx.font = "9px Inter, Segoe UI, sans-serif";
      ctx.fillText(`${thresholdVal.toFixed(1)}°C THRESHOLD`, left + 6, threshY - 4);
      ctx.restore();
    }
  }

  // 5. Compute coordinates of valid plotted data points
  const coords = [];
  points.forEach((point, index) => {
    const v = point[key];
    if (typeof v !== "number" || !Number.isFinite(v)) return;
    const x = left + (index / Math.max(points.length - 1, 1)) * plotWidth;
    const y = top + ((hi - v) / (hi - lo)) * plotHeight;
    coords.push({ x, y, point, index });
  });

  if (coords.length > 0) {
    // Faint gradient fill below line trace
    const grad = ctx.createLinearGradient(0, top, 0, height - bottom);
    grad.addColorStop(0, colorToRgba(color, 0.20));
    grad.addColorStop(1, colorToRgba(color, 0.0));

    ctx.save();
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(coords[0].x, height - bottom);
    coords.forEach(pt => ctx.lineTo(pt.x, pt.y));
    ctx.lineTo(coords[coords.length - 1].x, height - bottom);
    ctx.closePath();
    ctx.fill();
    ctx.restore();

    // Anti-aliased line trace
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.beginPath();
    coords.forEach((pt, idx) => {
      idx === 0 ? ctx.moveTo(pt.x, pt.y) : ctx.lineTo(pt.x, pt.y);
    });
    ctx.stroke();
    ctx.restore();
  }

  // 6. Time axis labels where possible
  const validTimes = coords.filter(c => c.point.time);
  if (validTimes.length >= 2) {
    ctx.save();
    ctx.fillStyle = "#637990";
    ctx.font = "9px Inter, Segoe UI, sans-serif";

    const firstTime = validTimes[0].point.time.split("T").pop().replace("Z", "");
    const lastTime = validTimes[validTimes.length - 1].point.time.split("T").pop().replace("Z", "");
    ctx.fillText(firstTime, left, height - 5);

    const lastTimeWidth = ctx.measureText(lastTime).width;
    ctx.fillText(lastTime, width - right - lastTimeWidth - 48, height - 5);
    ctx.restore();
  }

  // Unit indicator
  ctx.fillStyle = "#8094a8";
  ctx.font = "11px Inter, Segoe UI, sans-serif";
  ctx.fillText(unit, width - 42, height - 5);

  // 7. Interactive hover crosshair and tooltip system
  if (!canvas._hasHoverListener) {
    canvas._hasHoverListener = true;
    canvas.addEventListener("mousemove", (event) => {
      const rect = canvas.getBoundingClientRect();
      canvas._hoverPos = {
        x: event.clientX - rect.left,
        y: event.clientY - rect.top
      };
      if (canvas._redraw) canvas._redraw();
    });
    canvas.addEventListener("mouseleave", () => {
      canvas._hoverPos = null;
      if (canvas._redraw) canvas._redraw();
    });
  }
  canvas._redraw = () => drawChart(canvasId, emptyId, points, key, color, unit);

  if (canvas._hoverPos && coords.length > 0) {
    const hx = canvas._hoverPos.x;
    if (hx >= left && hx <= width - right) {
      // Find nearest data coordinate by X distance
      let nearest = coords[0];
      let minDist = Math.abs(coords[0].x - hx);
      coords.forEach(c => {
        const d = Math.abs(c.x - hx);
        if (d < minDist) {
          minDist = d;
          nearest = c;
        }
      });

      if (nearest && nearest.point && typeof nearest.point[key] === "number") {
        ctx.save();

        // Subtle vertical crosshair line
        ctx.strokeStyle = "rgba(255, 255, 255, 0.28)";
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(nearest.x, top);
        ctx.lineTo(nearest.x, height - bottom);
        ctx.stroke();
        ctx.setLineDash([]);

        // Highlight circle at nearest data point
        ctx.fillStyle = color;
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(nearest.x, nearest.y, 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        // Tooltip card
        const valStr = `${nearest.point[key].toFixed(key === "pressure_hpa" ? 1 : 2)} ${unit}`;
        const timeStr = nearest.point.time ? nearest.point.time.split("T").pop().replace("Z", "") : "";
        const tipText = timeStr ? `${valStr} · ${timeStr}` : valStr;

        ctx.font = "10px Inter, Segoe UI, sans-serif";
        const metrics = ctx.measureText(tipText);
        const boxW = metrics.width + 16;
        const boxH = 22;

        let boxX = nearest.x - boxW / 2;
        if (boxX < left) boxX = left;
        if (boxX + boxW > width - right) boxX = width - right - boxW;

        let boxY = nearest.y - 28;
        if (boxY < top) boxY = nearest.y + 10;

        ctx.fillStyle = "rgba(12, 26, 41, 0.94)";
        ctx.strokeStyle = "#274057";
        ctx.lineWidth = 1;
        ctx.beginPath();
        if (ctx.roundRect) {
          ctx.roundRect(boxX, boxY, boxW, boxH, 4);
        } else {
          ctx.rect(boxX, boxY, boxW, boxH);
        }
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = "#ffffff";
        ctx.fillText(tipText, boxX + 8, boxY + 15);
        ctx.restore();
      }
    }
  }
}

/**
 * Toggles active class on navigation items and view panels.
 */
function renderNav() {
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.view === state.activeView);
  });
  document.querySelectorAll("[data-view-panel]").forEach((panel) => {
    panel.classList.toggle("active-view", panel.id === state.activeView);
  });
}

/**
 * Renders telemetry table with exact 7-column aerospace layout.
 */
function renderTable(records, bodyId, emptyText, columns) {
  const body = $(bodyId);
  if (!body) return;
  if (!records.length) {
    body.innerHTML = `<tr class="empty-row"><td colspan="${columns}">${emptyText}</td></tr>`;
    return;
  }
  body.innerHTML = records.slice(0, 100).map((record) => `<tr><td>${escapeHtml(record.seq)}</td><td>${escapeHtml(record.host_received_utc || "—")}</td><td>${escapeHtml(record.device_time_ms ?? "—")}</td><td>${escapeHtml(value(record, "temperature_c"))}</td><td>${escapeHtml(record.sensor_status || "—")}</td><td>${escapeHtml(record.sequence_status || "—")}</td><td class="${record.sensor_valid ? "valid" : "invalid"}">${record.sensor_valid ? "VALID" : "INVALID"}</td></tr>`).join("");
}

/**
 * Updates aerospace subsystem status cards across the dashboard.
 */
function renderSubsystems(data) {
  const records = data.records || [];
  const latest = records[0];
  const hasIncident = Boolean(data.incident && data.incident.incident_id);
  const tempValid = latest && typeof latest.temperature_c === "number" && Number.isFinite(latest.temperature_c);
  const tempDisplay = tempValid ? `${latest.temperature_c.toFixed(1)} °C` : null;

  const cards = document.querySelectorAll(".subsystem-card");
  if (!cards || !cards.length) { /* No subsystem cards in DOM; skip */ }
  else cards.forEach((card) => {
    if (!card || !card.dataset) return;
    const rawName = card.dataset.subsystem || card.dataset.name || (card.querySelector ? (card.querySelector(".subsystem-name, .subsystem-title, h3, h4") || {}).textContent : "") || "";
    const name = rawName.trim().toUpperCase();
    const statusEl = card.querySelector ? card.querySelector(".subsystem-badge, .subsystem-status, .status-indicator, .status") : null;
    const detailEl = card.querySelector ? card.querySelector(".subsystem-status-text > span:first-child") : null;
    const valueEl = card.querySelector ? card.querySelector(".subsystem-value, .metric-value, .value") : null;

    if (name.includes("THERMAL")) {
      card.classList.remove("nominal", "anomaly", "has-anomaly", "no-data", "active", "muted");
      if (hasIncident) {
        if (statusEl) {
          statusEl.textContent = "ANOMALY";
          statusEl.className = "subsystem-badge anomaly warning";
        }
        if (detailEl) detailEl.textContent = "Threshold breach detected";
        card.classList.add("anomaly", "has-anomaly");
      } else if (tempValid) {
        if (statusEl) {
          statusEl.textContent = "ACTIVE";
          statusEl.className = "subsystem-badge active-thermal";
        }
        if (detailEl) detailEl.textContent = "Validated temperature reading";
        card.classList.add("nominal", "active");
      } else {
        if (statusEl) {
          statusEl.textContent = "NO DATA";
          statusEl.className = "subsystem-badge muted no-data";
        }
        if (detailEl) detailEl.textContent = "Awaiting validated reading";
        card.classList.add("no-data", "muted");
      }
      if (valueEl && tempDisplay) valueEl.textContent = tempDisplay;
    } else {
      // POWER, COMMS, ADCS, PROPULSION, PAYLOAD
      if (statusEl) {
        statusEl.textContent = "NO DATA";
        statusEl.className = "subsystem-badge muted no-data";
      }
      if (detailEl) detailEl.textContent = "Channel unconfigured";
      card.classList.remove("nominal", "anomaly", "has-anomaly", "active");
      card.classList.add("no-data", "muted");
      if (valueEl) valueEl.textContent = "—";
    }
  });

  // Direct ID fallback for subsystem status elements
  const thermalStatus = $("subsystem-thermal-status") || $("thermal-subsystem-status");
  if (thermalStatus) {
    if (hasIncident) {
      thermalStatus.textContent = "ANOMALY";
      thermalStatus.className = "subsystem-status anomaly warning";
    } else if (tempValid) {
      thermalStatus.textContent = `ACTIVE (${tempDisplay})`;
      thermalStatus.className = "subsystem-status nominal active";
    } else {
      thermalStatus.textContent = "NO DATA";
      thermalStatus.className = "subsystem-status muted no-data";
    }
  }
  ["power", "comms", "adcs", "propulsion", "payload"].forEach((sub) => {
    const el = $(`subsystem-${sub}-status`) || $(`${sub}-subsystem-status`);
    if (el) {
      el.textContent = "NO DATA";
      el.className = "subsystem-status muted no-data";
    }
  });
}

/**
 * Updates session view indicators, totals, and integrity checks.
 */
function renderSession(data) {
  const logging = Boolean(data.logging);
  $("session-indicator").textContent = logging ? "LOGGING" : "IDLE";
  $("session-indicator").classList.toggle("active", logging);
  $("session-status").textContent = `${data.status}${logging ? " · logging" : ""}`;
  $("session-page-duration").textContent = duration(data.stats.session_duration_s);
  $("session-total-records").textContent = data.stats.total_records;
  $("session-valid-records").textContent = data.stats.valid_records;
  $("session-start").disabled = logging || data.status !== "connected";
  $("session-start").title = logging ? "Logging is already active" : (data.status !== "connected" ? "Connect to a device before starting logging" : "Start a new logging session");
  $("session-stop").disabled = !logging;
  $("session-stop").title = logging ? "Stop the active logging session" : "No logging session is active";
  const checks = [["Validated records", data.stats.valid_records], ["Invalid records", data.stats.invalid_records], ["Sequence anomalies", data.stats.sequence_anomalies], ["Data gaps", data.stats.data_gaps]];
  $("session-integrity").innerHTML = checks.map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
}

/**
 * Updates incident investigation view, evidence lists, and event timeline.
 */
function renderIncident(incident) {
  const empty = $("incident-empty");
  const details = $("incident-details");
  const download = $("evidence-download");
  const timelineEl = document.querySelector ? (document.querySelector(".event-timeline") || $("event-timeline")) : $("event-timeline");

  if (!incident || !incident.incident_id) {
    if (empty) empty.hidden = false;
    if (details) details.hidden = true;
    if (download) download.disabled = true;
    if (timelineEl) timelineEl.innerHTML = "";
    return;
  }

  if (empty) empty.hidden = true;
  if (details) details.hidden = false;
  if (download) download.disabled = false;

  $("incident-id").textContent = incident.incident_id;
  $("incident-classification").textContent = incident.classification;
  $("incident-onset").textContent = `${incident.onset_device_time_ms} ms`;
  $("incident-threshold").textContent = `${incident.detector.threshold_c} °C`;
  $("incident-config").innerHTML = `<div><span>Detector</span><strong>${escapeHtml(incident.detector.id)} v${escapeHtml(incident.detector.version)}</strong></div><div><span>Rule</span><strong>${escapeHtml(incident.detector.rule)}</strong></div><div><span>Baseline median</span><strong>${escapeHtml(incident.baseline_median_c)} °C</strong></div>`;
  $("incident-channels").innerHTML = incident.affected_channels.map(channel => `<div><span>Channel</span><strong>${escapeHtml(channel)}</strong></div>`).join("");
  $("incident-records").innerHTML = incident.record_refs.map(record => `<div class="incident-record"><span>seq ${escapeHtml(record.seq)} · ${escapeHtml(record.device_time_ms)} ms</span><strong>${escapeHtml(record.temperature_c)} °C</strong></div>`).join("");

  // Event timeline rendering if container exists
  if (timelineEl) {
    const baselineRecords = incident.baseline_record_refs || [];
    const eventRecords = incident.record_refs || [];
    const allRecords = [...baselineRecords, ...eventRecords];

    if (allRecords.length > 0) {
      const times = allRecords.map(r => r.device_time_ms).filter(t => typeof t === "number");
      const minTime = Math.min(...times);
      const maxTime = Math.max(...times);
      const timeSpan = Math.max(maxTime - minTime, 1);

      const onsetMs = incident.onset_device_time_ms;
      const endMs = incident.end_device_time_ms || onsetMs;

      const onsetPct = Math.max(0, Math.min(100, ((onsetMs - minTime) / timeSpan) * 100));
      const endPct = Math.max(onsetPct, Math.min(100, ((endMs - minTime) / timeSpan) * 100));
      const windowWidth = Math.max(4, endPct - onsetPct);

      const dotsHtml = allRecords.map((r) => {
        const pct = Math.max(0, Math.min(100, ((r.device_time_ms - minTime) / timeSpan) * 100));
        const isAnomaly = eventRecords.some(ev => ev.seq === r.seq);
        const dotColor = isAnomaly ? "#ff5c67" : "#55aaf5";
        return `<div class="timeline-dot ${isAnomaly ? "anomaly-dot" : "baseline-dot"}" style="position:absolute;left:${pct}%;top:50%;transform:translate(-50%,-50%);width:10px;height:10px;border-radius:50%;background:${dotColor};border:2px solid #0c1a29;z-index:3;" title="seq ${escapeHtml(r.seq)} · ${escapeHtml(r.device_time_ms)}ms · ${escapeHtml(r.temperature_c)}°C"></div>`;
      }).join("");

      timelineEl.innerHTML = `
        <div class="timeline-wrapper" style="position:relative;padding:24px 10px 30px;margin-top:12px;">
          <div class="timeline-track" style="position:relative;height:6px;background:#183047;border-radius:3px;">
            <div class="timeline-event-window" style="position:absolute;left:${onsetPct}%;width:${windowWidth}%;height:100%;background:rgba(242, 189, 98, 0.4);border:1px solid #f2bd62;border-radius:3px;box-shadow:0 0 8px rgba(242,189,98,0.3);z-index:2;"></div>
            ${dotsHtml}
          </div>
          <div class="timeline-marker onset-marker" style="position:absolute;left:${onsetPct}%;top:0;transform:translateX(-50%);font-size:10px;color:#f2bd62;font-weight:600;white-space:nowrap;letter-spacing:0.5px;">ONSET (${onsetMs}ms)</div>
          <div class="timeline-marker end-marker" style="position:absolute;left:${endPct}%;bottom:6px;transform:translateX(-50%);font-size:10px;color:#ff5c67;font-weight:600;white-space:nowrap;letter-spacing:0.5px;">END (${endMs}ms)</div>
          <div class="timeline-time-min" style="position:absolute;left:0;bottom:6px;font-size:10px;color:#8094a8;">${minTime}ms</div>
          <div class="timeline-time-max" style="position:absolute;right:0;bottom:6px;font-size:10px;color:#8094a8;">${maxTime}ms</div>
        </div>
      `;
    }
  }
}

function drawAutonomyChart(report) {
  const canvas = $("autonomy-voltage-chart");
  if (!canvas || !report) return;
  const points = (report.telemetry_records || []).filter(record => typeof record.voltage_v === "number");
  if (!points.length) return;
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 640;
  const height = canvas.clientHeight || 220;
  canvas.width = width * dpr;
  canvas.height = height * dpr;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);
  const left = 46, right = 16, top = 16, bottom = 30;
  const values = points.map(point => point.voltage_v);
  const config = report.configuration;
  const min = Math.min(3.0, ...values, config.critical_voltage_v - 0.1);
  const max = Math.max(4.0, ...values, config.warning_voltage_v + 0.1);
  const x = index => left + (index / Math.max(points.length - 1, 1)) * (width - left - right);
  const y = value => height - bottom - ((value - min) / (max - min)) * (height - top - bottom);

  ctx.strokeStyle = "#24384d";
  ctx.lineWidth = 1;
  [min, (min + max) / 2, max].forEach(value => {
    ctx.beginPath(); ctx.moveTo(left, y(value)); ctx.lineTo(width - right, y(value)); ctx.stroke();
    ctx.fillStyle = "#70849b"; ctx.font = "10px Segoe UI, sans-serif"; ctx.fillText(`${value.toFixed(2)} V`, 4, y(value) + 3);
  });
  [[config.warning_voltage_v, "#f2b94b", "WARNING"], [config.critical_voltage_v, "#ff646f", "CRITICAL"], [config.recovery_voltage_v, "#54c99a", "RECOVERY"]].forEach(([value, color, label]) => {
    ctx.setLineDash([5, 4]); ctx.strokeStyle = color; ctx.beginPath(); ctx.moveTo(left, y(value)); ctx.lineTo(width - right, y(value)); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = color; ctx.font = "10px Segoe UI, sans-serif"; ctx.fillText(label, width - right - 58, y(value) - 4);
  });
  ctx.strokeStyle = "#63c9d8";
  ctx.lineWidth = 2;
  ctx.beginPath();
  points.forEach((point, index) => index ? ctx.lineTo(x(index), y(point.voltage_v)) : ctx.moveTo(x(index), y(point.voltage_v)));
  ctx.stroke();
  points.forEach((point, index) => {
    ctx.fillStyle = point.voltage_v <= config.critical_voltage_v ? "#ff646f" : "#63c9d8";
    ctx.beginPath(); ctx.arc(x(index), y(point.voltage_v), 3, 0, Math.PI * 2); ctx.fill();
  });
  ctx.fillStyle = "#70849b"; ctx.font = "10px Segoe UI, sans-serif";
  ctx.fillText("device time", width / 2 - 22, height - 8);
}

function renderAutonomy(data) {
  const report = data.autonomy;
  const empty = $("autonomy-empty");
  const details = $("autonomy-details");
  const status = $("autonomy-status");
  const download = $("autonomy-evidence-download");
  const reset = $("autonomy-reset");
  if (!empty || !details) return;
  if (!report) {
    empty.hidden = false;
    details.hidden = true;
    if (status) status.textContent = "No scenario run";
    if (download) download.disabled = true;
    if (reset) reset.disabled = true;
    return;
  }

  empty.hidden = true;
  details.hidden = false;
  if (status) status.textContent = `${report.scenario_id} · ${report.final_outcome.state}`;
  if (download) download.disabled = false;
  if (reset) reset.disabled = false;
  $("autonomy-scenario").textContent = report.scenario_id;
  $("autonomy-final-state").textContent = report.final_outcome.state;
  $("autonomy-outcome").textContent = report.final_outcome.success ? "RECOVERED" : "ESCALATED";
  $("autonomy-record-count").textContent = report.validation ? report.validation.accepted_records : report.telemetry_records.length;

  const config = report.configuration;
  $("autonomy-configuration").innerHTML = [
    ["Warning", `${config.warning_voltage_v.toFixed(2)} V`],
    ["Critical", `${config.critical_voltage_v.toFixed(2)} V`],
    ["Recovery criterion", `${config.recovery_voltage_v.toFixed(2)} V × ${config.required_consecutive_verified_samples}`],
    ["Action", `${config.action_id} · simulated`]
  ].map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");

  const trigger = report.trigger;
  $("autonomy-trigger").innerHTML = trigger ? [
    ["Trigger", `seq ${trigger.seq} · ${trigger.device_time_ms} ms`],
    ["Voltage", `${Number(trigger.voltage_v).toFixed(2)} V`],
    ["Decision", report.policy_decision.reason]
  ].map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("") : '<div><span>Trigger</span><strong>None observed</strong></div>';

  const action = report.action;
  $("autonomy-action").innerHTML = [
    ["Status", action.issued ? "Issued · simulated" : "Not issued"],
    ["Action ID", action.id],
    ["Hardware command", "None"],
    ["Description", action.description || "No action recorded"]
  ].map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");

  const verification = report.verification;
  $("autonomy-verification").innerHTML = [
    ["Criteria", verification.criteria],
    ["Verified samples", verification.consecutive_recovery_samples],
    ["Criteria met", verification.criteria_met ? "YES" : "NO"],
    ["Final reason", report.final_outcome.reason]
  ].map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");

  $("autonomy-state-history").innerHTML = report.state_history.map(item => `<li class="${escapeHtml(item.state.toLowerCase())}"><strong>${escapeHtml(item.state)}</strong><span>${escapeHtml(item.reason)}</span></li>`).join("");
  drawAutonomyChart(report);
  const metrics = report.execution_metrics || {};
  $("autonomy-runtime").innerHTML = [
    ["Measured execution", `${metrics.execution_time_ms ?? "—"} ms`],
    ["Peak traced memory", `${metrics.peak_traced_memory_bytes ?? "—"} bytes`],
    ["Records processed", metrics.records_processed ?? "—"],
    ["Verification samples", metrics.verification_samples_used ?? "—"],
    ["Evidence ID", metrics.evidence_id ?? "—"]
  ].map(([label, value]) => `<span><b>${escapeHtml(label)}</b> ${escapeHtml(value)}</span>`).join("");
}

/**
 * Updates replay controls and progress indicators.
 */
function renderReplay(data) {
  const replay = data.replay;
  $("source-label").textContent = data.source_type === "none" ? "No source selected" : data.source_type.replaceAll("_", " ").toUpperCase();
  const progressBar = $("replay-progress-bar");

  if (!replay) {
    $("replay-progress").textContent = "No replay loaded";
    $("replay-pause").disabled = true;
    $("replay-reset").disabled = true;
    if (progressBar) progressBar.value = 0;
    return;
  }

  $("replay-progress").textContent = `${replay.index}/${replay.total} frames · ${Math.round(replay.progress * 100)}%`;
  $("replay-play").disabled = replay.state === "playing";
  $("replay-pause").disabled = replay.state !== "playing";
  $("replay-reset").disabled = false;

  if (progressBar) {
    progressBar.value = Math.round(replay.progress * 100);
    if (progressBar.max) progressBar.max = 100;
  }
}

/**
 * Updates connect and disconnect button availability.
 */
function updateConnectionControls() {
  const status = state.last ? state.last.status : "disconnected";
  const selectedPort = $("port-select").value || $("settings-port-select").value;
  $("connect").disabled = status === "connected" || !selectedPort;
  $("connect").title = status === "connected" ? "Already connected" : (selectedPort ? "Connect to the selected serial port" : "Select a serial port first");
  $("disconnect").disabled = status !== "connected" && status !== "error";
  $("disconnect").title = $("disconnect").disabled ? "No active connection to disconnect" : "Disconnect and preserve the partial session";
}

/**
 * Main dashboard render pipeline.
 */
function render(data) {
  state.last = data;
  renderNav();

  const status = $("connection-status");
  status.className = `connection-status ${data.status}`;
  status.querySelector("strong").textContent = data.status[0].toUpperCase() + data.status.slice(1);
  status.querySelector("small").textContent = data.status_detail;

  updateConnectionControls();
  $("last-message").textContent = ageLabel(data.last_message_age_s);
  const quality = data.telemetry_quality || {state: "no_data", reason: "No telemetry quality reported"};
  const qualityLabel = $("telemetry-quality");
  if (qualityLabel) {
    qualityLabel.textContent = quality.state.replaceAll("_", " ").toUpperCase();
    qualityLabel.className = `quality-label ${quality.state}`;
    qualityLabel.title = quality.reason || "";
  }
  $("uptime").textContent = duration(data.uptime_s);

  const records = data.records || [];
  const latest = records[0];
  const displayed = visibleRecords(data);

  $("temperature-value").innerHTML = `${escapeHtml(value(latest, "temperature_c"))} <i>°C</i>`;
  $("temperature-time").textContent = latest ? latest.host_received_utc : "—";
  $("humidity-value").innerHTML = `${escapeHtml(value(latest, "humidity_pct"))} <i>%</i>`;
  $("humidity-time").textContent = latest && latest.humidity_pct !== undefined ? latest.host_received_utc : "—";
  $("pressure-value").innerHTML = `${escapeHtml(value(latest, "pressure_hpa"))} <i>hPa</i>`;
  $("pressure-time").textContent = latest && latest.pressure_hpa !== undefined ? latest.host_received_utc : "—";

  const stats = data.stats;
  $("valid-records").textContent = stats.valid_records;
  $("invalid-records").textContent = stats.invalid_records;
  $("sequence-errors").textContent = stats.sequence_anomalies;
  $("data-gaps").textContent = stats.data_gaps;
  $("session-duration").textContent = duration(stats.session_duration_s);
  $("total-records").textContent = stats.total_records;

  $("start-logging").disabled = data.logging || data.status !== "connected";
  $("start-logging").title = data.logging ? "Logging is already active" : (data.status !== "connected" ? "Connect to a device before starting logging" : "Start a new logging session");
  $("stop-logging").disabled = !data.logging;
  $("stop-logging").title = data.logging ? "Stop the active logging session" : "No logging session is active";

  const canDownload = stats.logged_records > 0;
  $("download").disabled = !canDownload;
  $("session-download").disabled = !canDownload;
  $("download").title = canDownload ? "Download captured JSONL records" : "No captured records to export";
  $("session-download").title = $("download").title;

  $("clear-records").disabled = !records.length;
  $("clear-records").title = records.length ? "Hide records from the display only" : "No records are currently displayed";
  $("log-clear").disabled = !records.length;
  $("log-clear").title = records.length ? "Hide records from the display only" : "No records are currently displayed";

  renderTable(displayed, "records-body", "No telemetry data in the current display.<br><small>Clearing the display does not delete the source log.</small>", 7);
  renderTable(displayed, "log-records-body", "No telemetry records in the current display.", 7);

  const points = (data.chart || []).slice(-state.chartWindow);
  drawChart("temperature-chart", "temperature-empty", points, "temperature_c", "#ff5c67", "°C");
  drawChart("humidity-chart", "humidity-empty", points, "humidity_pct", "#55aaf5", "%");
  drawChart("pressure-chart", "pressure-empty", points, "pressure_hpa", "#83db9b", "hPa");

  $("messages-list").innerHTML = (data.messages || []).slice(-8).map(m => `<div class="message ${escapeHtml(m.level)}">[${escapeHtml(m.level.toUpperCase())} ${escapeHtml(m.time)}] ${escapeHtml(m.text)}</div>`).join("") || '<div class="message info">[INFO] Dashboard initialized.</div>';

  renderSubsystems(data);
  renderSession(data);
  renderReplay(data);
  renderIncident(data.incident);
  renderAutonomy(data);
}

/**
 * Selects and activates a primary navigation view.
 */
function selectView(view) {
  if (!document.getElementById(view)) view = "dashboard-view";
  state.activeView = view;
  window.location.hash = view;
  renderNav();
}

/**
 * Fetches dashboard state from /api/state with HTTP validation.
 */
async function refresh() {
  try {
    const response = await fetch("/api/state", {cache: "no-store"});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    render(data);
  } catch (_) {
    if ($("messages-list")) {
      $("messages-list").innerHTML = '<div class="message error">[ERROR] Dashboard service unavailable</div>';
    }
  }
}

/**
 * Fetches serial ports from /api/ports with HTTP validation.
 */
async function refreshPorts() {
  try {
    const response = await fetch("/api/ports", {cache: "no-store"});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    renderPorts(data.ports);
    updateConnectionControls();
  } catch (_) {
    if ($("messages-list")) {
      $("messages-list").innerHTML = '<div class="message error">[ERROR] Could not refresh serial ports</div>';
    }
  }
}

/**
 * Starts a telemetry capture session.
 */
async function startLogging() {
  try {
    await post("/api/session/start");
    showNotification("Telemetry logging started", "info");
  } catch (error) {
    showNotification(error.message, "error");
  }
  await refresh();
}

/**
 * Stops the active telemetry capture session.
 */
async function stopLogging() {
  try {
    await post("/api/session/stop");
    showNotification("Telemetry logging stopped", "info");
  } catch (error) {
    showNotification(error.message, "error");
  }
  await refresh();
}

/**
 * Dispatches a replay control POST request.
 */
async function replayAction(path, body = {}) {
  try {
    await post(path, body);
  } catch (error) {
    showNotification(error.message, "error");
  }
  await refresh();
}

/**
 * Exports verified incident evidence JSON blob with data integrity check.
 */
async function downloadEvidence() {
  try {
    const response = await fetch("/api/evidence/export", {cache: "no-store"});
    const text = await response.text();
    if (!response.ok) throw new Error("Evidence export failed");
    const exported = JSON.parse(text);
    if (!state.last || JSON.stringify(exported) !== JSON.stringify(state.last.incident)) {
      throw new Error("Evidence changed; refresh the incident before downloading");
    }
    const incidentId = String(exported.incident_id || "evidence").replace(/[^a-zA-Z0-9_-]/g, "_");
    const blob = new Blob([text], {type: "application/json;charset=utf-8"});
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = `SATSentinelX_Incident_${incidentId}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
  } catch (error) {
    const message = `[ERROR] Evidence download failed: ${error.message}`;
    if ($("messages-list")) $("messages-list").innerHTML = `<div class="message error">${escapeHtml(message)}</div>`;
  }
}

async function downloadAutonomyEvidence() {
  try {
    const response = await fetch("/api/autonomy/evidence/export", {cache: "no-store"});
    const text = await response.text();
    if (!response.ok) throw new Error("Autonomy evidence export failed");
    const exported = JSON.parse(text);
    if (!state.last || JSON.stringify(exported) !== JSON.stringify(state.last.autonomy)) {
      throw new Error("Autonomy evidence changed; refresh the scenario before downloading");
    }
    const scenario = String(exported.scenario_id || "scenario").replace(/[^a-zA-Z0-9_-]/g, "_");
    const objectUrl = URL.createObjectURL(new Blob([text], {type: "application/json;charset=utf-8"}));
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = `SATSentinelX_Autonomy_${scenario}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 0);
  } catch (error) {
    showNotification(`Autonomy evidence download failed: ${error.message}`, "error");
  }
}

/**
 * Clears telemetry records from display only without deleting server logs.
 */
function clearDisplay() {
  if (state.last) {
    (state.last.records || []).forEach(record => state.hiddenRecordKeys.add(recordKey(record)));
    render(state.last);
  }
}

// Navigation event bindings
document.querySelectorAll(".nav-item").forEach(item => item.addEventListener("click", () => selectView(item.dataset.view)));
window.addEventListener("hashchange", () => selectView(window.location.hash.slice(1)));

// Port control bindings
$("refresh-ports").onclick = refreshPorts;
$("settings-refresh-ports").onclick = refreshPorts;
$("port-select").onchange = updateConnectionControls;

// Connect and disconnect bindings
$("connect").onclick = async () => {
  const port = $("port-select").value || $("settings-port-select").value;
  if (!port) {
    showNotification("Select a serial port first.", "warning");
    return;
  }
  try {
    await post("/api/connect", {port});
    showNotification(`Connected to ${port}`, "info");
  } catch (error) {
    showNotification(error.message, "error");
  }
  await refresh();
};

$("disconnect").onclick = async () => {
  try {
    await post("/api/disconnect");
    showNotification("Disconnected; partial session preserved", "info");
  } catch (error) {
    showNotification(error.message, "error");
  }
  await refresh();
};

// Logging control bindings
$("start-logging").onclick = startLogging;
$("session-start").onclick = startLogging;
$("stop-logging").onclick = stopLogging;
$("session-stop").onclick = stopLogging;

// Session download bindings
$("download").onclick = () => { window.location.href = "/api/session/export"; };
$("session-download").onclick = () => { window.location.href = "/api/session/export"; };

// Replay control bindings
$("replay-play").onclick = () => replayAction("/api/replay/start", {source: $("replay-source").value, speed: Number($("replay-speed").value)});
$("replay-pause").onclick = () => replayAction("/api/replay/pause");
$("replay-reset").onclick = () => replayAction("/api/replay/reset");
$("replay-speed").onchange = (event) => { if (state.last && state.last.replay) replayAction("/api/replay/speed", {speed: Number(event.target.value)}); };

// Evidence export binding
$("evidence-download").onclick = downloadEvidence;
if ($("autonomy-evidence-download")) $("autonomy-evidence-download").onclick = downloadAutonomyEvidence;

if ($("autonomy-run-success")) $("autonomy-run-success").onclick = async () => {
  try { await post("/api/autonomy/run", {scenario: "recovery_success"}); showNotification("Synthetic recovery-success scenario complete", "info"); }
  catch (error) { showNotification(error.message, "error"); }
  await refresh();
};
if ($("autonomy-run-failure")) $("autonomy-run-failure").onclick = async () => {
  try { await post("/api/autonomy/run", {scenario: "recovery_failure"}); showNotification("Synthetic failed-recovery scenario complete", "warning"); }
  catch (error) { showNotification(error.message, "error"); }
  await refresh();
};
if ($("autonomy-reset")) $("autonomy-reset").onclick = async () => {
  try { await post("/api/autonomy/reset"); showNotification("Synthetic autonomy demonstrator reset", "info"); }
  catch (error) { showNotification(error.message, "error"); }
  await refresh();
};

// Clear display bindings
$("clear-records").onclick = clearDisplay;
$("log-clear").onclick = clearDisplay;

// Settings and preference bindings
$("chart-window").value = String(state.chartWindow);
$("chart-window").onchange = (event) => {
  state.chartWindow = Number(event.target.value);
  localStorage.setItem("satsentinel.chartWindow", state.chartWindow);
  if (state.last) render(state.last);
};

$("auto-refresh").checked = state.autoRefresh;
$("auto-refresh").onchange = (event) => {
  state.autoRefresh = event.target.checked;
  localStorage.setItem("satsentinel.autoRefresh", String(state.autoRefresh));
};

$("settings-port-select").onchange = (event) => {
  $("port-select").value = event.target.value;
  updateConnectionControls();
};

// Application initialization
selectView(state.activeView);
refreshPorts();
refresh();
setInterval(() => { if (state.autoRefresh) refresh(); }, 750);
setInterval(refreshPorts, 5000);
window.addEventListener("resize", () => { if (state.last) render(state.last); });
