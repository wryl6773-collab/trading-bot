@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === יוצר קובץ ZIP לשיתוף (בלי הנתונים והכסף הווירטואלי שלך) ===
set TMP_DIR=%TEMP%\TradingBot_share
if exist "%TMP_DIR%" rmdir /s /q "%TMP_DIR%"
mkdir "%TMP_DIR%\TradingBot"
for %%F in (*.py *.html *.vbs *.ps1 *.ico *.md *.txt setup.bat start_bot.bat) do copy /Y "%%F" "%TMP_DIR%\TradingBot\" >nul
if exist TradingBot_share.zip del TradingBot_share.zip
powershell -NoProfile -Command "Compress-Archive -Path '%TMP_DIR%\TradingBot' -DestinationPath '%~dp0TradingBot_share.zip' -Force"
rmdir /s /q "%TMP_DIR%"
echo.
echo === מוכן: TradingBot_share.zip נמצא בתיקייה הזאת. ===
pause
