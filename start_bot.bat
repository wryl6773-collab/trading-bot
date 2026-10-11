@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Debug mode: the bot runs with a visible console. Normal start: use the desktop icon.
python app.py
pause
