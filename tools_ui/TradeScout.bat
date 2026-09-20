@echo off
REM TradeScout -- the MANUAL paper-trading app (a decision aid; it never trades).
REM
REM Lives in tools_ui/, NOT tools/: tools/ is engine territory and the engine
REM must never gain a UI dependency.
REM
REM INTERPRETER: the pinned UI environment .venv-ui, and nothing else. Plain
REM "python" is deliberately NOT used -- on this machine it can resolve to the
REM engine's .venv, which has no PySide6 and must never get one. A global
REM Python is not used either: its versions drift, and the app's pins conflict
REM with the engine's on purpose (see requirements-ui.txt).
cd /d "%~dp0.."
set "UI_PYTHON=%~dp0..\.venv-ui\Scripts\python.exe"
if not exist "%UI_PYTHON%" (
    echo.
    echo   The UI environment is missing: .venv-ui
    echo.
    echo   Create it once, from the repo root:
    echo       py -3.13 -m venv .venv-ui
    echo       .venv-ui\Scripts\python.exe -m pip install -r requirements-ui.txt
    echo.
    echo   Never install requirements-ui.txt into .venv -- that is the engine's.
    echo.
    pause
    exit /b 1
)
"%UI_PYTHON%" -m manual.app
if errorlevel 1 pause
