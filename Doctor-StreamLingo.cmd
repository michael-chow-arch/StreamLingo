@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\doctor.ps1"
set "streamlingo_exit=%ERRORLEVEL%"
pause
exit /b %streamlingo_exit%
