@echo off
REM ボートレース予測システム - 当日・翌日予想実行スクリプト
cd /d "%~dp0"
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo.
    echo ========================================
    echo 当日予想
    echo ========================================
    python main.py --mode predict-today
    echo.
    echo ========================================
    echo 翌日予想
    echo ========================================
    python main.py --mode predict-tomorrow
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
