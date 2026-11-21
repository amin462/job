@echo off
REM Double-click to (re)start both harvesters. Add -Watch to keep restarting them if they stop.
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_harvesters.ps1" %*
pause
