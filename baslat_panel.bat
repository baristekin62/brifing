@echo off
cd /d D:\BRIFING
start "" pythonw app.py
echo OZEN Brifing Paneli baslatildi: http://127.0.0.1:8080
timeout /t 3 >nul
start http://127.0.0.1:8080
