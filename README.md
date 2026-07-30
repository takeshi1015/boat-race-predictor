# Boat Race Predictor 🚤

自動ボートレース予測システム - 機械学習と強化学習を組み合わせた高精度予測ツール

## 📋 目次

- [機能](#機能)
- [システム構成](#システム構成)
- [インストール](#インストール)
- [設定](#設定)
- [使用方法](#使用方法)
- [アーキテクチャ](#アーキテクチャ)
- [トラブルシューティング](#トラブルシューティング)

## ✨ 機能

### 予測機能
- **複数モデルアンサンブル**: ニューラルネットワーク、XGBoost、ランダムフォレストを組み合わせた予測
- **信頼度スコア**: 各予測に対する確信度を計算
- **リアルタイム予測**: 当日・翌日の予測を自動実行
- **強化学習**: Q学習によるモデルの継続的な改善

### 通知機能
- **メール通知**: 高精度予測結果をメール送信
- **LINE通知**: LINE Notifyによるリアルタイム通知
- **カスタマイズ可能な閾値**: 信頼度と配当に基づくフィルタリング

### 分析機能
- **パフォーマンス分析**: 予測精度の追跡と分析
- **精度アラート**: 精度低下時の自動通知
- **データビジュアライゼーション**: Plotlyによる対話的なグラフ表示

### スケジューリング
- **自動スケジューリング**: APSchedulerによる定時実行
- **カスタマイズ可能な実行時間**: 環境変数で実行スケジュールを設定
- **ジョブログ**: 全ジョブの実行履歴を記録

## 🏗️ システム構成

```
boat-race-predictor/
├── main.py                 # アプリケーションエントリーポイント
├── config.py              # 設定管理
├── requirements.txt       # Python依存関係
├── .env.example          # 環境変数テンプレート
├── scripts/
│   ├── fetch_real_races.py    # 公式サイトから実レースデータ取得
│   └── init_test_data.py      # テストデータ生成（非推奨：本番運用では使用しない）
├── scheduler/
│   └── task_scheduler.py  # タスクスケジューラー
├── scrapers/
│   ├── boat_race_scraper.py  # データスクレイピング
│   └── official_scraper.py   # 公式サイトスクレップ
├── models/
│   ├── ensemble_model.py   # アンサンブルモデル
│   ├── neural_network.py   # ニューラルネットワーク
│   └── reinforcement_learner.py  # 強化学習
├── notifiers/
│   ├── email_notifier.py   # メール通知
│   ├── line_notifier.py    # LINE通知
│   └── telegram_notifier.py # Telegram通知
├── utils/
│   ├── logger.py          # ロギング設定
│   ├── venue_manager.py   # レース場の開催情報管理
│   ├── database.py        # データベース接続
│   └── helpers.py         # ユーティリティ関数
└── tests/
    ├── test_models.py     # モデルテスト
    └── test_scrapers.py   # スクレイパーテスト
```

## 🚀 インストール

### 前提条件
- Python 3.8以上
- SQLite（デフォルト）またはPostgreSQL 12以上

### セットアップ手順

1. **リポジトリをクローン**
```bash
git clone https://github.com/takeshi1015/boat-race-predictor.git
cd boat-race-predictor
```

2. **仮想環境を作成して有効化**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# または
venv\Scripts\activate  # Windows
```

3. **依存関係をインストール**
```bash
pip install -r requirements.txt
```

4. **環境変数を設定**
```bash
cp .env.example .env
# .envファイルを編集して設定値を入力
```

## ⚙️ 設定

### 環境変数の設定

`.env`ファイルを編集して以下を設定します：

#### データベース
```env
DATABASE_URL=sqlite:///boat_race.db
```

#### メール通知
```env
USE_EMAIL=True
EMAIL_ADDRESS=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_RECIPIENTS=recipient1@example.com,recipient2@example.com
```

#### LINE通知
```env
USE_LINE=True
LINE_NOTIFY_TOKEN=your_line_notify_token
```

#### スケジューリング
```env
SCHEDULE_TODAY=06:00        # 当日予測実行時刻
SCHEDULE_TOMORROW=18:00     # 翌日予測実行時刻
SCHEDULE_EVALUATE=23:30     # 評価実行時刻
```

#### 機械学習設定
```env
EPOCHS=50
BATCH_SIZE=32
LEARNING_RATE=0.001
NN_DROPOUT_RATE=0.3
```

## 💻 使用方法

### 🔴 重要: 本番運用モード（推奨）

#### 1. 実レースデータを公式サイトから取得
```bash
python scripts/fetch_real_races.py
```
- ボートレース公式サイト (boatrace.jp) から実レースデータを自動取得
- 当日と翌日のレースデータをDBに保存
- データは自動的にリアルタイムで更新

#### 2. 当日予測を実行
```bash
python main.py --mode predict-today
```
- 本日開催中のレース場のみを表示
- 購入可能なレースのみを対象（開始10分前まで購入可能）
- 信頼度70%以上の高精度予測をハイライト

#### 3. 翌日予測を実行
```bash
python main.py --mode predict-tomorrow
```
- 翌日開催予定のレース場のみを表示
- すべてのレースが対象（購入締め切り確認なし）

### 起動方法

#### 1. 起動オプションを表示
```bash
python main.py
```

#### 2. パフォーマンス分析を実行
```bash
python main.py --mode analyze
```

#### 3. モデルの再トレーニング
```bash
python main.py --mode retrain
```

#### 4. 統計情報を表示
```bash
python main.py --mode stats
```

#### 5. Web UI を起動（ブラウザからアクセス）
```bash
python main.py --mode run-server
# → http://localhost:5000/ でアクセス可能
```

Web UI 機能：
- ダッシュボード（統計情報表示）
- 当日予想表示（レスポンシブ）
- 翌日予想表示
- 的中率分析
- 設定画面

#### 6. 連続実行モード（スケジューラー）
```bash
python main.py --mode run
```
スケジューラーが起動し、設定された時間に自動的にタスクを実行します。

### デバッグモード
```bash
python main.py --debug
```

## 🏛️ アーキテクチャ

### 予測パイプライン

```
公式サイトから実レースデータ取得
    ↓
レース場の開催情報を取得（リアルタイム）
    ↓
開催中のレース場のみをフィルタリング
    ↓
購入可能なレースのみを対象（当日のみ）
    ↓
複数モデルによる予測
├─ ニューラルネットワーク
├─ XGBoost
└─ ランダムフォレスト
    ↓
アンサンブル（重み付き平均）
    ↓
信頼度スコア計算
    ↓
通知・保存
```

### 強化学習（Q学習）

モデルの重みを動的に調整し、予測精度に基づいて学習を継続します。

## 📊 予測結果の理解

### 信頼度スコア
- **0.8以上**: 非常に高い信頼度
- **0.6～0.8**: 高い信頼度
- **0.4～0.6**: 中程度の信頼度
- **0.4未満**: 低い信頼度（推奨なし）

### 通知フィルター
- `HIGH_CONFIDENCE_RACES`: 信頼度の高い上位N件のレースのみ通知
- `HIGH_ODDS_RACES`: 配当の高い上位N件のレースのみ通知

## 🔧 トラブルシューティング

### 非開催のレース場が表示される
```
❌ 児島競艇場が表示されているが、公式サイトでは開催していない
```
**解決策**: 
1. `python scripts/fetch_real_races.py` を再実行して最新データを取得
2. VenueManagerが公式サイトから正しく開催情報を取得しているか確認
3. `rm boat_race.db` でDBをリセットしてから再度実行

### レースデータが取得されない
```
Error: Failed to fetch races from official site
```
**解決策**: 
1. インターネット接続を確認
2. boatrace.jpが正常にアクセスできるか確認
3. requests と BeautifulSoup がインストールされているか確認
4. User-Agentがブロックされていないか確認

### データベース接続エラー
```
Error: could not connect to server
```
**解決策**: SQLiteの場合は自動作成されます。PostgreSQLの場合は接続情報を確認

### メール送信エラー
```
Error: SMTP authentication failed
```
**解決策**: Gmailの場合、アプリパスワードを使用してください

### モデル予測エラー
```
Error: Model prediction failed
```
**解決策**: 必要なモデルファイルが存在するか、またはモデルの再トレーニングが必要です

## 📝 ログ

ログファイルは `logs/boat_race_predictor.log` に保存されます。

```bash
# ログの確認
tail -f logs/boat_race_predictor.log

# デバッグレベルのログを表示
python main.py --debug
```

## 🧪 テスト

```bash
# 全テストを実行
pytest

# カバレッジ付きで実行
pytest --cov=. --cov-report=html

# 特定のテストを実行
pytest tests/test_models.py -v
```

## 📈 パフォーマンス最適化

1. **バッチ処理**: 大量のレースデータはバッチで処理
2. **キャッシング**: 頻繁にアクセスするデータをキャッシュ
3. **非同期処理**: I/Oバウンドな操作は非同期実行
4. **インデックス**: データベースのインデックスを最適化

## 🤝 貢献

改善提案やバグ報告は、GitHubのIssueで受け付けています。

## 📄 ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 🙏 謝辞

本プロジェクトは以下のライブラリを使用しています：
- TensorFlow / Keras
- scikit-learn
- XGBoost
- APScheduler
- requests
- BeautifulSoup4

## 📞 サポート

問題が発生した場合は、以下をご確認ください：

1. `.env`ファイルの設定が正しいか
2. 依存パッケージがすべてインストールされているか
3. ボートレース公式サイト (boatrace.jp) にアクセスできるか
4. ログファイルにエラーメッセージがないか

---

**最終更新**: 2026年7月30日
