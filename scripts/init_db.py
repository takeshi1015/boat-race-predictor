"""データベース初期化スクリプト."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from database.db_manager import init_db


if __name__ == "__main__":
    init_db()
    print("✅ データベースを初期化しました")
