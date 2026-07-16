@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: LAAP + Hermes Source Code Integration Rollback Script
:: This script restores the original agent/system_prompt.py from backup

set HERMES_HOME=%~1
if "%HERMES_HOME%"=="" set HERMES_HOME=%LOCALAPPDATA%\hermes\hermes-agent

echo ============================================================
echo  LAAP + Hermes Source Code Integration - Rollback
echo ============================================================
echo Hermes home: %HERMES_HOME%
echo.

:: Check if backup exists
if not exist "%HERMES_HOME%\agent\system_prompt.py.laap-backup" (
    echo Error: Backup file %HERMES_HOME%\agent\system_prompt.py.laap-backup not found!
    echo No LAAP patch was applied or backup was deleted.
    pause
    exit /b 1
)

:: Restore backup
echo Restoring original system_prompt.py from backup...
copy /Y "%HERMES_HOME%\agent\system_prompt.py.laap-backup" "%HERMES_HOME%\agent\system_prompt.py" >nul

echo Rollback completed successfully!
echo Original system_prompt.py has been restored.
echo.
pause
