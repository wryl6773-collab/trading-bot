@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === התקנת הבוט ===
echo בודק שפייתון מותקן...
python --version
if errorlevel 1 (
  echo !!! פייתון לא מותקן. התקן מ-python.org ואז הפעל שוב את הקובץ הזה.
  pause
  exit /b 1
)
echo מתקין את הספריות הדרושות...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo !!! ההתקנה נכשלה. צלם את החלון.
  pause
  exit /b 1
)
echo יוצר קיצור דרך עם אייקון בשולחן העבודה...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0make_shortcut.ps1" -Folder "%~dp0"
echo.
echo === מוכן. בשולחן העבודה יש עכשיו אייקון "בוט מסחר". לחיצה כפולה עליו מפעילה את הבוט. ===
pause
