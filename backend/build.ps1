param(
    [string]$AppName = "RestaurantPOS"
)

# Exit on any error; all checks must pass
$ErrorActionPreference = "Stop"

# Utility function to print step headers
function Print-Step {
    param([string]$Title)
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
    Write-Host $Title -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
}

function Print-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor Green
}

function Print-Error {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor Red
}

Write-Host "Restaurant POS Build Script" -ForegroundColor Yellow
Write-Host "Starting build at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host ""
Write-Host "NOTE: This script modifies files in c:\dev\my-pos only." -ForegroundColor Gray
Write-Host "      Data in %LOCALAPPDATA%\RestaurantPOS is never touched." -ForegroundColor Gray
Write-Host ""

# ============================================================================
# STEP 1: Build Frontend
# ============================================================================
Print-Step "STEP 1: Build Frontend (React/Vite)"

Push-Location ..\frontend

# Run npm build
Write-Host "Running: npm run build"
npm run build
if ($LASTEXITCODE -ne 0) {
    Print-Error "npm run build failed (exit code: $LASTEXITCODE)"
    Pop-Location
    exit 1
}
Print-Success "npm run build completed with exit code 0"

# ============================================================================
# STEP 2: Verify Frontend Bundle Contents
# ============================================================================
Print-Step "STEP 2: Verify Frontend Bundle"

Write-Host "Checking: dist/assets/*.js contains exactly 1 occurrence of 'Create a category first'"

# Search for the marker string in dist/assets/*.js files
$SearchResults = @()
if (Test-Path "dist/assets") {
    $SearchResults = Select-String -Path "dist/assets/*.js" -Pattern "Create a category first" -SimpleMatch -ErrorAction SilentlyContinue
}

$MatchCount = $SearchResults.Count
Write-Host "  Found $MatchCount occurrence(s)"

if ($MatchCount -eq 0) {
    Print-Error "Frontend bundle is stale or empty. 'Create a category first' not found in dist/assets/*.js"
    Print-Error "dist folder may contain outdated code. Investigate dist/assets/ manually."
    Pop-Location
    exit 1
}
elseif ($MatchCount -gt 1) {
    Print-Error "Unexpected: found $MatchCount occurrences (expected exactly 1). Build may have included duplicates."
    Pop-Location
    exit 1
}

Print-Success "Frontend bundle verified: contains expected marker code"

Pop-Location
Write-Host ""

# ============================================================================
# STEP 3: Close Running RestaurantPOS Process
# ============================================================================
Print-Step "STEP 3: Stop Running RestaurantPOS Process"

$ProcessesToKill = Get-Process -Name "RestaurantPOS" -ErrorAction SilentlyContinue
if ($ProcessesToKill) {
    Write-Host "Found running RestaurantPOS process(es). Stopping..."
    $ProcessesToKill | Stop-Process -Force -ErrorAction SilentlyContinue

    # Wait for process to actually exit (up to 5 seconds)
    $WaitStarted = Get-Date
    while ((Get-Process -Name "RestaurantPOS" -ErrorAction SilentlyContinue) -and ((Get-Date) - $WaitStarted).TotalSeconds -lt 5) {
        Start-Sleep -Milliseconds 100
    }

    if (Get-Process -Name "RestaurantPOS" -ErrorAction SilentlyContinue) {
        Print-Error "RestaurantPOS process still running after 5 seconds. PyInstaller may fail."
        exit 1
    }
    Print-Success "RestaurantPOS process stopped and confirmed exited"
} else {
    Print-Success "No running RestaurantPOS process found"
}
Write-Host ""

# ============================================================================
# STEP 4: Run PyInstaller with New Flags
# ============================================================================
Print-Step "STEP 4: Run PyInstaller"

# Must be in backend directory for PyInstaller to find run.py and relative paths
if (-not (Test-Path "run.py")) {
    Print-Error "run.py not found in current directory. This script must be run from backend folder."
    exit 1
}

Write-Host "Command:"
Write-Host "  pyinstaller --noconfirm --onedir --noconsole --name $AppName \" -ForegroundColor Gray
Write-Host "    --add-data '..\frontend\dist;frontend/dist' \" -ForegroundColor Gray
Write-Host "    --add-data '.\alembic;backend/alembic' \" -ForegroundColor Gray
Write-Host "    --add-data '.\alembic.ini;backend' \" -ForegroundColor Gray
Write-Host "    --collect-all=webview \" -ForegroundColor Gray
Write-Host "    --hidden-import=pythonnet \" -ForegroundColor Gray
Write-Host "    --collect-all=pystray \" -ForegroundColor Gray
Write-Host "    --collect-all=PIL \" -ForegroundColor Gray
Write-Host "    run.py" -ForegroundColor Gray
Write-Host ""

pyinstaller --noconfirm --onedir --noconsole --name $AppName `
    --add-data "..\frontend\dist;frontend/dist" `
    --add-data ".\alembic;backend/alembic" `
    --add-data ".\alembic.ini;backend" `
    --collect-all=webview `
    --hidden-import=pythonnet `
    --collect-all=pystray `
    --collect-all=PIL `
    run.py

if ($LASTEXITCODE -ne 0) {
    Print-Error "PyInstaller failed (exit code: $LASTEXITCODE)"
    exit 1
}
Print-Success "PyInstaller completed"

# ============================================================================
# STEP 5: Verify PyInstaller Output
# ============================================================================
Print-Step "STEP 5: Verify Build Output"

$DistPath = "dist\$AppName"
$ExePath = "$DistPath\$AppName.exe"
$InternalPath = "$DistPath\_internal"

# Check for exe
if (-not (Test-Path $ExePath)) {
    Print-Error "$AppName.exe not found at $ExePath"
    exit 1
}
Print-Success "Executable: $ExePath exists"

# Check for webview bundle
if (-not (Test-Path "$InternalPath\webview")) {
    Print-Error "webview module not bundled at $InternalPath\webview"
    exit 1
}
Print-Success "Bundled: webview/_internal"

# Check for pystray bundle
if (-not (Test-Path "$InternalPath\pystray")) {
    Print-Error "pystray module not bundled at $InternalPath\pystray"
    exit 1
}
Print-Success "Bundled: pystray/_internal"

# Check for PIL bundle
if (-not (Test-Path "$InternalPath\PIL")) {
    Print-Error "PIL module not bundled at $InternalPath\PIL"
    exit 1
}
Print-Success "Bundled: PIL/_internal"

# Verify bundled frontend contains the marker code
$BundledAssets = Get-ChildItem -Path "$DistPath\frontend\dist\assets\*.js" -ErrorAction SilentlyContinue
if (-not $BundledAssets) {
    Print-Error "No JavaScript files found in bundled frontend at $DistPath\frontend\dist\assets"
    exit 1
}

$BundledMarkers = @()
$BundledMarkers = Select-String -Path "$DistPath\frontend\dist\assets\*.js" -Pattern "Create a category first" -SimpleMatch -ErrorAction SilentlyContinue
$BundledCount = $BundledMarkers.Count

if ($BundledCount -ne 1) {
    Print-Error "Bundled frontend has $BundledCount occurrences of 'Create a category first' (expected 1)"
    exit 1
}
Print-Success "Bundled frontend verified: contains expected marker code (1 occurrence)"

Write-Host ""

# ============================================================================
# SUCCESS SUMMARY
# ============================================================================
Print-Step "BUILD SUCCESSFUL"
Write-Host ""
Write-Host "Executable:        $ExePath" -ForegroundColor Yellow
Write-Host "Size:              $((Get-Item $ExePath).Length / 1MB)MB" -ForegroundColor Yellow
Write-Host "Built:             $(Get-Item $ExePath | Select-Object -ExpandProperty LastWriteTime)" -ForegroundColor Yellow
Write-Host ""
Write-Host "Data folder (exe): %LOCALAPPDATA%\$AppName" -ForegroundColor Yellow
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Close any running $AppName instance"
Write-Host "  2. Run: $ExePath"
Write-Host "  3. If issues occur, check: %LOCALAPPDATA%\$AppName\pos.log"
Write-Host ""
