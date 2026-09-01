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
  return `left:${x1}%;top:${y1}%;width:${x2 - x1}%;height:${y2 - y1}%`;
}

function renderSyntheticShelf(target, analysis) {
  const zones = analysis?.zones || [];
  const detections = analysis?.detections || [];
  target.innerHTML = `
    <div class="shelf-scene">
      <div class="shelf-board top"></div>
      <div class="shelf-board middle"></div>
      <div class="shelf-board bottom"></div>
      ${zones.map((zone) => `<div class="zone-box ${statusClass(zone.status)}" style="${boxStyle(zone.bbox)}"><span>${zone.id}</span></div>`).join("")}
      ${detections.map((item) => `<div class="product-box" style="${boxStyle(item.bbox)}" title="${item.label} ${item.confidence}"><span>${item.label}</span></div>`).join("")}
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
        <span>${zone.product} • ${zone.detected_count}/${zone.expected_count} detected</span>
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
      <article class="alert-card ${alert.priority.toLowerCase()}">
        <div>
          <strong>${alert.shelf}</strong>
          <span>${alert.message}</span>
        </div>
        <b>${alert.priority}</b>
      </article>
    `).join("")
    : `<article class="empty-card">No restock alerts.</article>`;

  const bars = document.querySelector("#trendBars");
  bars.innerHTML = analysis.trend.map((value) => `<span style="height:${Math.max(value, 18)}%" title="${value}%"></span>`).join("");

  renderSyntheticShelf(document.querySelector("#monitorShelf"), analysis);
  renderSyntheticShelf(document.querySelector("#analysisShelf"), analysis);
}

async function analyze(file) {
  scanButton.disabled = true;
  monitorButton.disabled = true;
  scanButton.textContent = "Scanning";
  const body = new FormData();
  if (file) body.append("file", file);

  const response = await fetch("/api/analyze", { method: "POST", body });
  const analysis = await response.json();
  state.analysis = analysis;

  if (analysis.image) {
    uploadPreview.style.backgroundImage = `url(${analysis.image})`;
    imageLayer.classList.add("with-image");
  }

  renderAnalysis(analysis);
  scanButton.disabled = false;
  monitorButton.disabled = false;
  scanButton.textContent = "Scan Shelf";
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

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/static/sw.js").catch(() => {});
}

setPage("dashboard");
analyze();
