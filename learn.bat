@echo off
REM ボートレース予測システム - 学習実行スクリプト
cd /d "%~dp0"
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo.
    echo ========================================
    echo モデル再学習を実行中...
    echo ========================================
    python << 'EOF'
from models.ensemble_model import EnsembleModel
import json

model = EnsembleModel()
result = model.retrain()

print("\n学習結果:")
for key, value in result.items():
    print(f"  {key}: {value}")

print("\nパフォーマンス評価:")
performance = model.evaluate_performance()
for key, value in performance.items():
    if isinstance(value, float):
        print(f"  {key}: {value:.1%}" if key in ["accuracy", "precision", "recall", "f1_score", "recovery_rate"] else f"  {key}: {value}")
    else:
        print(f"  {key}: {value}")
EOF
    echo.
    pause
) else (
    echo エラー: 仮想環境が見つかりません
    echo 次のコマンドを実行してください:
    echo python -m venv venv
    echo venv\Scripts\activate.bat
    echo pip install -r requirements.txt
    pause
)
