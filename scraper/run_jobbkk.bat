@echo off
REM Start the JobBKK harvester; restart after a crash (not after a block-stop).
cd /d "%~dp0.."
set BK_DELAY=5
set BK_REDISCOVER_HOURS=24
set PY=
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set PY="%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not defined PY where py >nul 2>nul && set PY=py -3
if not defined PY where python >nul 2>nul && set PY=python
if not defined PY (
  echo Python not found. Install Python 3.11+ from python.org and tick "Add to PATH".
  pause
  exit /b 1
)
echo Using Python: %PY%
:loop
echo Starting harvester... (log: data\harvester_jobbkk.log)
%PY% -X utf8 scraper\jobbkk_harvester.py run
set CODE=%errorlevel%
if "%CODE%"=="2" goto blocked
echo.
echo Harvester exited with code %CODE%. See data\harvester_jobbkk.log for the reason.
echo Restarting in 60 seconds... press Ctrl+C to quit.
"%SystemRoot%\System32\timeout.exe" /t 60
goto loop
:blocked
echo Stopped: the site blocked requests 3 times. Wait a day, then raise BK_DELAY.
pause
