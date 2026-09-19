@echo off
rem ============================================================================
rem  pcbqa - bagimsiz uygulama baslaticisi
rem
rem  Ayri bir Python KURULUMU GEREKTIRMEZ: KiCad kendi Python'unu getiriyor ve
rem  pcbqa'nin calisma zamani bagimliligi yok (bkz. pcbqa/confload.py). KiCad
rem  zaten kurulu olmak zorunda - netlist/ERC/DRC icin kicad-cli, bilesenler
rem  icin sembol ve footprint kutuphaneleri oradan geliyor.
rem
rem  Yorumlayici sirasi:
rem    1) PCBQA_PYTHON       - kullanici acikca soylediyse
rem    2) KiCad'in kendi python.exe'si (yeni surumden eskiye)
rem    3) PATH uzerindeki python
rem
rem  Kullanim:  pcbqa <komut> [secenekler]      ilk kez:  pcbqa tani
rem ============================================================================
setlocal EnableDelayedExpansion

set "PCBQA_HOME=%~dp0"
if "%PCBQA_HOME:~-1%"=="\" set "PCBQA_HOME=%PCBQA_HOME:~0,-1%"

if defined PCBQA_PYTHON (
    if exist "%PCBQA_PYTHON%" goto :run
    echo hata: PCBQA_PYTHON gosterilen yerde yok: "%PCBQA_PYTHON%" 1>&2
    exit /b 2
)

rem --- KiCad'in Python'u: yeni surumden eskiye ---------------------------------
for %%V in (10.0 9.0 8.0 7.0) do (
    for %%R in ("%ProgramFiles%" "%ProgramFiles(x86)%" "%LOCALAPPDATA%\Programs") do (
        if not defined PCBQA_PYTHON (
            if exist "%%~R\KiCad\%%V\bin\python.exe" (
                set "PCBQA_PYTHON=%%~R\KiCad\%%V\bin\python.exe"
            )
        )
    )
)
if defined PCBQA_PYTHON goto :run

rem --- Son care: PATH uzerindeki python ---------------------------------------
for /f "delims=" %%P in ('where python 2^>nul') do (
    if not defined PCBQA_PYTHON set "PCBQA_PYTHON=%%P"
)
if defined PCBQA_PYTHON goto :run

echo hata: calistirilacak bir Python bulunamadi. 1>&2
echo. 1>&2
echo   pcbqa KiCad'in kendi Python'uyla calisir. Once KiCad'i kurun. 1>&2
echo   Baska bir yorumlayici kullanmak icin PCBQA_PYTHON ayarlayin: 1>&2
echo     set PCBQA_PYTHON=C:\Program Files\KiCad\10.0\bin\python.exe 1>&2
exit /b 2

:run
rem Paketi `baslat.py` uzerinden cagiriyoruz, `-m pcbqa.app` ile DEGIL.
rem Sebep olculmus: KiCad'in sitecustomize.py'si site asamasinda `sys.path = []`
rem yapiyor, yani PYTHONPATH yok sayiliyor; `-m` ise yalnizca CALISMA DIZINI
rem paket klasoruyken ise yariyordu. Ayrinti: baslat.py basligi.
"%PCBQA_PYTHON%" "%PCBQA_HOME%\baslat.py" %*
exit /b %ERRORLEVEL%
