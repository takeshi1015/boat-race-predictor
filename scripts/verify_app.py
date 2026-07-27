"""
動作確認スクリプト
全機能が正常に動作することを確認します
"""

import sys
import os
import traceback

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check(label: str, func):
    try:
        result = func()
        print(f"  ✅ {label}")
        return True
    except Exception as e:
        print(f"  ❌ {label}: {e}")
        traceback.print_exc()
        return False


def main():
    print()
    print("━" * 50)
    print("ボートレース予測システム 動作確認")
    print("━" * 50)
    print()

    results = []

    # 1. config
    print("【設定】")
    results.append(check("config.py 読み込み", lambda: __import__("config")))
    results.append(check("DATABASE_URL が SQLite", lambda: (
        __import__("config").DATABASE_URL.startswith("sqlite") or None
        or (_ for _ in ()).throw(AssertionError("DATABASE_URL is not SQLite"))
    )))
    print()

    # 2. データベース
    print("【データベース】")
    def check_db():
        from database.db_manager import get_db_manager
        db = get_db_manager()
        session = db.get_session()
        session.close()
    results.append(check("DatabaseManager 初期化", check_db))

    def check_races():
        from database.db_manager import get_db_manager
        from datetime import datetime
        db = get_db_manager()
        session = db.get_session()
        races = db.get_races_by_date(session, datetime.now())
        session.close()
        assert len(races) > 0, f"当日レースが0件です。python scripts/init_test_data.py を実行してください"
        return races
    results.append(check("当日レースデータ存在確認", check_races))
    print()

    # 3. モデル
    print("【予測モデル】")
    def check_today_predict():
        from models.ensemble_model import EnsembleModel
        model = EnsembleModel()
        preds = model.predict_today()
        assert len(preds) > 0, "当日予測が0件"
        return preds
    results.append(check("当日予測", check_today_predict))

    def check_tomorrow_predict():
        from models.ensemble_model import EnsembleModel
        model = EnsembleModel()
        preds = model.predict_tomorrow()
        return preds
    results.append(check("翌日予測", check_tomorrow_predict))

    def check_evaluate():
        from models.ensemble_model import EnsembleModel
        model = EnsembleModel()
        metrics = model.evaluate_performance()
        assert "accuracy" in metrics
        return metrics
    results.append(check("パフォーマンス評価", check_evaluate))

    def check_retrain():
        from models.ensemble_model import EnsembleModel
        model = EnsembleModel()
        result = model.retrain()
        return result
    results.append(check("モデル再学習", check_retrain))
    print()

    # 4. スケジューラー
    print("【スケジューラー】")
    def check_scheduler():
        from scheduler.task_scheduler import TaskScheduler
        scheduler = TaskScheduler()
        return scheduler
    results.append(check("TaskScheduler 初期化", check_scheduler))
    print()

    # 5. Web サーバー
    print("【Web サーバー】")
    def check_flask():
        from app import create_app
        app = create_app()
        client = app.test_client()
        response = client.get("/")
        assert response.status_code == 200
    results.append(check("Flask アプリ起動", check_flask))

    def check_api():
        from app import create_app
        app = create_app()
        client = app.test_client()
        response = client.get("/api/health")
        assert response.status_code == 200
    results.append(check("API /health エンドポイント", check_api))

    def check_api_today():
        from app import create_app
        app = create_app()
        client = app.test_client()
        response = client.get("/api/races/today")
        assert response.status_code == 200
    results.append(check("API /races/today エンドポイント", check_api_today))
    print()

    # サマリー
    passed = sum(results)
    total = len(results)
    print("━" * 50)
    print(f"結果: {passed}/{total} チェック通過")
    if passed == total:
        print("✅ 全て正常に動作しています！")
        print()
        print("以下のコマンドで使用できます：")
        print("  python main.py                          # 起動方法表示")
        print("  python main.py --mode predict-today     # 当日予想")
        print("  python main.py --mode predict-tomorrow  # 翌日予想")
        print("  python main.py --mode analyze           # 的中率分析")
        print("  python main.py --mode retrain           # 学習実行")
        print("  python main.py --mode stats             # 統計表示")
        print("  python main.py --mode run-server        # Web UI起動")
    else:
        print("⚠️  一部のチェックが失敗しました。")
        print("   python scripts/init_test_data.py を実行してください。")
    print("━" * 50)
    print()

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
