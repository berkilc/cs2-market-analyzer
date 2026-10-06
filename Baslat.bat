@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo ========================================================
echo  🎮 CS2 Market Analyzer & Pro Dashboard Baslatiliyor...
echo ========================================================
python gui_app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Bir hata olustu. CS2_Market_Analyzer.exe deneniyor...
    start "" "CS2_Market_Analyzer.exe"
)
