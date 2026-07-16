@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: LAAP + Hermes Source Code Integration Patch Script
:: This script patches Hermes agent/system_prompt.py to inject LAAP cognitive state

set HERMES_HOME=%~1
if "%HERMES_HOME%"=="" set HERMES_HOME=%LOCALAPPDATA%\hermes\hermes-agent

echo ============================================================
echo  LAAP + Hermes Source Code Integration
echo ============================================================
echo Hermes home: %HERMES_HOME%
echo LAAP API base: http://localhost:11546
echo.

:: Check if Hermes home exists
if not exist "%HERMES_HOME%\agent\system_prompt.py" (
    echo Error: %HERMES_HOME%\agent\system_prompt.py not found!
    echo Please ensure %HERMES_HOME% is the correct Hermes installation directory.
    pause
    exit /b 1
)

:: Check if already patched
findstr /C:"LAAP_COGNITIVE_STATE_INJECTION" "%HERMES_HOME%\agent\system_prompt.py" >nul
if %errorlevel%==0 (
    echo LAAP integration already applied to system_prompt.py
    goto :end
)

:: Create backup
echo [1/3] Creating backup: %HERMES_HOME%\agent\system_prompt.py.laap-backup
copy /Y "%HERMES_HOME%\agent\system_prompt.py" "%HERMES_HOME%\agent\system_prompt.py.laap-backup" >nul

:: Apply patch using Python script
echo [2/3] Applying LAAP patch to system_prompt.py...
python "%~dp0patch_hermes_system_prompt.py" "%HERMES_HOME%"

if %errorlevel%==0 (
    echo [3/3] Patch applied successfully!
    echo.
    echo LAAP cognitive state will now be injected into the volatile system prompt tier.
    echo.
    echo To rollback if needed:
    echo   Copy-Item -Path "%HERMES_HOME%\agent\system_prompt.py.laap-backup" -Destination "%HERMES_HOME%\agent\system_prompt.py" -Force
) else (
    echo Error: Patch failed!
    echo Restoring backup...
    copy /Y "%HERMES_HOME%\agent\system_prompt.py.laap-backup" "%HERMES_HOME%\agent\system_prompt.py" >nul
)

:end
echo.
pause
