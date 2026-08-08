@echo off
REM ボートレース予測システム - セットアップスクリプト
cd /d "%~dp0"

echo.
echo ========================================
echo ボートレース予測システム セットアップ
echo ========================================
echo.

REM 仮想環境の作成
if not exist venv (
    echo [1/4] 仮想環境を作成中...
    python -m venv venv
    if errorlevel 1 (
        echo エラー: 仮想環境の作成に失敗しました
        pause
        exit /b 1
    )
    echo 完了！
) else (
    echo [1/4] 仮想環境は既に存在します
)

echo.

REM 仮想環境の有効化
echo [2/4] 仮想環境を有効化中...
call venv\Scripts\activate.bat
echo 完了！

echo.

REM 依存パッケージのインストール
echo [3/4] 依存パッケージをインストール中...
pip install -r requirements.txt
if errorlevel 1 (
    echo エラー: パッケージのインストールに失敗しました
    pause
    exit /b 1
)
echo 完了！

echo.

REM テストデータの初期化
echo [4/4] テストデータを初期化中...
python scripts/init_test_data.py
if errorlevel 1 (
    echo エラー: テストデータの初期化に失敗しました
    pause
    exit /b 1
)
echo 完了！

echo.
echo ========================================
echo セットアップ完了！
echo ========================================
echo.
echo 次のコマンドで起動できます:
echo   run_server.bat    - Web UI起動
echo   predict.bat       - 当日・翌日予想実行
echo   learn.bat         - モデル学習実行
echo.
pause
