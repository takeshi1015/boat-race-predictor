/**
 * app.js – Dashboard interactivity for Boat Race Predictor
 *
 * Fetches prediction data from the REST API and populates the dashboard UI.
 */

/* global renderConfidenceChart, renderPredictionPieChart */

const MODEL_LABELS = {
  logistic_regression: "ロジスティック回帰",
  random_forest: "ランダムフォレスト",
  neural_network: "ニューラルネットワーク",
  rule_based: "ルールベース",
  statistical: "統計モデル",
  ensemble: "アンサンブル",
};

const MODEL_BADGE_COLORS = {
  logistic_regression: "primary",
  random_forest: "success",
  neural_network: "danger",
  rule_based: "warning",
  statistical: "info",
  ensemble: "dark",
};

/**
 * Fetch prediction data from the API and refresh all dashboard widgets.
 */
async function loadDashboard() {
  try {
    const res = await fetch("/api/predictions");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    updateEnsembleBanner(data);
    renderModelCards(data);
    renderCharts(data);
    updateTimestamp(data.timestamp);
  } catch (err) {
    console.error("Failed to load predictions:", err);
    showError();
  }
}

/**
 * Update the ensemble result banner.
 *
 * @param {Object} data - API response payload.
 */
function updateEnsembleBanner(data) {
  const ens = (data.predictions || {}).ensemble || {};
  const pred = (ens.prediction || []).join(", ") || "N/A";
  const conf = ((ens.confidence || 0) * 100).toFixed(1);

  const predEl = document.getElementById("ensemble-prediction");
  const confEl = document.getElementById("ensemble-confidence");
  if (predEl) predEl.textContent = `枠番 ${pred}`;
  if (confEl) confEl.textContent = `信頼度 ${conf}%`;
}

/**
 * Render individual model prediction cards.
 *
 * @param {Object} data - API response payload.
 */
function renderModelCards(data) {
  const container = document.getElementById("model-cards");
  if (!container) return;

  const predictions = data.predictions || {};
  container.innerHTML = "";

  const orderedModels = [
    "logistic_regression",
    "random_forest",
    "neural_network",
    "rule_based",
    "statistical",
    "ensemble",
  ];

  orderedModels.forEach((modelKey) => {
    if (!(modelKey in predictions)) return;
    const info = predictions[modelKey];
    const pred = info.prediction || [];
    const conf = ((info.confidence || 0) * 100).toFixed(1);
    const color = MODEL_BADGE_COLORS[modelKey] || "secondary";
    const label = MODEL_LABELS[modelKey] || modelKey;

    const col = document.createElement("div");
    col.className = "col-sm-6 col-xl-4";
    col.innerHTML = `
      <div class="card shadow-sm h-100 model-card">
        <div class="card-body">
          <div class="d-flex justify-content-between align-items-start mb-2">
            <span class="badge bg-${color} badge-model">${label}</span>
            <span class="text-muted small">${conf}%</span>
          </div>
          <div class="d-flex gap-2 mb-3">
            ${pred.slice(0, 3).map((p, i) => `
              <div class="text-center">
                <div class="text-muted small">${i + 1}位</div>
                <div class="fw-bold fs-5">${p}</div>
              </div>`).join("")}
          </div>
          <div class="progress" style="height:6px" title="信頼度 ${conf}%">
            <div class="progress-bar bg-${color}" style="width:${conf}%"></div>
          </div>
        </div>
      </div>`;
    container.appendChild(col);
  });
}

/**
 * Render confidence bar chart and first-place distribution pie chart.
 *
 * @param {Object} data - API response payload.
 */
function renderCharts(data) {
  const predictions = data.predictions || {};

  // Confidence chart (all models including ensemble)
  const confLabels = [];
  const confValues = [];
  Object.entries(predictions).forEach(([key, info]) => {
    confLabels.push(MODEL_LABELS[key] || key);
    confValues.push(info.confidence || 0);
  });
  renderConfidenceChart(confLabels, confValues);

  // First-place vote distribution (exclude ensemble)
  const voteCounts = {};
  Object.entries(predictions).forEach(([key, info]) => {
    if (key === "ensemble") return;
    const first = (info.prediction || [])[0];
    if (first !== undefined) {
      const label = `枠 ${first}`;
      voteCounts[label] = (voteCounts[label] || 0) + 1;
    }
  });
  const pieLabels = Object.keys(voteCounts);
  const pieCounts = Object.values(voteCounts);
  renderPredictionPieChart(pieLabels, pieCounts);
}

/**
 * Update the "last updated" timestamp display.
 *
 * @param {string|null} iso - ISO 8601 timestamp string or null.
 */
function updateTimestamp(iso) {
  const el = document.getElementById("last-updated");
  if (!el) return;
  if (!iso) {
    el.textContent = "-";
    return;
  }
  try {
    el.textContent = new Date(iso).toLocaleString("ja-JP");
  } catch (_) {
    el.textContent = iso;
  }
}

/**
 * Show an error message in the model cards container.
 */
function showError() {
  const container = document.getElementById("model-cards");
  if (container) {
    container.innerHTML = `
      <div class="col-12">
        <div class="alert alert-danger" role="alert">
          <i class="bi bi-exclamation-triangle-fill me-2"></i>
          予測データの読み込みに失敗しました。ページを再読み込みしてください。
        </div>
      </div>`;
  }
}

// ── Boot ──────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  // Only run on the dashboard page
  if (document.getElementById("model-cards")) {
    loadDashboard();

    const refreshBtn = document.getElementById("btn-refresh");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", loadDashboard);
    }
  }
});

// ── Race countdown timer ──────────────────────────────────────────────────
// Updates .time-remaining spans and toggles state classes every second.
setInterval(() => {
  document.querySelectorAll(".race-item[data-deadline]").forEach((el) => {
    const deadline = el.dataset.deadline;
    if (!deadline) return;

    const now = new Date();
    const remaining = Math.max(0, (new Date(deadline) - now) / 1000);

    // Update remaining time text
    const timeEl = el.querySelector(".time-remaining");
    if (timeEl) {
      const min = Math.floor(remaining / 60);
      const sec = Math.floor(remaining % 60);
      timeEl.textContent = `${min}分${sec}秒`;
    }

    // Update state class
    if (remaining <= 0) {
      el.classList.add("expired");
      el.classList.remove("urgent", "available");
    } else if (remaining <= 300) {
      el.classList.add("urgent");
      el.classList.remove("expired", "available");
    } else {
      el.classList.add("available");
      el.classList.remove("urgent", "expired");
    }
  });
}, 1000);
