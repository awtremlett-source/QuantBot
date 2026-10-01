@echo off
REM qb2 intraday recorder -- run hourly on weekdays and at logon.
REM
REM Catch-up safe: it always resumes from the last saved bar, so a missed run
REM costs nothing as long as the gap is inside the provider's window (minute
REM bars reach back about 30 days, 8 days per request -- FACTS row n).
REM
REM Uses qb2's OWN environment. Plain "python" is deliberately not used: on this
REM machine it can resolve to v1's .venv, which is frozen.
cd /d "%~dp0..\.."
set "QB2_PYTHON=%~dp0..\..\.venv-qb2\Scripts\python.exe"
if not exist "%QB2_PYTHON%" (
    echo   The qb2 environment is missing: .venv-qb2
    echo   Create it: py -3.13 -m venv .venv-qb2
    echo              .venv-qb2\Scripts\python.exe -m pip install -r requirements-qb2.txt
    exit /b 1
)
"%QB2_PYTHON%" -m qb2.tools.record_now >> "data\raw\intraday\recorder.log" 2>&1
