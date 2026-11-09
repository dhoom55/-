@echo off
chcp 65001 >nul
cd /d "%~dp0"
python save_to_desktop.py || py save_to_desktop.py
pause
