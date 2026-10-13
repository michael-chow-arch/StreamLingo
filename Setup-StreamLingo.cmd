@echo off
setlocal
pushd "%~dp0" || exit /b 1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup.ps1" %*
set "streamlingoExitCode=%errorlevel%"
if not "%streamlingoExitCode%"=="0" echo Setup did not finish. Read the message above and try again.
pause
popd
exit /b %streamlingoExitCode%
