"use strict";
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const state = { user: null, analysis: null, selectedFile: null, scanning: false, cameraRunning: false,
  stream: null, timer: null, history: [], tasks: [], layout: { zones: [] }, next: null, source: "upload", refresh: 0 };
const escapeHtml = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const icons = () => window.lucide?.createIcons();
const level = (s) => /critical/i.test(s) ? "danger" : /low/i.test(s) ? "warn" : "good";
const date = (t) => new Date(t * 1000).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
const empty = (text) => `<div class="empty-row">${escapeHtml(text)}</div>`;
const descriptions = { dashboard: "Shelf availability, evidence, and action.", monitor: "Current camera observations and detection quality.",
  analysis: "Zone performance and scan comparison.", alerts: "Ownership, progress, and replenishment records.",
  inventory: "Expected facings, product assignments, and shelf zones.", reports: "Availability history and operational reports.", admin: "People, camera connections, and system status." };
function notice(message, type = "") {
  $("#fileName").textContent = message;
  if (!type && ["Complete", "Saved scan"].includes($("#scanState").textContent)) type = "success";
  $("#scanNotice").className = `scan-notice ${type}`;
  $("#noticeIcon").innerHTML = `<i data-lucide="${({error:"circle-alert", loading:"loader-circle", success:"circle-check"})[type] || "info"}"></i>`;
  icons();
}
let toastTimer;
function toast(message) {
  $("#toast").textContent = message; $("#toast").hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { $("#toast").hidden = true; }, 5000);
}
async function api(path, options = {}) {
  const response = await fetch(path, { ...options, credentials: "same-origin", cache: "no-store" });
  if (response.status === 401) {
    stopCamera(); if (!$("#loginDialog").open) $("#loginDialog").showModal();
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === "string" ? body.detail : body.detail?.map((e) => e.msg).join("; ") || `Request failed (${response.status})`);
  }
  return response.json();
}
const jsonRequest = (method, data) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
function setPage(page) {
  hideProductTooltip();
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `${page}View`));
  $$("[data-page]").forEach((b) => { b.classList.toggle("active", b.dataset.page === page); b.setAttribute("aria-current", b.dataset.page === page ? "page" : "false"); });
  $("#pageTitle").textContent = $(`[data-page="${page}"]`).dataset.title;
  $("#pageDescription").textContent = descriptions[page];
  if (page !== "monitor") stopCamera();
  window.scrollTo({ top: 0, behavior: "smooth" });
}
function tuning() {
  const f = $("#tuningForm").elements;
  return { confidence: +f.confidence.value, iou: +f.iou.value, image_size: +f.image_size.value,
    max_detections: +f.max_detections.value, min_area: +f.min_area.value, contrast: f.contrast.checked };
}
function tuningChanged() {
  const t = tuning();
  $("#confidenceOutput").textContent = `${Math.round(t.confidence*100)}%`;
  $("#iouOutput").textContent = `${Math.round(t.iou*100)}%`;
  $("#tuningState").textContent = "Pending settings / next scan";
}
function renderShelf(target, analysis, interactive = false) {
  hideProductTooltip();
  if (!analysis?.image) { target.innerHTML = '<div class="inspection-empty"><i data-lucide="scan-line"></i><strong>No image selected</strong><span>Awaiting inspection</span></div>'; target.className = "shelf-wrap empty-visual"; target.style.removeProperty("aspect-ratio"); icons(); return; }
  const ratio = `${analysis.quality.width} / ${analysis.quality.height}`;
  target.className = "shelf-wrap has-scan"; target.style.aspectRatio = ratio;
  const boxes = $("#showBoxes").checked;
  const zones = $("#showZones").checked;
  const heat = $("#showHeatmap").checked;
  const filter = $("#classFilter").value;
  const style = (b) => `left:${b[0]}%;top:${b[1]}%;width:${b[2]-b[0]}%;height:${b[3]-b[1]}%`;
  target.innerHTML = `<img class="scan-image" src="${escapeHtml(analysis.image)}" alt="Shelf scan ${analysis.id}" loading="lazy"><div class="detection-layer">` +
    (zones || heat ? analysis.zones.map((z) => `<button type="button" class="zone-overlay ${level(z.status)} ${heat ? "heat" : ""}" style="${style(z.bbox)}" data-zone="${escapeHtml(z.id)}" aria-label="${escapeHtml(z.name)}: ${z.occupancy}% available"><span class="zone-label">${escapeHtml(z.id)}</span></button>`).join("") : "") +
    (boxes ? analysis.detections.filter((b) => !filter || b.label === filter).map((b) => `<button type="button" class="product-box" style="${style(b.bbox)}" data-confidence="${(b.confidence*100).toFixed(1)}" data-product="${escapeHtml(b.label)}" aria-label="${escapeHtml(b.label)}: ${(b.confidence*100).toFixed(1)}% detection confidence"></button>`).join("") : "") + '</div>';
  if (interactive) target.querySelector(".detection-layer").style.clipPath = `inset(0 ${100-Number($("#overlayReveal").value)}% 0 0)`;
  target.querySelectorAll(".product-box").forEach((box) => {
    box.addEventListener("pointerenter", () => showProductTooltip(box));
    box.addEventListener("focus", () => showProductTooltip(box));
    box.addEventListener("click", () => showProductTooltip(box));
    box.addEventListener("pointerleave", hideProductTooltip);
    box.addEventListener("blur", hideProductTooltip);
  });
  if (interactive) target.querySelectorAll("[data-zone]").forEach((button) => button.addEventListener("click", () => {
    const z = analysis.zones.find((item) => item.id === button.dataset.zone);
    $("#selectedZone").textContent = `${z.name}: ${z.detected_count} / ${z.expected_count} items, ${z.missing_count} missing, ${z.status}`;
    target.querySelectorAll(".zone-overlay").forEach((b) => b.classList.toggle("selected", b === button));
  }));
}
function hideProductTooltip() {
  $("#productTooltip").hidden = true;
  document.querySelectorAll('.product-box[aria-describedby]').forEach((box) => box.removeAttribute("aria-describedby"));
}
function showProductTooltip(box) {
  const tooltip = $("#productTooltip");
  tooltip.textContent = `${box.dataset.product} / ${box.dataset.confidence}% confidence`;
  if (box.closest("#analysisShelf")) $("#selectedZone").textContent = tooltip.textContent;
  box.setAttribute("aria-describedby", "productTooltip");
  tooltip.hidden = false;
  const rect = box.getBoundingClientRect(), size = tooltip.getBoundingClientRect();
  tooltip.style.left = `${Math.max(8, Math.min(innerWidth-size.width-8, rect.left+rect.width/2-size.width/2))}px`;
  tooltip.style.top = `${Math.max(8, Math.min(innerHeight-size.height-8, rect.top-size.height-8 > 8 ? rect.top-size.height-8 : rect.bottom+8))}px`;
}
function repositionProductTooltip() {
  const focused = document.activeElement;
  if (focused?.classList.contains("product-box")) showProductTooltip(focused);
  else hideProductTooltip();
}
window.addEventListener("scroll", repositionProductTooltip, {passive:true});
window.addEventListener("resize", repositionProductTooltip);
document.addEventListener("keydown", (e) => { if(e.key === "Escape") hideProductTooltip(); });
function renderAnalysis(analysis) {
  state.analysis = analysis;
  $("#overlayReveal").disabled = false;
  const detections = analysis.detections;
  const confidence = detections.length ? detections.reduce((s, d) => s+d.confidence, 0)/detections.length : null;
  $("#occupancyValue").textContent = `${analysis.occupancy}%`;
  $("#detectedValue").textContent = analysis.detected_items;
  $("#expectedValue").textContent = `${analysis.matched_items} matched / ${analysis.expected_items} expected`;
  $("#gapValue").textContent = analysis.missing_items;
  $("#alertValue").textContent = `${analysis.alerts.length} zones need attention`;
  $("#statusBadge").textContent = analysis.status;
  $("#statusBadge").className = `status-text ${level(analysis.status)}`;
  $("#lastScanTime").textContent = date(analysis.created_at);
  $("#analysisExpected").textContent = analysis.expected_items;
  $("#analysisDetected").textContent = analysis.matched_items;
  $("#analysisUnassigned").textContent = analysis.unassigned_items;
  $("#analysisConfidence").textContent = confidence === null ? "--" : `${Math.round(confidence*100)}%`;
  $("#monitorMode").textContent = `Scan #${analysis.id} / ${analysis.inference_ms} ms`;
  $("#chartAverage").textContent = `${analysis.occupancy}% weighted`;
  $("#trendBars").innerHTML = analysis.zones.map((z) => `<div class="zone-bar"><span>${escapeHtml(z.id)}</span><div class="zone-track"><i class="${level(z.status)}" style="width:${z.occupancy}%"></i></div><strong>${z.occupancy}%</strong></div>`).join("");
  const previousFilter = $("#classFilter").value;
  const labels = [...new Set(detections.map((d) => d.label))];
  $("#classFilter").innerHTML = '<option value="">All classes</option>' + labels.map((l) => `<option value="${escapeHtml(l)}">${escapeHtml(l)}</option>`).join("");
  if (labels.includes(previousFilter)) $("#classFilter").value = previousFilter;
  $("#classCatalog").innerHTML = labels.map((l) => `<div><span>${escapeHtml(l)}</span><b>Detected class</b></div>`).join("");
  $("#overviewQuality").textContent = analysis.quality.warnings.join(" ") || "Image checks passed; verify shelf counts before action.";
  const lowConfidence = detections.filter((d) => d.confidence < .5).length;
  $("#qualityPanel").innerHTML = `<h3>Scan quality</h3><dl><dt>Below 50% confidence</dt><dd>${lowConfidence}</dd><dt>Sharpness score</dt><dd>${analysis.quality.sharpness}</dd><dt>Brightness / 255</dt><dd>${analysis.quality.brightness}</dd><dt>Inference threshold</dt><dd>${Math.round(analysis.tuning.confidence*100)}%</dd><dt>Outside zones</dt><dd>${analysis.unassigned_items}</dd></dl>` + analysis.quality.warnings.map((w) => `<p class="quality-warning">${escapeHtml(w)}</p>`).join("");
  $("#tuningState").textContent = JSON.stringify(tuning()) === JSON.stringify(analysis.tuning) ? "Settings match displayed scan" : "Displayed scan uses saved settings";
  renderShelf($("#monitorShelf"), analysis);
  renderShelf($("#analysisShelf"), analysis, true);
  renderZoneTable(); icons();
}
function renderZoneTable() {
  const search = $("#zoneSearch").value.toLowerCase(); const status = $("#zoneStatus").value;
  const zones = (state.analysis?.zones || []).filter((z) => `${z.id} ${z.name}`.toLowerCase().includes(search) && (!status || z.status === status));
  $("#zoneTable").innerHTML = zones.length ? zones.map((z) => `<tr><td><strong>${escapeHtml(z.name)}</strong><small>${escapeHtml(z.id)}</small></td><td>${z.detected_count}</td><td>${z.expected_count}</td><td>${z.missing_count}</td><td>${z.occupancy}%</td><td><span class="status-pill ${level(z.status)}">${escapeHtml(z.status)}</span></td></tr>`).join("") : '<tr><td colspan="6" class="table-empty">No matching zone results</td></tr>';
}
async function analyze(file, camera = state.source) {
  if (state.scanning || !file) return;
  if (!$("#tuningForm").reportValidity()) return;
  if (file.size > 12*1024*1024) { notice("Image exceeds 12 MB. Resize it and retry.", "error"); return; }
  const body = new FormData(); body.append("file", file); body.append("camera", camera); body.append("tuning", JSON.stringify(tuning()));
  return runScan(() => api("/api/analyze", { method: "POST", body }));
}
async function runScan(run) {
  if (state.scanning) return;
  state.scanning = true; $("#scanButton").disabled = true;
  $("#scanState").textContent = "Processing"; notice("Analyzing shelf image", "loading");
  try {
    const result = await run();
    renderAnalysis(result); $("#scanState").textContent = result.duplicate ? "Saved scan" : "Complete";
    notice(result.duplicate ? `Identical input / opened scan #${result.id}` : `${result.source} / scan #${result.id}`);
    $("#cameraStatus").textContent = state.cameraRunning ? `Last frame ${date(result.created_at)}` : "Stopped";
    await refreshData(false);
    return result;
  } catch (error) {
    $("#scanState").textContent = "Failed"; notice(error.message, "error");
    if (state.cameraRunning) { stopCamera(); $("#cameraStatus").textContent = error.message; }
  } finally {
    state.scanning = false; $("#scanButton").disabled = !state.selectedFile || state.user?.role === "viewer";
  }
}
function historyQuery() {
  return new URLSearchParams({camera: state.source, days: $("#reportDays").value,
    search: $("#historySearch").value, status: $("#historyStatus").value});
}
async function refreshData() {
  const requestId = ++state.refresh;
  const camera = encodeURIComponent(state.source);
  try {
    const [history, recent, taskData, analytics, timeline] = await Promise.all([
      api(`/api/history?${historyQuery()}`), api(`/api/history?camera=${camera}&days=365&limit=25`),
      api(`/api/tasks?camera=${camera}`), api(`/api/analytics?camera=${camera}&days=${$("#reportDays").value}`), api("/api/events")]);
    if (requestId !== state.refresh) return;
    state.history = history.history; state.next = history.next; state.tasks = taskData.tasks;
    renderHistory(); renderTasks(); renderReports(analytics);
    $("#eventTimeline").innerHTML = timeline.events.length ? timeline.events.map((e) => `<li><time>${date(e.created_at)}</time><div><strong>${escapeHtml(e.actor)}</strong><span>${escapeHtml(e.message)}</span></div></li>`).join("") : empty("No activity recorded");
    $("#historyList").innerHTML = recent.history.slice(0, 4).map((h) => `<button class="history-item history-open" data-scan="${h.id}"><i class="history-marker"></i><span><strong>${escapeHtml(h.source)}</strong><small>${date(h.created_at)}</small></span><b>${h.occupancy}%</b></button>`).join("") || empty("No scans for this source");
    for (const id of ["compareBefore", "compareAfter"]) {
      const old = $(`#${id}`).value;
      $(`#${id}`).innerHTML = recent.history.map((h) => `<option value="${h.id}">#${h.id} / ${escapeHtml(h.source)} / ${date(h.created_at)}</option>`).join("");
      if (recent.history.some((h) => String(h.id) === old)) $(`#${id}`).value = old;
    }
    if (recent.history.length > 1 && $("#compareBefore").value === $("#compareAfter").value) {
      $("#compareAfter").selectedIndex = 0;
      $("#compareBefore").selectedIndex = 1;
    }
    $("#compareButton").disabled = recent.history.length < 2;
    const previous = recent.history.find((h) => h.id < state.analysis?.id && h.baseline === state.analysis?.baseline);
    $("#changeValue").textContent = previous ? `${(state.analysis.occupancy - previous.occupancy).toFixed(1)} pp vs scan #${previous.id}` : "No comparable previous scan";
    icons();
  } catch (error) { notice(error.message, "error"); }
}
function clearAnalysis() {
  state.analysis = null;
  $("#overlayReveal").value = "100";
  $("#overlayReveal").disabled = true;
  $("#overlayRevealValue").textContent = "100%";
  for (const id of ["occupancyValue", "detectedValue", "gapValue", "statusBadge", "analysisExpected", "analysisDetected", "analysisUnassigned", "analysisConfidence"]) $(`#${id}`).textContent = "--";
  $("#trendBars").innerHTML = empty("Awaiting inspection"); $("#chartAverage").textContent = "--";
  $("#changeValue").textContent = "No scan selected";
  $("#statusBadge").className = "status-text";
  $("#lastScanTime").textContent = "Awaiting scan"; $("#expectedValue").textContent = "No scan yet"; $("#alertValue").textContent = "Awaiting scan";
  renderShelf($("#monitorShelf"), null); renderShelf($("#analysisShelf"), null); renderZoneTable();
  $("#qualityPanel").innerHTML = ""; $("#overviewQuality").textContent = "Awaiting image checks";
  $("#monitorMode").textContent = "No scan"; $("#selectedZone").textContent = "No product selected";
  $("#classFilter").innerHTML = '<option value="">All classes</option>';
  $("#comparisonSummary").textContent = "Choose two saved scans.";
  renderShelf($("#beforeImage"), null); renderShelf($("#afterImage"), null);
}
function renderHistory() {
  $("#historyTable").innerHTML = state.history.map((h) => `<tr><td><strong>${escapeHtml(h.source)}</strong><small>#${h.id} / ${escapeHtml(h.camera)}</small></td><td>${date(h.created_at)}</td><td>${h.occupancy}%</td><td><span class="status-pill ${level(h.status)}">${h.status}</span></td><td>${h.alerts}</td><td><button class="icon-button" data-scan="${h.id}" title="Open scan" aria-label="Open scan ${h.id}"><i data-lucide="arrow-up-right"></i></button></td></tr>`).join("") || '<tr><td colspan="6" class="table-empty">No matching scans</td></tr>';
  $("#moreHistory").hidden = !state.next; icons();
}
function renderReports(data) {
  const s = data.summary;
  $("#reportSummary").innerHTML = `<div><span>Scans in period</span><strong>${s.count}</strong></div><div><span>Mean availability</span><strong>${s.average === null ? "--" : s.average.toFixed(1)+"%"}</strong></div><div><span>Zone alert observations</span><strong>${s.alerts || 0}</strong></div><div><span>Open tasks / all time</span><strong>${data.tasks.filter((t) => t.state !== "resolved").reduce((a,t) => a+t.count, 0)}</strong></div>`;
  $("#historyChart").innerHTML = data.points.length ? data.points.map((p, i) => `<button class="time-bar ${i && p.baseline !== data.points[i-1].baseline ? "baseline-change" : ""}" data-scan="${p.id}" title="${date(p.created_at)} / ${p.occupancy}% / scan #${p.id}" aria-label="Scan ${p.id}, ${p.occupancy}%"><i class="${level(p.status)}" style="height:${Math.max(1,p.occupancy)}%"></i><span>#${p.id}</span></button>`).join("") : empty("No observations in this period");
}
function renderTasks() {
  const active = state.tasks.filter((t) => t.state !== "resolved");
  $("#navAlertCount").textContent = active.length;
  $("#taskSummary").textContent = `${active.length} active / latest ${state.tasks.length} tasks`;
  $("#priorityList").innerHTML = active.sort((a,b) => (a.severity !== "Critical")-(b.severity !== "Critical") || b.missing-a.missing).slice(0,4).map((t) => `<button class="row-card task-open" data-task="${t.id}"><span><strong>${escapeHtml(t.zone_name)}</strong><small>${t.missing} missing / ${escapeHtml(t.assignee || "Unassigned")}</small></span><b class="${level(t.severity)}">${t.severity}</b></button>`).join("") || empty("No active restock tasks");
  const filtered = state.tasks.filter((t) => (!$("#taskSeverity").value || t.severity === $("#taskSeverity").value) && t.assignee.toLowerCase().includes($("#taskAssignee").value.toLowerCase()));
  $("#taskBoard").innerHTML = [["open","Open"],["acknowledged","Acknowledged"],["in_progress","In progress"],["resolved","Resolved"]].map(([status,title]) => {
    const tasks = filtered.filter((t) => t.state === status);
    return `<section class="task-column"><h2>${title}<span>${tasks.length}</span></h2>${tasks.map((t) => `<article class="task-card"><span class="status-pill ${level(t.severity)}">${t.severity}</span><h3>${escapeHtml(t.zone_name)}</h3><p>${t.missing} missing at last observation</p><div>${escapeHtml(t.assignee || "Unassigned")}</div><small>${date(t.updated_at)}</small><button class="text-button" data-task="${t.id}">${state.user?.role === "viewer" ? "View" : "Update"} <i data-lucide="arrow-right"></i></button></article>`).join("") || empty("No tasks")}</section>`;
  }).join(""); icons();
}
async function compare() {
  const before = $("#compareBefore").value, after = $("#compareAfter").value;
  if (!before || !after || before === after) { toast("Choose two different scans."); return; }
  try {
    const [a,b] = await Promise.all([api(`/api/scans/${before}`), api(`/api/scans/${after}`)]);
    renderShelf($("#beforeImage"), a); renderShelf($("#afterImage"), b);
    $("#beforeCaption").textContent = `${a.source} / ${date(a.created_at)} / ${a.occupancy}%`;
    $("#afterCaption").textContent = `${b.source} / ${date(b.created_at)} / ${b.occupancy}%`;
    $("#comparisonSummary").textContent = a.baseline !== b.baseline || a.camera !== b.camera ? "Different layout or source: stock percentages are not directly comparable." :
      `${(b.occupancy-a.occupancy).toFixed(1)} percentage points / ${b.detected_items-a.detected_items} visible items / ${b.missing_items-a.missing_items} missing items` +
      (JSON.stringify(a.tuning) !== JSON.stringify(b.tuning) || a.model_version !== b.model_version ? " / Detection settings or model changed; review the difference." : "");
  } catch (error) { toast(error.message); }
}
function renderInventory() {
  const query = $("#inventorySearch").value.toLowerCase();
  const disabled = state.user?.role === "admin" ? "" : "disabled";
  const field = (z, name, type="text", extra="") => `<input aria-label="${escapeHtml(z.id)} ${name}" data-field="${name}" type="${type}" value="${escapeHtml(z[name] ?? "")}" ${extra} ${disabled}>`;
  $("#inventoryTable").innerHTML = state.layout.zones.filter((z) => `${z.id} ${z.name} ${z.sku || ""} ${z.product || ""}`.toLowerCase().includes(query)).map((z) => `<tr data-zone-id="${escapeHtml(z.id)}"><td><strong>${escapeHtml(z.id)}</strong>${field(z,"name")}</td><td>${field(z,"sku")}${field(z,"product")}</td><td>${field(z,"expected_count","number",'min="1" max="10000"')}</td><td>${field(z,"critical_threshold","number",'min="0" max="99"')}${field(z,"low_threshold","number",'min="1" max="100"')}</td><td class="bounds-cell">${z.bbox.map((v,i) => `<input aria-label="${escapeHtml(z.id)} ${["left","top","right","bottom"][i]}" data-bound="${i}" type="number" step="0.1" min="0" max="100" value="${v}" ${disabled}>`).join("")}</td><td><button class="icon-button" data-remove-zone="${escapeHtml(z.id)}" title="Remove zone" aria-label="Remove ${escapeHtml(z.id)}" ${disabled}><i data-lucide="trash-2"></i></button></td></tr>`).join(""); icons();
}
async function loadAdmin() {
  const [layout, health, cameras] = await Promise.all([api("/api/planogram"), api("/api/health"), api("/api/cameras")]);
  state.layout = layout; renderInventory();
  $("#healthLabel").textContent = "Backend connected"; $("#modelStatusSide").textContent = health.model_available ? "Model available" : "Model missing";
  $("#healthDot").classList.toggle("unhealthy", !health.model_available);
  $("#storageStatus").textContent = `${health.storage === "sqlite" ? "SQLite / local disk" : "PostgreSQL / shared storage"}`;
  $("#modelDetails").innerHTML = `<div><span>Detector</span><b>${health.model_available ? "Model file present" : "Model missing"}</b></div><div><span>Processing</span><strong>One scan at a time</strong></div><div><span>Last scan resolution</span><strong>${state.analysis?.tuning.image_size || "--"}</strong></div>`;
  $("#cameraList").innerHTML = cameras.configured.length ? cameras.configured.map((c) => `<div><span>${escapeHtml(c)}</span><b>Configured</b></div>`).join("") : empty("No IP cameras configured");
  $("#cameraSelect").innerHTML = '<option value="browser">Browser camera</option>' + cameras.configured.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");
  $("#sourceFilter").innerHTML = cameras.sources.map((s) => `<option value="${escapeHtml(s)}">${escapeHtml(s === "upload" ? "Uploaded images" : s === "browser" ? "Browser camera" : s)}</option>`).join("");
  $("#sourceFilter").value = state.source;
  if (["admin","manager"].includes(state.user.role)) {
    const data = await api("/api/users");
    $("#usersList").innerHTML = data.users.map((u) => `<div><span>${escapeHtml(u.username)}</span><b>${u.role}</b></div>`).join("") || empty("Local access only / no accounts yet");
    $("#teamNames").innerHTML = data.users.map((u) => `<option value="${escapeHtml(u.username)}">`).join("");
  }
}
async function startCamera() {
  if (state.cameraRunning || state.scanning) return;
  const camera = $("#cameraSelect").value;
  try {
    if (camera === "browser") {
      if (!navigator.mediaDevices) throw new Error("Camera access requires HTTPS or localhost.");
      state.stream = await navigator.mediaDevices.getUserMedia({video: { facingMode: "environment", width: {ideal: 1280} }, audio: false});
      $("#cameraVideo").srcObject = state.stream; $("#cameraVideo").hidden = false;
      await $("#cameraVideo").play();
    }
    state.source = camera; $("#sourceFilter").value = camera; clearAnalysis(); await refreshData(false);
    state.cameraRunning = true; $("#stopCamera").disabled = false; $("#startCamera").disabled = true;
    $("#cameraSelect").disabled = true; $("#cameraStatus").textContent = "Capturing";
    await captureFrame();
  } catch (error) { stopCamera(); $("#cameraStatus").textContent = error.message; }
}
async function captureFrame() {
  if (!state.cameraRunning || document.hidden) return;
  if (!state.scanning) {
    if (state.source === "browser") {
      const video = $("#cameraVideo");
      if (video.videoWidth) {
        const canvas = document.createElement("canvas"); const ratio = Math.min(1,1280/video.videoWidth);
        canvas.width = Math.round(video.videoWidth*ratio); canvas.height = Math.round(video.videoHeight*ratio);
        canvas.getContext("2d").drawImage(video,0,0,canvas.width,canvas.height);
        const blob = await new Promise((resolve) => canvas.toBlob(resolve,"image/jpeg",.88));
        if (blob && state.cameraRunning) await analyze(new File([blob],`camera-${Date.now()}.jpg`,{type:"image/jpeg"}),"browser");
      }
    } else await runScan(() => api(`/api/cameras/${encodeURIComponent(state.source)}/scan`, jsonRequest("POST", tuning())));
  }
  if (state.cameraRunning) state.timer = setTimeout(captureFrame, Number($("#captureInterval").value)*1000);
}
function stopCamera() {
  state.cameraRunning = false; clearTimeout(state.timer); state.stream?.getTracks().forEach((t) => t.stop());
  state.stream = null; $("#cameraVideo").srcObject = null; $("#cameraVideo").hidden = true;
  $("#stopCamera").disabled = true; $("#startCamera").disabled = state.user?.role === "viewer";
  $("#cameraSelect").disabled = false; $("#cameraStatus").textContent = "Stopped";
}
async function boot() {
  try {
    state.user = await api("/api/me");
    $("#accountLabel").textContent = `${state.user.username} / ${state.user.role}`;
    $("#roleLabel").textContent = state.user.local ? "Local administrator" : state.user.role;
    $$(".admin-only").forEach((el) => { el.hidden = state.user.role !== "admin"; });
    $$(".manager-only").forEach((el) => { el.hidden = !["admin","manager"].includes(state.user.role); });
    $("#startCamera").disabled = state.user.role === "viewer";
    $("#fileInput").disabled = state.user.role === "viewer";
    await loadAdmin(); await refreshData(false);
    $("#sourceContext").textContent = "Connected / " + (state.user.local ? "Local workspace" : state.user.username);
    icons();
  } catch (error) { notice(error.message,"error"); $("#healthLabel").textContent = "Access unavailable"; }
}

$$("[data-page]").forEach((b) => b.addEventListener("click", () => setPage(b.dataset.page)));
$$("[data-go]").forEach((b) => b.addEventListener("click", () => setPage(b.dataset.go)));
$("#scanButton").addEventListener("click", () => analyze(state.selectedFile));
$("#fileInput").addEventListener("change", () => { stopCamera(); clearAnalysis(); state.source="upload"; $("#sourceFilter").value="upload"; state.selectedFile = $("#fileInput").files[0] || null; $("#scanState").textContent="Ready"; $("#scanButton").disabled = !state.selectedFile || state.scanning; notice(state.selectedFile?.name || "No image selected"); refreshData(false); });
$("#refreshButton").addEventListener("click", () => refreshData(false));
$("#sourceFilter").addEventListener("change", () => { stopCamera(); state.source = $("#sourceFilter").value; clearAnalysis(); refreshData(false); });
$("#tuningForm").addEventListener("input", tuningChanged);
$("#overlayReveal").addEventListener("input", (event) => {
  const value = Number(event.target.value);
  $("#overlayRevealValue").textContent = `${value}%`;
  const layer = $("#analysisShelf .detection-layer");
  if (layer) layer.style.clipPath = `inset(0 ${100-value}% 0 0)`;
  hideProductTooltip();
});
$("#tuningForm").addEventListener("submit", (e) => e.preventDefault());
$("#resetTuning").addEventListener("click", () => { $("#tuningForm").reset(); tuningChanged(); });
for (const id of ["showBoxes","showZones","showHeatmap","classFilter"]) $(`#${id}`).addEventListener("change", () => { renderShelf($("#analysisShelf"),state.analysis,true); renderShelf($("#monitorShelf"),state.analysis); });
for (const id of ["zoneSearch","zoneStatus"]) $(`#${id}`).addEventListener("input",renderZoneTable);
for (const id of ["taskSeverity","taskAssignee"]) $(`#${id}`).addEventListener("input",renderTasks);
$("#compareButton").addEventListener("click",compare);
$("#inventorySearch").addEventListener("input",renderInventory);
$("#inventoryTable").addEventListener("input",(e) => { const row=e.target.closest("[data-zone-id]"); if (!row) return; const z=state.layout.zones.find((z)=>z.id===row.dataset.zoneId); if (e.target.dataset.bound !== undefined) z.bbox[+e.target.dataset.bound]=+e.target.value; else if (e.target.dataset.field) z[e.target.dataset.field]=e.target.type === "number" ? +e.target.value : e.target.value; $("#layoutMessage").textContent="Unsaved changes"; });
$("#addZone").addEventListener("click",()=>{ let index=state.layout.zones.length+1; while(state.layout.zones.some((z)=>z.id===`Z${index}`)) index++; state.layout.zones.push({id:`Z${index}`,name:`Zone ${index}`,sku:"",product:"Shelf item",expected_count:10,critical_threshold:45,low_threshold:75,bbox:[0,0,100,100]}); renderInventory(); $("#layoutMessage").textContent="Unsaved changes"; });
$("#saveLayout").addEventListener("click",async()=>{ try { state.layout=await api("/api/planogram",jsonRequest("PUT",state.layout)); $("#layoutMessage").textContent="Layout saved. Existing scans retain their original layout."; renderInventory(); } catch(e) { $("#layoutMessage").textContent=e.message; } });
let searchTimer;
for(const id of ["reportDays","historyStatus","historySearch"]) $(`#${id}`).addEventListener("input",()=>{ clearTimeout(searchTimer); searchTimer=setTimeout(()=>refreshData(false),250); });
$("#moreHistory").addEventListener("click",async()=>{ try { const data=await api(`/api/history?${historyQuery()}&before=${state.next}`); state.history.push(...data.history); state.next=data.next; renderHistory(); } catch(e){toast(e.message);} });
$("#exportButton").addEventListener("click",()=>{ window.location.href=`/api/reports.csv?camera=${encodeURIComponent(state.source)}&days=${$("#reportDays").value}`; });
$("#printButton").addEventListener("click",()=>window.print());
$("#startCamera").addEventListener("click",startCamera); $("#stopCamera").addEventListener("click",stopCamera);
document.addEventListener("visibilitychange",()=>{if(document.hidden)stopCamera();});
window.addEventListener("pagehide",stopCamera);
document.addEventListener("click",async(e)=>{
  const scan=e.target.closest("[data-scan]");
  if(scan) { try { renderAnalysis(await api(`/api/scans/${scan.dataset.scan}`)); setPage("analysis"); notice(`Viewing saved scan #${scan.dataset.scan}`); } catch(error){toast(error.message);} }
  const remove=e.target.closest("[data-remove-zone]");
  if(remove) { state.layout.zones=state.layout.zones.filter((z)=>z.id!==remove.dataset.removeZone); renderInventory(); $("#layoutMessage").textContent="Unsaved changes"; }
  const task=e.target.closest("[data-task]");
  if(task) { const t=state.tasks.find((t)=>t.id===+task.dataset.task); if(!t)return; const f=$("#taskForm").elements; f.id.value=t.id; f.state.value=t.state; f.assignee.value=t.assignee; f.note.value=""; $("#taskTitle").textContent=t.zone_name; $("#taskError").textContent=""; $("#taskForm button[type=submit]").disabled=state.user.role==="viewer"; $("#taskDialog").showModal(); }
});
$("#closeTask").addEventListener("click",()=>$("#taskDialog").close());
$("#taskForm").addEventListener("submit",async(e)=>{ e.preventDefault(); const f=e.target.elements; try { await api(`/api/tasks/${f.id.value}`,jsonRequest("PATCH",{state:f.state.value,assignee:f.assignee.value,note:f.note.value})); $("#taskDialog").close(); await refreshData(false); }catch(error){$("#taskError").textContent=error.message;} });
$("#userForm").addEventListener("submit",async(e)=>{e.preventDefault(); const data=Object.fromEntries(new FormData(e.target)); try { await api("/api/users",jsonRequest("POST",data)); e.target.reset(); if(state.user.local){state.user=null; $("#loginDialog").showModal();}else await loadAdmin(); toast("User created"); }catch(error){toast(error.message);} });
$("#loginDialog").addEventListener("cancel",(e)=>e.preventDefault());
$("#loginForm").addEventListener("submit",async(e)=>{e.preventDefault(); try { await api("/api/login",jsonRequest("POST",Object.fromEntries(new FormData(e.target)))); $("#loginDialog").close(); e.target.reset(); await boot(); }catch(error){$("#loginError").textContent=error.message;} });
$("#accountButton").addEventListener("click",async()=>{if(state.user?.local){setPage("admin");return;} try{await api("/api/logout",{method:"POST"}); location.reload();}catch(e){toast(e.message);} });
window.addEventListener("offline",()=>{stopCamera(); notice("Offline / saved dashboard only. Reconnect to scan or update tasks.","error"); $("#healthLabel").textContent="Offline";});
window.addEventListener("online",()=>boot());
if("serviceWorker" in navigator) {
  navigator.serviceWorker.getRegistrations().then((registrations) => {
    for (const registration of registrations) {
      if (registration.active?.scriptURL === `${location.origin}/static/sw.js`) registration.unregister();
    }
  }).catch(()=>{});
  navigator.serviceWorker.register("/sw.js", {scope:"/", updateViaCache:"none"}).then((registration) => registration.update()).catch(()=>{});
}
clearAnalysis(); setPage("dashboard"); icons(); boot();
