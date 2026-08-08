@echo off
REM ボートレース予測システム - Web UI起動スクリプト
cd /d "%~dp0"
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    python main.py --mode run-server
) else (
    echo エラー: 仮想環境が見つかりません
    echo 次のコマンドを実行してください:
    echo python -m venv venv
    echo venv\Scripts\activate.bat
    echo pip install -r requirements.txt
    pause
)
