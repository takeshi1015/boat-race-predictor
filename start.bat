@echo off
chcp 65001 > nul
echo ========================================
echo  ボートレース予測システム 起動中...
echo ========================================
cd /d %~dp0
python main.py
pause
