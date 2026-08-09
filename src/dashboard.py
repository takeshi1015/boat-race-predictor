"""
src/dashboard.py

Flask ベースの Web ダッシュボード（ポート 8080）。
リアルタイム統計・予想表示。
"""

import json
import logging
import os
import sys

import pandas as pd
from flask import Flask, jsonify, render_template_string, request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Predictor is loaded once at startup to avoid re-reading model files on every request.
_predictor = None


def _get_predictor():
    global _predictor  # noqa: PLW0603
    if _predictor is None:
        try:
            from predictor import BoatracePredictor  # noqa: PLC0415
            _predictor = BoatracePredictor()
        except Exception as exc:
            logger.warning("予測モデルのロード失敗: %s", exc)
    return _predictor

# ------------------------------------------------------------------
# HTMLテンプレート（外部ファイル不要でスタンドアロン動作）
# ------------------------------------------------------------------

_DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ボートレース予想システム</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; }
    header { background: #1e40af; padding: 1rem 2rem; display: flex; align-items: center; gap: 1rem; }
    header h1 { font-size: 1.5rem; }
    .badge { background: #22c55e; color: #fff; border-radius: 9999px; padding: 0.2rem 0.7rem; font-size: 0.75rem; }
    main { padding: 2rem; max-width: 1200px; margin: 0 auto; }
    .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
    .stat-card { background: #1e293b; border-radius: 0.75rem; padding: 1.2rem; text-align: center; }
    .stat-card .label { font-size: 0.8rem; color: #94a3b8; margin-bottom: 0.4rem; }
    .stat-card .value { font-size: 2rem; font-weight: 700; color: #60a5fa; }
    .section { background: #1e293b; border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 1.5rem; }
    .section h2 { font-size: 1.1rem; margin-bottom: 1rem; color: #93c5fd; }
    .form-row { display: flex; gap: 1rem; flex-wrap: wrap; align-items: flex-end; margin-bottom: 1rem; }
    label { font-size: 0.85rem; color: #94a3b8; }
    select, input { background: #0f172a; color: #e2e8f0; border: 1px solid #334155; border-radius: 0.5rem; padding: 0.5rem 0.75rem; font-size: 0.9rem; }
    button { background: #2563eb; color: #fff; border: none; border-radius: 0.5rem; padding: 0.55rem 1.2rem; cursor: pointer; font-size: 0.9rem; }
    button:hover { background: #1d4ed8; }
    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
    th, td { padding: 0.6rem 0.8rem; text-align: center; border-bottom: 1px solid #334155; }
    th { color: #94a3b8; font-weight: 600; }
    .high { color: #22c55e; font-weight: 700; }
    .mid  { color: #facc15; }
    .low  { color: #ef4444; }
    .top1 { background: #1e3a5f; }
    #result-box { display: none; }
  </style>
</head>
<body>
  <header>
    <h1>⛵ ボートレース予想システム</h1>
    <span class="badge">稼働中</span>
  </header>
  <main>
    <!-- 統計カード -->
    <div class="stats-grid" id="stats-cards">
      <div class="stat-card"><div class="label">データ件数</div><div class="value" id="stat-total">―</div></div>
      <div class="stat-card"><div class="label">期間（日）</div><div class="value" id="stat-days">―</div></div>
      <div class="stat-card"><div class="label">会場数</div><div class="value" id="stat-venues">―</div></div>
      <div class="stat-card"><div class="label">モデル数</div><div class="value" id="stat-models">―</div></div>
    </div>

    <!-- 予想フォーム -->
    <div class="section">
      <h2>🔮 レース予想</h2>
      <div class="form-row">
        <div>
          <label>会場コード (1-24)</label><br>
          <input type="number" id="venue" value="3" min="1" max="24" style="width:120px">
        </div>
        <div>
          <label>レース番号 (1-12)</label><br>
          <input type="number" id="race" value="1" min="1" max="12" style="width:120px">
        </div>
        <button onclick="predict()">予想する</button>
      </div>
      <div id="result-box">
        <table>
          <thead><tr><th>艇番</th><th>勝利確率</th><th>信頼度</th></tr></thead>
          <tbody id="pred-table"></tbody>
        </table>
        <p style="margin-top:0.8rem;color:#94a3b8;font-size:0.85rem" id="method-label"></p>
      </div>
    </div>

    <!-- 全会場今日の予想 -->
    <div class="section">
      <h2>📊 本日の注目レース（全会場 R1）</h2>
      <div id="today-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:1rem;"></div>
      <button onclick="loadToday()" style="margin-top:1rem">更新</button>
    </div>
  </main>

  <script>
    async function loadStats() {
      const r = await fetch('/api/stats');
      const d = await r.json();
      document.getElementById('stat-total').textContent = d.total_records ?? '―';
      document.getElementById('stat-days').textContent = d.days ?? '―';
      document.getElementById('stat-venues').textContent = d.venues ?? '―';
      document.getElementById('stat-models').textContent = d.models ?? '―';
    }

    async function predict() {
      const venue = document.getElementById('venue').value;
      const race  = document.getElementById('race').value;
      const r = await fetch(`/api/predict?venue=${venue}&race=${race}`);
      const d = await r.json();
      const tbody = document.getElementById('pred-table');
      tbody.innerHTML = '';
      d.predictions.forEach((p, i) => {
        const tr = document.createElement('tr');
        if (i === 0) tr.className = 'top1';
        const conf = p.confidence === '高' ? 'high' : p.confidence === '中' ? 'mid' : 'low';
        tr.innerHTML = `<td>${p.boat}</td><td>${(p.win_prob*100).toFixed(1)}%</td><td class="${conf}">${p.confidence}</td>`;
        tbody.appendChild(tr);
      });
      document.getElementById('method-label').textContent = `予測手法: ${d.method}  / 上位3艇: ${d.top3.join(' → ')}`;
      document.getElementById('result-box').style.display = 'block';
    }

    async function loadToday() {
      const grid = document.getElementById('today-grid');
      grid.innerHTML = '<p style="color:#94a3b8">読み込み中...</p>';
      const r = await fetch('/api/today');
      const data = await r.json();
      grid.innerHTML = '';
      data.forEach(item => {
        const card = document.createElement('div');
        card.style.cssText = 'background:#0f172a;border-radius:0.5rem;padding:1rem;';
        card.innerHTML = `<div style="font-weight:700;margin-bottom:0.5rem">会場${item.venue_code} R${item.race_number}</div>
          <div>予想: ${item.top3.join(' → ')}</div>
          <div style="color:#60a5fa;font-size:0.85rem">信頼度: ${(item.confidence_score*100).toFixed(0)}%</div>`;
        grid.appendChild(card);
      });
    }

    loadStats();
    loadToday();
  </script>
</body>
</html>
"""


# ------------------------------------------------------------------
# API routes
# ------------------------------------------------------------------

@app.route("/")
def index():
    return render_template_string(_DASHBOARD_HTML)


@app.route("/api/stats")
def api_stats():
    """データ統計を返す。"""
    stats = {"total_records": 0, "days": 0, "venues": 0, "models": 0}

    csv_path = "data/all_races.csv"
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            stats["total_records"] = len(df)
            if "date" in df.columns:
                stats["days"] = df["date"].nunique()
            if "venue_code" in df.columns:
                stats["venues"] = df["venue_code"].nunique()
        except Exception as exc:
            logger.warning("CSV 読み込みエラー: %s", exc)

    model_dir = "models"
    if os.path.exists(model_dir):
        stats["models"] = len([f for f in os.listdir(model_dir) if f.endswith(".pkl")])

    return jsonify(stats)


@app.route("/api/predict")
def api_predict():
    """1レースの予想を返す。"""
    try:
        venue = int(request.args.get("venue", 3))
        race = int(request.args.get("race", 1))
        predictor = _get_predictor()
        if predictor is None:
            return jsonify({"error": "モデルが利用できません"}), 503
        result = predictor.predict_race(venue, race)
        return jsonify(result)
    except Exception as exc:
        logger.error("predict error: %s", exc)
        return jsonify({"error": "予想処理に失敗しました"}), 500


@app.route("/api/today")
def api_today():
    """全24会場の第1レース予想を返す。"""
    try:
        predictor = _get_predictor()
        if predictor is None:
            return jsonify({"error": "モデルが利用できません"}), 503
        results = [predictor.predict_race(v, 1) for v in range(1, 25)]
        return jsonify(results)
    except Exception as exc:
        logger.error("today error: %s", exc)
        return jsonify({"error": "本日の予想取得に失敗しました"}), 500


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main():
    port = int(os.environ.get("PORT", 8080))
    logger.info("ダッシュボードを起動します → http://0.0.0.0:%d", port)
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
