# install.ps1 -- thin bootstrap for the QuantBot installer (two-stage design).
#
# Usage (from the repo root; PowerShell may block unsigned scripts, so run as):
#   powershell -ExecutionPolicy Bypass -File install.ps1            # install
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Verify    # verify only
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall # decommission
#
# Stage 1 (this file): Python 3.13 check, venv bootstrap, pinned deps.
# Stage 2 (tools/installer.py): everything else -- bat generation, DB init/check,
# scheduled tasks, killswitch note, verify report. Idempotent by design.
# NOTE: installing on any machine other than the current one is RUBRIC-GATED --
# read docs/DEPLOY.md first (single-writer law: never two machines with tasks).

param(
    [switch]$Verify,
    [switch]$Uninstall
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$venvPython = Join-Path $root ".venv\Scripts\python.exe"

if ($Verify -or $Uninstall) {
    # Read-only / decommission paths never build anything.
    if (-not (Test-Path $venvPython)) {
        Write-Host "ERROR: no .venv yet -- run install.ps1 (no flags) first."
        exit 1
    }
    if ($Uninstall) { & $venvPython -m tools.installer uninstall; exit $LASTEXITCODE }
    & $venvPython -m tools.installer verify
    exit $LASTEXITCODE
}

# --- Python 3.13 required (py launcher) ---
$pyOk = $false
try {
    & py -3.13 -c "import sys" 2>$null
    if ($LASTEXITCODE -eq 0) { $pyOk = $true }
} catch {
    $pyOk = $false
}
if (-not $pyOk) {
    Write-Host "ERROR: Python 3.13 not found via the 'py' launcher."
    Write-Host "Install it from https://www.python.org/downloads/ (tick the"
    Write-Host "'py launcher' option), then rerun install.ps1."
    exit 1
}

# --- venv bootstrap (reused if present -- idempotent) ---
if (-not (Test-Path $venvPython)) {
    Write-Host "creating .venv (Python 3.13)..."
    & py -3.13 -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: venv creation failed."; exit 1 }
}

Write-Host "installing pinned dependencies..."
& $venvPython -m pip install --quiet -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: pip install failed."; exit 1 }

# --- hand off to stage 2 ---
& $venvPython -m tools.installer install
exit $LASTEXITCODE
