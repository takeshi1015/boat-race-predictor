"""
アプリケーション動作確認スクリプト
データベース接続、テストデータの存在確認、予測実行を確認します。
"""

import sys
import os
import re
import subprocess

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from utils.logger import setup_logger

logger = setup_logger(__name__)


def check_database_connection():
    """データベース接続を確認"""
    print("\n[1/3] データベース接続確認...")
    try:
        from database.db_manager import get_db_manager
        db = get_db_manager()
        session = db.get_session()
        session.close()
        print("  ✅ データベース接続成功")
        return True
    except Exception as e:
        print(f"  ❌ データベース接続失敗: {e}")
        return False


def check_test_data():
    """テストデータの存在を確認"""
    print("\n[2/3] テストデータ確認...")
    try:
        from database.db_manager import get_db_manager
        db = get_db_manager()
        session = db.get_session()
        try:
            races = db.get_races_by_date(session, datetime.now())
            count = len(races)
            if count >= 5:
                print(f"  ✅ 当日のレースデータ: {count}件 (5件以上)")
                for r in races:
                    print(f"     - {r.race_id}: {r.venue} 第{r.race_number}R")
                return True
            else:
                print(f"  ❌ 当日のレースデータが不足: {count}件 (5件必要)")
                print("  → scripts/init_test_data.py を実行してください")
                return False
        finally:
            session.close()
    except Exception as e:
        print(f"  ❌ テストデータ確認失敗: {e}")
        return False


def run_predict_today():
    """predict-todayモードで予測を実行"""
    print("\n[3/3] 予測実行確認...")
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cmd = [sys.executable, "main.py", "--mode", "predict-today", "--debug"]

    try:
        result = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=60
        )

        output = result.stdout + result.stderr
        print("  --- 出力 ---")
        for line in output.split('\n'):
            if line.strip():
                print(f"  {line}")
        print("  -----------")

        if result.returncode == 0:
            print("  ✅ 予測実行成功")
            # 期待される出力を確認
            if "当日予測完了" in output:
                match = re.search(r'当日予測完了: (\d+)レース', output)
                if match:
                    count = int(match.group(1))
                    print(f"  📊 予測完了レース数: {count}件")
                    if count >= 5:
                        print("  ✅ 5件以上のレースが予測されました")
                        return True
                    else:
                        print(f"  ⚠️  予測レース数が少ない: {count}件")
                        return False
            return True
        else:
            print(f"  ❌ 予測実行失敗 (終了コード: {result.returncode})")
            return False
    except subprocess.TimeoutExpired:
        print("  ❌ タイムアウト (60秒超過)")
        return False
    except Exception as e:
        print(f"  ❌ 予測実行エラー: {e}")
        return False


def main():
    print("=" * 60)
    print("アプリケーション動作確認スクリプト")
    print(f"実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    results = []

    # 1. データベース接続確認
    results.append(check_database_connection())

    # 2. テストデータ確認
    if results[0]:
        results.append(check_test_data())
    else:
        results.append(False)

    # 3. 予測実行確認
    if all(results):
        results.append(run_predict_today())
    else:
        print("\n[3/3] 予測実行確認... スキップ（前の確認が失敗）")
        results.append(False)

    # 結果サマリー
    print("\n" + "=" * 60)
    print("確認結果サマリー")
    print("=" * 60)
    labels = ["データベース接続", "テストデータ存在", "予測実行"]
    for label, ok in zip(labels, results):
        status = "✅" if ok else "❌"
        print(f"  {status} {label}")

    if all(results):
        print("\n✅ すべての確認が成功しました！")
        sys.exit(0)
    else:
        print("\n❌ 一部の確認が失敗しました")
        sys.exit(1)


if __name__ == "__main__":
    main()
