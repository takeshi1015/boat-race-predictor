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
├── scheduler/
│   └── task_scheduler.py  # タスクスケジューラー
├── scrapers/
│   ├── boat_race_scraper.py  # データスクレイピング
│   └── official_scraper.py   # 公式サイトスクレイプ
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
│   ├── database.py        # データベース接続
│   └── helpers.py         # ユーティリティ関数
└── tests/
    ├── test_models.py     # モデルテスト
    └── test_scrapers.py   # スクレイパーテスト
```

## 🚀 インストール

### 前提条件
- Python 3.8以上
- PostgreSQL 12以上
- Redis（オプション）

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

5. **データベースを初期化**
```bash
python -m alembic upgrade head
```

## ⚙️ 設定

### 環境変数の設定

`.env`ファイルを編集して以下を設定します：

#### データベース
```env
DATABASE_URL=postgresql://user:password@localhost:5432/boat_race_db
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

### 1. 連続実行モード（デフォルト）
```bash
python main.py --mode run
```
スケジューラーが起動し、設定された時間に自動的にタスクを実行します。

### 2. 当日予測を即座に実行
```bash
python main.py --mode predict-today
```

### 3. 翌日予測を即座に実行
```bash
python main.py --mode predict-tomorrow
```

### 4. パフォーマンス分析を実行
```bash
python main.py --mode analyze
```

### 5. モデルの再トレーニング
```bash
python main.py --mode retrain
```

### デバッグモード
```bash
python main.py --debug
```

## 🏛️ アーキテクチャ

### 予測パイプライン

```
データ取得
    ↓
前処理・特徴量エンジニアリング
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

### データベース接続エラー
```
Error: could not connect to server
```
**解決策**: PostgreSQLが起動しているか、CONNECTION_URLが正しいか確認

### メール送信エラー
```
Error: SMTP authentication failed
```
**解決策**: Gmailの場合、アプリパスワードを使用してください

### スクレイピングエラー
```
Error: Failed to scrape data
```
**解決策**: Webサイトの仕様変更の可能性があります。スクレイパーの更新が必要です

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

## 📞 サポート

問題が発生した場合は、以下をご確認ください：

1. `.env`ファイルの設定が正しいか
2. データベースが起動しているか
3. 必要なPythonパッケージがインストールされているか
4. ログファイルにエラーメッセージがないか

---

**最終更新**: 2026年7月23日
