@echo off
setlocal
NET SESSION >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo   MUST RUN AS ADMINISTRATOR
    echo   Right-click this file -^> Run as administrator
    echo.
    pause
    exit /b 1
)

echo ============================================
echo   Fixing PostgreSQL Windows Service
echo ============================================
echo.

echo [1/5] Stopping running postgres processes...
taskkill /F /IM postgres.exe >nul 2>&1
timeout /t 3 /nobreak >nul

echo [2/5] Removing stale pid file...
del "C:\pgdata_azad\postmaster.pid" >nul 2>&1

echo [3/5] Stopping service...
sc stop postgresql-x64-18 >nul 2>&1
timeout /t 2 /nobreak >nul

echo [4/5] Pointing service to the real data dir (C:\pgdata_azad, port 5433)...
sc config postgresql-x64-18 binPath= "\"C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe\" runservice -N \"postgresql-x64-18\" -D \"C:\pgdata_azad\" -o \"-p 5433\" -w"

echo [5/5] Starting service...
sc start postgresql-x64-18

echo.
echo ============================================
echo   Result:
sc query postgresql-x64-18 | findstr STATE
echo ============================================
echo.
echo If STATE shows RUNNING, the fix is complete.
echo Your other databases (ERPLite2026, AzadFull2026, azad_uae_test)
echo are untouched - this only changes which folder the service uses.
echo.
pause
