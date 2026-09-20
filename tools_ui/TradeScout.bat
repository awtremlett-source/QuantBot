@echo off
REM TradeScout -- the MANUAL paper-trading app (a decision aid; it never trades).
REM
REM Lives in tools_ui/, NOT tools/: tools/ is engine territory and the engine
REM must never gain a UI dependency.
REM
REM Interpreter: the UI venv if it exists, else the system Python 3.13. Plain
REM "python" is deliberately NOT used -- on this machine it can resolve to the
REM engine's .venv, which has no PySide6 and must never get one.
cd /d "%~dp0.."
set "UI_PYTHON=%~dp0..\.venv-ui\Scripts\python.exe"
if exist "%UI_PYTHON%" (
    "%UI_PYTHON%" -m manual.app
) else (
    py -3.13 -m manual.app
)
if errorlevel 1 pause
