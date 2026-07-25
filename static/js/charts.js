/**
 * charts.js – Chart rendering helpers using Chart.js
 *
 * Exposes two functions consumed by app.js:
 *   renderConfidenceChart(labels, values)
 *   renderPredictionPieChart(labels, counts)
 */

/* eslint-disable no-unused-vars */

let confidenceChartInstance = null;
let pieChartInstance = null;

/**
 * Render (or update) the bar chart that compares confidence scores.
 *
 * @param {string[]} labels - Model names.
 * @param {number[]} values - Confidence values in [0, 1].
 */
function renderConfidenceChart(labels, values) {
  const ctx = document.getElementById("confidence-chart");
  if (!ctx) return;

  if (confidenceChartInstance) {
    confidenceChartInstance.destroy();
  }

  confidenceChartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "信頼度スコア",
          data: values.map((v) => +(v * 100).toFixed(1)),
          backgroundColor: [
            "rgba(13,110,253,0.7)",
            "rgba(25,135,84,0.7)",
            "rgba(220,53,69,0.7)",
            "rgba(255,193,7,0.7)",
            "rgba(111,66,193,0.7)",
            "rgba(13,202,240,0.7)",
          ],
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.parsed.y.toFixed(1)}%`,
          },
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          max: 100,
          ticks: { callback: (v) => `${v}%` },
        },
      },
    },
  });
}

/**
 * Render (or update) the doughnut chart showing first-place prediction distribution.
 *
 * @param {string[]} labels - Candidate identifiers.
 * @param {number[]} counts - Vote counts per candidate.
 */
function renderPredictionPieChart(labels, counts) {
  const ctx = document.getElementById("prediction-pie-chart");
  if (!ctx) return;

  if (pieChartInstance) {
    pieChartInstance.destroy();
  }

  pieChartInstance = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          data: counts,
          backgroundColor: [
            "rgba(13,110,253,0.8)",
            "rgba(25,135,84,0.8)",
            "rgba(220,53,69,0.8)",
            "rgba(255,193,7,0.8)",
            "rgba(111,66,193,0.8)",
            "rgba(13,202,240,0.8)",
          ],
          hoverOffset: 8,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: "bottom" },
      },
    },
  });
}
