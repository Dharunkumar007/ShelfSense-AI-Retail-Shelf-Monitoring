const state = {
  analysis: null,
  page: "dashboard"
};

const views = document.querySelectorAll(".view");
const navButtons = document.querySelectorAll("[data-page]");
const scanButton = document.querySelector("#scanButton");
const monitorButton = document.querySelector("#monitorButton");
const fileInput = document.querySelector("#fileInput");
const imageLayer = document.querySelector("#imageLayer");
const uploadPreview = document.querySelector("#uploadPreview");

function setPage(page) {
  state.page = page;
  views.forEach((view) => view.classList.toggle("active", view.id === `${page}View`));
  navButtons.forEach((button) => button.classList.toggle("active", button.dataset.page === page));
}

function statusClass(status) {
  if (status === "Critical") return "danger";
  if (status === "Low" || status === "Low Stock") return "warn";
  return "good";
}

function boxStyle(bbox) {
  const [x1, y1, x2, y2] = bbox;
  const width = Math.max(0.5, x2 - x1);
  const height = Math.max(0.5, y2 - y1);
  return `left:${x1}%;top:${y1}%;width:${width}%;height:${height}%;`;
}

function renderSyntheticShelf(target, analysis) {
  if (!target) return;
  const zones = analysis?.zones || [];
  const detections = analysis?.detections || [];
  const hasImage = Boolean(analysis?.image);

  target.innerHTML = `
    <div class="shelf-scene ${hasImage ? "real-feed" : "synthetic-feed"}">
      ${
        hasImage
          ? ""
          : `
        <div class="shelf-board top"></div>
        <div class="shelf-board middle"></div>
        <div class="shelf-board bottom"></div>
      `
      }
      ${zones
        .map(
          (zone) => `
        <div class="zone-box ${statusClass(zone.status)}" style="${boxStyle(zone.bbox)}" title="${zone.name}">
          <span class="zone-tag">${zone.id}</span>
        </div>
      `
        )
        .join("")}
      ${detections
        .map((item) => {
          const confPercent = Math.round((item.confidence || 0) * 100);
          return `
        <div class="product-box" style="${boxStyle(item.bbox)}" title="${item.label} (${confPercent}%)">
          <span class="box-tooltip">${confPercent}%</span>
        </div>
      `;
        })
        .join("")}
    </div>
  `;
}

function renderAnalysis(analysis) {
  document.querySelector("#occupancyValue").textContent = `${analysis.occupancy}%`;
  document.querySelector("#detectedValue").textContent = analysis.detected_items;
  document.querySelector("#alertValue").textContent = analysis.alerts.length;
  document.querySelector("#statusBadge").textContent = analysis.status;
  document.querySelector("#statusBadge").className = `badge ${statusClass(analysis.status)}`;

  const zoneMarkup = analysis.zones.map((zone) => `
    <article class="row-card">
      <div>
        <strong>${zone.name}</strong>
        <span>${zone.product || "Shelf Item"} • ${zone.detected_count}/${zone.expected_count} detected</span>
      </div>
      <b class="${statusClass(zone.status)}">${zone.status}</b>
    </article>
  `).join("");

  document.querySelectorAll(".zone-list").forEach((zoneList) => {
    zoneList.innerHTML = zoneMarkup;
  });

  const alertList = document.querySelector("#alertList");
  alertList.innerHTML = analysis.alerts.length
    ? analysis.alerts.map((alert) => `
      <article class="alert-card danger">
        <div>
          <strong>${alert.zone_name}</strong>
          <span>${alert.status} priority restock required.</span>
        </div>
        <b>High</b>
      </article>
    `).join("")
    : `<article class="row-card">No restock alerts.</article>`;

  const bars = document.querySelector("#trendBars");
  bars.innerHTML = analysis.trend.map((value) => `<span style="height:${Math.max(value, 18)}%" title="${value}%"></span>`).join("");

  // Renders the synthetic blueprint in the Overview tab
  renderSyntheticShelf(document.querySelector("#monitorShelf"), analysis);
}

function renderLiveOverlay(target, analysis) {
  if (!target) return;
  const detections = analysis?.detections || [];
  target.innerHTML = detections.map((item) => {
      const conf = Math.round((item.confidence || 0) * 100);
      return `
          <div class="product-box pulse-hover" style="${boxStyle(item.bbox)}">
              <div class="box-crosshair"></div>
              <span class="box-tooltip">${item.label} [${conf}%]</span>
          </div>
      `;
  }).join("");
}

async function analyze(file) {
  // If no file is provided, do nothing. This stops the mock data spam on startup.
  if (!file) return;

  scanButton.disabled = true;
  monitorButton.disabled = true;

  const body = new FormData();
  body.append("file", file);

  try {
    // --- STEP 1: AUTO-CALIBRATE ON UPLOAD ---
    scanButton.textContent = "Calibrating Layout...";
    await fetch("/api/calibrate", { method: "POST", body });
    if (typeof loadAdminPanel === "function") loadAdminPanel();

    // --- STEP 2: ANALYZE THE SHELF ---
    scanButton.textContent = "Analyzing Stock...";
    const response = await fetch("/api/analyze", { method: "POST", body });
    const analysis = await response.json();
    state.analysis = analysis;

    if (analysis.image) {
      // Create an image object to calculate the exact aspect ratio
      const img = new Image();
      img.onload = function() {
          const ratio = img.width / img.height;
          // Apply the ratio to BOTH preview containers so boxes align perfectly
          uploadPreview.style.aspectRatio = ratio;
          uploadPreview.style.backgroundSize = "100% 100%";
          uploadPreview.style.backgroundPosition = "center";
          uploadPreview.style.backgroundRepeat = "no-repeat";

          // Render the overlay only AFTER the container has resized
          renderLiveOverlay(document.querySelector("#analysisShelf"), analysis);
      };
      // Trigger the image load
      img.src = analysis.image;

      uploadPreview.style.backgroundImage = `url(${analysis.image})`;
      imageLayer.classList.add("with-image");
    }

    renderAnalysis(analysis);
  } catch (error) {
    console.error("Detection failed:", error);
  } finally {
    scanButton.disabled = false;
    monitorButton.disabled = false;
    scanButton.textContent = "Scan Shelf";
  }
}

navButtons.forEach((button) => button.addEventListener("click", () => setPage(button.dataset.page)));
scanButton.addEventListener("click", () => analyze(fileInput.files[0]));
monitorButton.addEventListener("click", () => {
  setPage("monitor");
  analyze(fileInput.files[0]);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) analyze(fileInput.files[0]);
});

async function loadAdminPanel() {
  try {
    const response = await fetch("/api/planogram");
    const planogram = await response.json();

    // Inject the real zones into the Camera Zones column
    const zoneInputs = planogram.zones.map(z => `<input value="${z.name}" readonly title="Cannot edit in prototype" />`).join("");
    document.querySelectorAll(".admin-grid .panel")[2].innerHTML = `
      <h2>Camera Zones</h2>
      <p style="color:var(--text-secondary); font-size: 0.85rem;">Detected from backend JSON.</p>
      ${zoneInputs}
    `;

    // Overwrite the Product Catalog with actual products
    document.querySelectorAll(".admin-grid .panel")[0].innerHTML = `
      <h2>Product Catalog</h2>
      <input value="Shelf Item" readonly />
      <input value="Stock" readonly />
    `;
  } catch (err) {
    console.error("Failed to load admin data", err);
  }
}

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/static/sw.js").catch(() => {});
}

setPage("dashboard");
if (typeof loadAdminPanel === "function") loadAdminPanel();

document.querySelector("#calibrateBtn")?.addEventListener("click", async () => {
  const fileInput = document.querySelector("#calibrateInput");
  const statusText = document.querySelector("#calibrateStatus");

  if (!fileInput.files[0]) {
    statusText.textContent = "Please select a reference image first.";
    statusText.style.color = "var(--alert-red)";
    return;
  }

  statusText.textContent = "Processing layout via YOLO...";
  statusText.style.color = "var(--warning-yellow)";

  const body = new FormData();
  body.append("file", fileInput.files[0]);

  try {
    const response = await fetch("/api/calibrate", { method: "POST", body });
    const result = await response.json();

    if (result.status === "success") {
      statusText.textContent = `Success! Generated ${result.zones_created} zones across ${result.shelves} shelves.`;
      statusText.style.color = "var(--success-green)";
      loadAdminPanel(); // Refresh the inputs
    } else {
      statusText.textContent = `Error: ${result.message}`;
      statusText.style.color = "var(--alert-red)";
    }
  } catch (error) {
    statusText.textContent = "Network error during calibration.";
    statusText.style.color = "var(--alert-red)";
  }
});
