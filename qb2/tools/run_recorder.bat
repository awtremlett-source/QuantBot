@echo off
REM qb2 intraday recorder -- for running BY HAND.
REM
REM The scheduled task does NOT use this file. It runs pythonw.exe directly, with
REM absolute paths and "Start in" set to the repository, so that no console window
REM ever appears. That matters twice over: the operator was seeing a window titled
REM C:\Windows\System32\cmd.exe every hour, and a visible window is something that
REM can be closed mid-run -- which kills the run.
REM
REM Why System32 was in that title: Task Scheduler starts a task in
REM C:\Windows\system32 when no "Start in" is set. Confirmed by probe on
REM 2026-10-02, not assumed. That is also why the old shared recorder.log never
REM existed anywhere -- the relative path resolved under System32, where it could
REM not be created.
REM
REM The run writes its own log to logs\recorder\run-<timestamp>.log, so there is
REM nothing to redirect here. A log with no "run finished" line is a run that was
REM killed.
REM
REM Catch-up safe: it resumes from each name's last saved bar, so a missed run
REM costs nothing while the gap fits inside the provider's window.
setlocal
cd /d "%~dp0..\.."

set "QB2_PYTHON=%~dp0..\..\.venv-qb2\Scripts\python.exe"
if not exist "%QB2_PYTHON%" (
    echo   The qb2 environment is missing: .venv-qb2
    echo   Create it: py -3.13 -m venv .venv-qb2
    echo              .venv-qb2\Scripts\python.exe -m pip install -r requirements-qb2.txt
    exit /b 1
)

"%QB2_PYTHON%" -m qb2.tools.record_now %*
set "RC=%ERRORLEVEL%"

REM No pause, no "cmd /k": an unattended run has nobody to press a key, and a
REM window left open holds the scheduler's instance slot. The exit code must
REM reach Task Scheduler so a broken run cannot report success.
exit /b %RC%
