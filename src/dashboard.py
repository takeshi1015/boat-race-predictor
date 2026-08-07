"""
Flask Dashboard
Web dashboard for the Boat Race Predictor - runs on port 8080.

Usage:
    python src/dashboard.py
"""

import os
import sys
import logging
import pandas as pd
from flask import Flask, jsonify, render_template_string, request

# Allow importing sibling modules when run directly
sys.path.insert(0, os.path.dirname(__file__))

from predictor import load_models, predict_race  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Global model cache
# ---------------------------------------------------------------------------
_models: dict = {}

VENUE_NAMES = {
    1: "桐生", 2: "戸田", 3: "江戸川", 4: "平和島", 5: "多摩川",
    6: "浜名湖", 7: "蒲郡", 8: "常滑", 9: "津", 10: "三国",
    11: "びわこ", 12: "住之江", 13: "尼崎", 14: "鳴門", 15: "丸亀",
    16: "児島", 17: "宮島", 18: "徳山", 19: "下関", 20: "若松",
    21: "芦屋", 22: "福岡", 23: "唐津", 24: "大村",
}

# ---------------------------------------------------------------------------
# HTML template (self-contained, no external template files required)
# ---------------------------------------------------------------------------
_INDEX_HTML = """
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ボートレース予想ダッシュボード</title>
<style>
  body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; background: #0d1b2a; color: #e0e0e0; }
  header { background: #1a3a5c; padding: 16px 32px; display: flex; align-items: center; }
  header h1 { margin: 0; font-size: 1.5rem; color: #4fc3f7; }
  .container { max-width: 960px; margin: 32px auto; padding: 0 16px; }
  .card { background: #1e2f45; border-radius: 8px; padding: 24px; margin-bottom: 24px; }
  h2 { color: #4fc3f7; margin-top: 0; }
  label { display: block; margin: 8px 0 4px; }
  select, input { background: #0d1b2a; color: #e0e0e0; border: 1px solid #4fc3f7; border-radius: 4px; padding: 6px 10px; font-size: 1rem; }
  button { background: #4fc3f7; color: #0d1b2a; border: none; padding: 10px 24px; border-radius: 4px; font-size: 1rem; cursor: pointer; font-weight: bold; margin-top: 12px; }
  button:hover { background: #81d4fa; }
  table { width: 100%; border-collapse: collapse; margin-top: 16px; }
  th { background: #1a3a5c; color: #4fc3f7; padding: 8px 12px; text-align: center; }
  td { padding: 8px 12px; text-align: center; border-bottom: 1px solid #1a3a5c; }
  tr:nth-child(even) td { background: #162433; }
  .rank-1 td { color: #ffd700; font-weight: bold; }
  .rank-2 td { color: #c0c0c0; }
  .rank-3 td { color: #cd7f32; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.85rem; }
  .badge-win { background: #ffd700; color: #0d1b2a; }
  .stat { display: inline-block; margin: 8px 16px 8px 0; }
  .stat .value { font-size: 2rem; font-weight: bold; color: #4fc3f7; }
  .stat .label { font-size: 0.85rem; color: #90a4ae; }
  #message { color: #ff7043; margin-top: 8px; }
</style>
</head>
<body>
<header>
  <h1>🚤 ボートレース予想ダッシュボード</h1>
</header>
<div class="container">

  <div class="card">
    <h2>📊 データ概要</h2>
    <div id="stats">読み込み中...</div>
  </div>

  <div class="card">
    <h2>🔮 レース予想</h2>
    <label>場コード</label>
    <select id="venue">
      {% for code, name in venues %}
      <option value="{{ code }}">{{ "%02d"|format(code) }} {{ name }}</option>
      {% endfor %}
    </select>
    <label>レース番号</label>
    <select id="race_number">
      {% for r in range(1, 13) %}
      <option value="{{ r }}">{{ r }}R</option>
      {% endfor %}
    </select>
    <button onclick="predict()">予想する</button>
    <div id="message"></div>
    <div id="result"></div>
  </div>

  <div class="card">
    <h2>📈 最近の結果サマリ</h2>
    <div id="summary">読み込み中...</div>
  </div>

</div>
<script>
async function loadStats() {
  const r = await fetch('/api/stats');
  const d = await r.json();
  if (d.error) { document.getElementById('stats').innerText = d.error; return; }
  document.getElementById('stats').innerHTML =
    `<span class="stat"><span class="value">${d.total_races}</span><br><span class="label">総レース数</span></span>` +
    `<span class="stat"><span class="value">${d.venues}</span><br><span class="label">場数</span></span>` +
    `<span class="stat"><span class="value">${d.date_range}</span><br><span class="label">期間</span></span>`;
}

async function loadSummary() {
  const r = await fetch('/api/summary');
  const d = await r.json();
  if (d.error) { document.getElementById('summary').innerText = d.error; return; }
  let html = '<table><tr><th>艇番</th><th>勝率</th></tr>';
  for (const row of d.lane_win_rates) {
    html += `<tr><td>${row.lane}号艇</td><td>${(row.win_rate*100).toFixed(1)}%</td></tr>`;
  }
  html += '</table>';
  document.getElementById('summary').innerHTML = html;
}

async function predict() {
  const venue = document.getElementById('venue').value;
  const race_number = document.getElementById('race_number').value;
  document.getElementById('message').innerText = '予想中...';
  document.getElementById('result').innerHTML = '';
  const r = await fetch(`/api/predict?venue_code=${venue}&race_number=${race_number}`);
  const d = await r.json();
  if (d.error) { document.getElementById('message').innerText = d.error; return; }
  document.getElementById('message').innerText = '';
  let html = `<p>場: ${d.venue_name} / ${d.race_number}R</p>`;
  html += '<table><tr><th>予想順位</th><th>艇番</th><th>勝率スコア</th></tr>';
  for (const p of d.predictions) {
    const cls = p.predicted_rank <= 3 ? `rank-${p.predicted_rank}` : '';
    const badge = p.predicted_rank === 1 ? '<span class="badge badge-win">◎</span>' : '';
    html += `<tr class="${cls}"><td>${p.predicted_rank}${badge}</td><td>${p.lane}号艇</td><td>${(p.win_probability*100).toFixed(2)}%</td></tr>`;
  }
  html += '</table>';
  document.getElementById('result').innerHTML = html;
}

loadStats();
loadSummary();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    venues = sorted(VENUE_NAMES.items())
    return render_template_string(_INDEX_HTML, venues=venues)


@app.route("/api/stats")
def api_stats():
    path = "data/all_races.csv"
    if not os.path.exists(path):
        return jsonify({"error": "data/all_races.csv が見つかりません。scraper.py を実行してください。"})
    df = pd.read_csv(path)
    date_min = df["date"].min()
    date_max = df["date"].max()
    return jsonify({
        "total_races": len(df),
        "venues": int(df["venue_code"].nunique()),
        "date_range": f"{date_min} ～ {date_max}",
    })


@app.route("/api/summary")
def api_summary():
    path = "data/all_races.csv"
    if not os.path.exists(path):
        return jsonify({"error": "データが見つかりません"})
    df = pd.read_csv(path)
    df["result_1st"] = pd.to_numeric(df["result_1st"], errors="coerce")
    total = len(df)
    lane_stats = []
    for lane in range(1, 7):
        wins = int((df["result_1st"] == lane).sum())
        lane_stats.append({"lane": lane, "win_rate": wins / total if total > 0 else 0})
    return jsonify({"lane_win_rates": lane_stats})


@app.route("/api/predict")
def api_predict():
    global _models
    if not _models:
        try:
            _models = load_models()
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)})

    try:
        venue_code = int(request.args.get("venue_code", 12))
        race_number = int(request.args.get("race_number", 1))
    except ValueError:
        return jsonify({"error": "パラメータが不正です"})

    preds = predict_race(_models, venue_code, race_number)
    return jsonify({
        "venue_code": venue_code,
        "venue_name": VENUE_NAMES.get(venue_code, ""),
        "race_number": race_number,
        "predictions": preds,
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    port = int(os.environ.get("PORT", 8080))
    logger.info("=" * 50)
    logger.info("ダッシュボード起動: http://0.0.0.0:%d", port)
    logger.info("=" * 50)
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
