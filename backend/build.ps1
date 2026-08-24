param(
    [string]$AppName = "RestaurantPOS"
)

# Exit on any error
$ErrorActionPreference = "Stop"

Write-Host "Building Restaurant POS Windows Application" -ForegroundColor Green
Write-Host "==========================================="
Write-Host ""

# Step 1: Build the frontend
Write-Host "Step 1: Building frontend..." -ForegroundColor Cyan
Push-Location ..\frontend
if (!(Test-Path node_modules)) {
    Write-Host "  Installing npm dependencies..."
    npm install
}
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "Frontend build failed!" -ForegroundColor Red
    Pop-Location
    exit 1
}
Pop-Location
Write-Host "  Frontend build complete." -ForegroundColor Green
Write-Host ""

# Step 2: Run PyInstaller
Write-Host "Step 2: Running PyInstaller..." -ForegroundColor Cyan
Write-Host "  App name: $AppName"
Write-Host "  Entry point: run.py"
Write-Host "  Mode: --onedir (fast startup, easy updates)"
Write-Host "  Console: --noconsole (no console window)"
Write-Host ""

# Build the PyInstaller command with all necessary --add-data entries
# These entries tell PyInstaller which files to bundle into the application.
# On Windows, the separator is SEMICOLON (;), not colon (:) — colons are for Unix/macOS.
# Each argument is quoted to prevent PowerShell from interpreting the semicolon as a statement separator.
$PyInstallerCmd = @(
    "pyinstaller",
    "--onedir",                                                    # One-folder build for fast startup and easy updates
    "--noconsole",                                                 # No console window (required for unattended POS)
    "--name=$AppName",                                             # Executable and folder name
    "--add-data=..\frontend\dist;frontend/dist",                 # Built React frontend (SPA assets, JS, CSS)
    "--add-data=.\alembic;backend/alembic",                       # Database migration scripts (from alembic/versions/)
    "--add-data=.\alembic.ini;backend",                           # Alembic configuration for running migrations at startup
    "run.py"                                                       # Entry point
)

Write-Host "PyInstaller flags:"
$PyInstallerCmd | ForEach-Object {
    Write-Host "  $_"
}
Write-Host ""

# Execute PyInstaller
& pyinstaller @PyInstallerCmd
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller build failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Build complete!" -ForegroundColor Green
Write-Host "==========================================="
Write-Host ""
Write-Host "Output directory: $PSScriptRoot\dist\$AppName" -ForegroundColor Yellow
Write-Host ""
Write-Host "To run the application:"
Write-Host "  $PSScriptRoot\dist\$AppName\$AppName.exe"
Write-Host ""
Write-Host "Data will be stored in:"
Write-Host "  %LOCALAPPDATA%\$AppName"
Write-Host ""
