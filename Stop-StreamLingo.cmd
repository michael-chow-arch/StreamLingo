@echo off
setlocal
pushd "%~dp0" || exit /b 1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop.ps1"
set "streamlingoExitCode=%errorlevel%"
pause
popd
exit /b %streamlingoExitCode%
