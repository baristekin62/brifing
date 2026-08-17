@echo off
REM ============================================================
REM  OZEN BRIFING - PAKET KURULUMU
REM  Yeni PC'ye geciste bu dosyayi calistirin.
REM  Kurulacaklar:
REM   1) Python paketleri (flask, pyodbc, openpyxl)
REM   2) ODBC Driver 18 for SQL Server (yoksa otomatik kurulum)
REM   3) .env gizli deger olusturmasi (sifreler burada tutulur)
REM   4) Panel baslatma testi
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo  OZEN BRIFING - PAKET KURULUMU
echo  Klasor: %CD%
echo ============================================================
echo.

REM ---------- 0) .env kontrolu ----------
echo [0/4] Gizli degerler (.env) kontrol ediliyor...
if not exist ".env" (
    if exist "config.json" (
        echo  .env bulunamadi ama config.json mevcut.
        echo  Lutfen .env dosyasini olusturun:
        echo    ADMIN_PASSWORD=panel_giris_sifresi
        echo    ERP_PASSWORD=erp_sifresi
        echo    SMTP_PASSWORD=smtp_sifresi
        echo  (Detay: README.md / KURULUM.md)
        echo.
        pause
        exit /b 1
    )
    copy /y "config.example.json" "config.json" >nul
    copy /y "erp_connection.example.json" "erp_connection.json" >nul
    copy /y "smtp_profiles.example.json" "smtp_profiles.json" >nul
    echo  Sablon config dosyalari olusturuldu.
    echo  Simdi .env dosyasi olusturup gercek degerleri girin:
    echo    ADMIN_PASSWORD=panel_giris_sifresi
    echo    ERP_PASSWORD=erp_sifresi
    echo    SMTP_PASSWORD=smtp_sifresi
    echo.
    pause
    exit /b 1
)
echo  .env mevcut.

REM ---------- 1) Python kontrolu ----------
echo [1/4] Python kontrol ediliyor...
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo  HATA: Python bulunamadi!
    echo  Lutfen once https://www.python.org/downloads/ adresinden Python 3 kurun.
    echo  Kurulumda "Add Python to PATH" secenegini ISARETLEYIN.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  Python bulundu: !PYVER!

REM ---------- 2) Python paketleri ----------
echo.
echo [2/4] Python paketleri kuruluyor (flask, pyodbc, openpyxl)...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo  HATA: Paket kurulumu basarisiz oldu.
    echo.
    pause
    exit /b 1
)
echo  Paketler kuruldu.

REM ---------- 3) ODBC surucu kontrolu ----------
echo.
echo [3/4] ODBC surucusu kontrol ediliyor...
set ODBC_OK=0
reg query "HKLM\SOFTWARE\ODBC\ODBCINST.INI\ODBC Driver 18 for SQL Server" >nul 2>&1
if not errorlevel 1 set ODBC_OK=1
reg query "HKLM\SOFTWARE\ODBC\ODBCINST.INI\ODBC Driver 17 for SQL Server" >nul 2>&1
if not errorlevel 1 set ODBC_OK=1

if "%ODBC_OK%"=="1" (
    echo  ODBC Driver 17/18 for SQL Server kurulu.
) else (
    echo  ODBC surucusu bulunamadi. Surucu otomatik kuruluyor...
    powershell -Command "Start-Process msiexec -ArgumentList '/i', 'https://go.microsoft.com/fwlink/?linkid=2249005', '/quiet', '/norestart' -Wait -Verb RunAs"
    reg query "HKLM\SOFTWARE\ODBC\ODBCINST.INI\ODBC Driver 18 for SQL Server" >nul 2>&1
    if errorlevel 1 (
        echo  UYARI: ODBC Driver 18 kurulumu tamamlanamadi.
        echo  Lutfen elinizle kurun:
        echo  https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server
        echo  SQL Server baglantisi icin ODBC 17 veya 18 zorunludur.
    ) else (
        echo  ODBC Driver 18 kuruldu.
    )
)

REM ---------- 4) Panel testi ----------
echo.
echo [4/4] Panel test ediliyor...
python -c "from app import app; print('Uygulama yuklendi: OK')"
if errorlevel 1 (
    echo.
    echo  HATA: Uygulama yuklenemedi. Config dosyalarini kontrol edin.
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  KURULUM TAMAMLANDI!
echo.
echo  Sonraki adimlar:
echo   1) baslat_panel.bat ile paneli baslatin (http://127.0.0.1:8080)
echo   2) GIRIS: config.json icindeki admin_username / admin_password
echo   3) Profiller sayfasindan saatleri yeniden kaydedin
echo      (Gorev Zamanlayici kayitlari yeni PC'ye tasinmaz,
echo       kaydetmek otomatik yeniden kurar)
echo   4) ERP ve SMTP baglantilarini Ayarlar sayfasindan test edin
echo ============================================================
echo.
pause
