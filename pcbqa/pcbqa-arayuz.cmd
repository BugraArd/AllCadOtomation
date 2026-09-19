@echo off
rem ============================================================================
rem  pcbqa - masaustu arayuzu baslaticisi (kisayolun hedefi budur)
rem
rem  NEDEN AYRI BIR BASLATICI VAR
rem
rem  `pcbqa.cmd` yorumlayici olarak ONCE KiCad'inkini secer - dogru karar,
rem  cunku pcbqa'nin baska bagimliligi yok ve KiCad zaten kurulu olmak
rem  zorunda. Ama OLCULDU:
rem
rem    "C:\Program Files\KiCad\10.0\bin\python.exe" -c "import tkinter"
rem    -> ModuleNotFoundError: No module named '_tkinter'
rem
rem  KiCad kendi Python'unu Tk OLMADAN paketliyor; arayuz onunla acilamaz.
rem  Bu dosya bu yuzden ayri: tkinter'i GERCEKTEN olan bir Python arar -
rem  varsaymaz, her adayi calistirip sinar.
rem
rem  ADAYLARIN NEDEN CALISTIRILARAK SINANDIGI
rem
rem  `if exist` yetmiyor. Olculdu: bu makinede PATH'teki `python`, Microsoft
rem  Store takma adi; `sys.executable` "C:\Program Files\WindowsApps\..."
rem  altini gosteriyor ve o klasorun ACL'si yuzunden `if exist` YANLIS olarak
rem  "yok" diyor. Bu yuzden hem tkinter hem pythonw denetimi, adayi gercekten
rem  CALISTIRIP cikis koduna bakarak yapiliyor.
rem
rem  Konsol penceresi acilmasin diye `pythonw.exe` tercih edilir; ama tkinter
rem  sinamasi `python.exe` ile yapilir, cunku pythonw'nun cikti kanali yoktur
rem  ve bir hata sessizce kaybolurdu.
rem
rem  Kullanim:  pcbqa-arayuz.cmd  [--proje <klasor>]
rem ============================================================================
setlocal EnableDelayedExpansion

set "PCBQA_HOME=%~dp0"
if "%PCBQA_HOME:~-1%"=="\" set "PCBQA_HOME=%PCBQA_HOME:~0,-1%"

set "TKPY="
set "PYW="

rem --- Yorumlayici: tkinter'i olan ILK aday ------------------------------------
rem KiCad'in python.exe'si BILEREK denenmiyor (yukaridaki olcum).
if defined PCBQA_PYTHON call :dene_tk "%PCBQA_PYTHON%"
if not defined TKPY call :dene_tk "%PCBQA_HOME%\.venv\Scripts\python.exe"
if not defined TKPY call :dene_tk "py"
if not defined TKPY call :dene_tk "python"
if not defined TKPY call :dene_tk "python3"
if not defined TKPY goto :yok

rem --- Konsolsuz ikiz: SECILEN yorumlayicinin kendi pythonw'su ------------------
rem
rem  PATH'teki `pythonw`a DUSULMEZ, bilerek. Olculdu: bu makinede secilen
rem  yorumlayici projenin .venv'i, ama PATH'teki `pythonw` Microsoft Store
rem  takma adi - bambaska bir kurulum. Ilk surum ona dusuyordu ve `start`
rem  onu calistiramadigi icin arayuz SESSIZCE hic acilmiyordu (cikis kodu 0).
rem  tkinter'i sinadigimiz yorumlayici ile arayuzu acan yorumlayici AYNI olmali.
rem
rem  Yol, ara dosyayla okunuyor - `for /f "usebackq"` icindeki ic ice tirnaklar
rem  cmd'de guvenilir cozumlenmiyor (ayni olcum: dongu hic sonuc uretmedi).
set "PYWLIST=%TEMP%\pcbqa-pyw-%RANDOM%%RANDOM%.txt"
"%TKPY%" -c "import os,sys;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))" >"%PYWLIST%" 2>nul
set "PYWCAND="
if exist "%PYWLIST%" set /p PYWCAND=<"%PYWLIST%"
del "%PYWLIST%" >nul 2>&1
if defined PYWCAND call :dene_w "%PYWCAND%"

rem --- Tanilama: neyi sectigimizi gosterip cik ---------------------------------
rem Kisayol calismadiginda ilk sorulacak soru "hangi Python?" oldugu icin var.
if /i "%~1"=="--nerede" (
    echo pcbqa arayuz - secilen yorumlayicilar
    echo   ev klasoru : %PCBQA_HOME%
    echo   tkinter'li : %TKPY%
    if defined PYW (echo   konsolsuz  : %PYW%) else (echo   konsolsuz  : YOK - konsollu acilacak)
    exit /b 0
)

if defined PYW (
    start "" "%PYW%" "%PCBQA_HOME%\baslat.py" arayuz %*
    exit /b 0
)

rem pythonw bulunamadi: konsollu surumle ac - arayuzun hic acilmamasindan iyi.
echo not: konsolsuz pythonw bulunamadi, arayuz bu pencereden aciliyor.
"%TKPY%" "%PCBQA_HOME%\baslat.py" arayuz %*
exit /b %ERRORLEVEL%

rem ---------------------------------------------------------------------------
:dene_tk
"%~1" -c "import tkinter" >nul 2>&1
if not errorlevel 1 set "TKPY=%~1"
exit /b 0

:dene_w
rem pythonw sessizdir; varligini CIKIS KODUYLA dogruluyoruz.
"%~1" -c "raise SystemExit(0)" >nul 2>&1
if not errorlevel 1 set "PYW=%~1"
exit /b 0

:yok
echo hata: tkinter'i olan bir Python bulunamadi - arayuz acilamaz. 1>&2
echo. 1>&2
echo   Sebep olculdu: KiCad kendi Python'unu getiriyor ama icinde tkinter YOK 1>&2
echo   (KiCad 10.0.4). Arayuz icin ayri bir Python gerekiyor. 1>&2
echo. 1>&2
echo   1) python.org'dan Python kurun ("tcl/tk" secili kalsin), ya da 1>&2
echo   2) elinizdeki bir Python'u gosterin: 1>&2
echo        set PCBQA_PYTHON=C:\Python313\python.exe 1>&2
echo. 1>&2
echo   Arayuz olmadan ayni isler komut satirindan yapilabilir: 1>&2
echo        pcbqa yap "10 adet kapasitor ekle" 1>&2
echo        pcbqa parcalar ^<sematik^> 1>&2
echo. 1>&2
pause
exit /b 2
