# Restaurant POS Build Script
# This script builds the frontend bundle, then packages it with the backend using PyInstaller.
# It stops immediately if any step fails.
#
# What this script touches: only files in the repo (frontend/dist, backend/dist).
# What it does NOT touch: database, backups, or %LOCALAPPDATA%\RestaurantPOS.

$ErrorActionPreference = 'Stop'

# Colors for output
$ColorSuccess = 'Green'
$ColorError = 'Red'
$ColorInfo = 'Cyan'

Write-Host '=' * 60
Write-Host 'Restaurant POS Build' -ForegroundColor $ColorInfo
Write-Host '=' * 60
Write-Host ''

# ============================================================================
# STEP 1: Build the frontend
# ============================================================================

Write-Host 'STEP 1: Building frontend' -ForegroundColor $ColorInfo
Write-Host 'Running: npm run build' -ForegroundColor $ColorInfo

Push-Location 'C:\dev\my-pos\frontend'

try {
  npm run build
  $frontendExitCode = $LASTEXITCODE
}
catch {
  Write-Host 'ERROR: npm command failed' -ForegroundColor $Error
  exit 1
}
finally {
  Pop-Location
}

if ($frontendExitCode -ne 0) {
  Write-Host "ERROR: Frontend build failed with exit code $frontendExitCode" -ForegroundColor $ColorError
  Write-Host 'This is critical. The frontend bundle must be current before packaging.' -ForegroundColor $ColorError
  exit 1
}

Write-Host 'Frontend build succeeded' -ForegroundColor $ColorSuccess
Write-Host ''

# ============================================================================
# STEP 2: Verify the bundle contains current code
# ============================================================================

Write-Host 'STEP 2: Verifying bundle contains current code' -ForegroundColor $ColorInfo

$bundleFiles = Get-ChildItem -Path 'C:\dev\my-pos\frontend\dist\assets\*.js' -ErrorAction SilentlyContinue

if ($null -eq $bundleFiles -or $bundleFiles.Count -eq 0) {
  Write-Host 'ERROR: No JavaScript files found in dist/assets' -ForegroundColor $ColorError
  exit 1
}

$searchPattern = 'Create a category first'
$matches = @()

foreach ($file in $bundleFiles) {
  $fileContent = Get-Content -Path $file.FullName -Raw
  $fileMatches = [regex]::Matches($fileContent, [regex]::Escape($searchPattern))
  if ($fileMatches.Count -gt 0) {
    $matches += @($file.Name) * $fileMatches.Count
  }
}

$matchCount = $matches.Count

if ($matchCount -eq 0) {
  Write-Host "ERROR: Bundle verification failed" -ForegroundColor $ColorError
  Write-Host "Expected to find '$searchPattern' in the bundle, but found 0 occurrences" -ForegroundColor $ColorError
  Write-Host "This means the bundle is stale or missing current code." -ForegroundColor $ColorError
  exit 1
}

if ($matchCount -ne 1) {
  Write-Host "ERROR: Bundle verification failed" -ForegroundColor $ColorError
  Write-Host "Expected exactly 1 occurrence of '$searchPattern', but found $matchCount" -ForegroundColor $ColorError
  exit 1
}

Write-Host "Bundle verified: found '$searchPattern' exactly once" -ForegroundColor $ColorSuccess
Write-Host ''

# ============================================================================
# STEP 3: Close any running RestaurantPOS process
# ============================================================================

Write-Host 'STEP 3: Closing any running RestaurantPOS process' -ForegroundColor $ColorInfo

$process = Get-Process -Name 'RestaurantPOS' -ErrorAction SilentlyContinue

if ($null -ne $process) {
  Write-Host "Found running RestaurantPOS (PID: $($process.Id)), stopping..." -ForegroundColor $ColorInfo
  Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue

  # Wait for the process to actually exit
  $waitTime = 0
  $maxWait = 5000
  while ((Get-Process -Name 'RestaurantPOS' -ErrorAction SilentlyContinue) -and $waitTime -lt $maxWait) {
    Start-Sleep -Milliseconds 100
    $waitTime += 100
  }

  if (Get-Process -Name 'RestaurantPOS' -ErrorAction SilentlyContinue) {
    Write-Host 'WARNING: Process did not exit cleanly, but continuing' -ForegroundColor 'Yellow'
  }
  else {
    Write-Host 'Process stopped successfully' -ForegroundColor $ColorSuccess
  }
}
else {
  Write-Host 'No running RestaurantPOS process found' -ForegroundColor $ColorInfo
}

Write-Host ''

# ============================================================================
# STEP 4: Run PyInstaller
# ============================================================================

Write-Host 'STEP 4: Running PyInstaller' -ForegroundColor $ColorInfo

Push-Location 'C:\dev\my-pos\backend'

try {
  & pyinstaller `
    --noconfirm `
    --onedir `
    --noconsole `
    --name RestaurantPOS `
    --add-data '..\frontend\dist;frontend/dist' `
    --add-data '.\alembic;backend/alembic' `
    --add-data '.\alembic.ini;backend' `
    --collect-all=webview `
    --hidden-import=pythonnet `
    --collect-all=pystray `
    --collect-all=PIL `
    run.py

  $pyinstallerExitCode = $LASTEXITCODE
}
catch {
  Write-Host 'ERROR: PyInstaller command failed' -ForegroundColor $ColorError
  exit 1
}
finally {
  Pop-Location
}

if ($pyinstallerExitCode -ne 0) {
  Write-Host "ERROR: PyInstaller failed with exit code $pyinstallerExitCode" -ForegroundColor $ColorError
  exit 1
}

Write-Host 'PyInstaller succeeded' -ForegroundColor $ColorSuccess
Write-Host ''

# ============================================================================
# STEP 5: Verify the output
# ============================================================================

Write-Host 'STEP 5: Verifying build output' -ForegroundColor $ColorInfo

$allVerified = $true

# Check: _internal\webview exists
$webviewPath = 'C:\dev\my-pos\backend\dist\RestaurantPOS\_internal\webview'
if (-not (Test-Path -Path $webviewPath -PathType Container)) {
  Write-Host "ERROR: $webviewPath not found" -ForegroundColor $ColorError
  $allVerified = $false
}
else {
  Write-Host "Found: $webviewPath" -ForegroundColor $ColorSuccess
}

# Check: _internal\pystray exists
$pystrayPath = 'C:\dev\my-pos\backend\dist\RestaurantPOS\_internal\pystray'
if (-not (Test-Path -Path $pystrayPath -PathType Container)) {
  Write-Host "ERROR: $pystrayPath not found" -ForegroundColor $ColorError
  $allVerified = $false
}
else {
  Write-Host "Found: $pystrayPath" -ForegroundColor $ColorSuccess
}

# Check: RestaurantPOS.exe exists
$exePath = 'C:\dev\my-pos\backend\dist\RestaurantPOS\RestaurantPOS.exe'
if (-not (Test-Path -Path $exePath -PathType Leaf)) {
  Write-Host "ERROR: $exePath not found" -ForegroundColor $ColorError
  $allVerified = $false
}
else {
  Write-Host "Found: $exePath" -ForegroundColor $ColorSuccess
}

# Check: frontend bundle inside the exe directory contains the marker
# Search recursively under dist\RestaurantPOS for any .js files
$bundleJsFiles = Get-ChildItem -Path 'C:\dev\my-pos\backend\dist\RestaurantPOS' -Recurse -Filter '*.js' -ErrorAction SilentlyContinue

if ($null -eq $bundleJsFiles -or $bundleJsFiles.Count -eq 0) {
  Write-Host "ERROR: No JavaScript files found in packaged bundle" -ForegroundColor $ColorError
  $allVerified = $false
}
else {
  $bundleMatches = @()
  foreach ($file in $bundleJsFiles) {
    $fileContent = Get-Content -Path $file.FullName -Raw
    $fileMatches = [regex]::Matches($fileContent, [regex]::Escape($searchPattern))
    if ($fileMatches.Count -gt 0) {
      $bundleMatches += @($file.Name) * $fileMatches.Count
    }
  }

  $bundleMatchCount = $bundleMatches.Count

  if ($bundleMatchCount -ne 1) {
    Write-Host "ERROR: Packaged bundle verification failed" -ForegroundColor $ColorError
    Write-Host "Expected exactly 1 occurrence of '$searchPattern' in packaged bundle, but found $bundleMatchCount" -ForegroundColor $ColorError
    $allVerified = $false
  }
  else {
    Write-Host "Packaged bundle verified: '$searchPattern' found exactly once" -ForegroundColor $ColorSuccess
  }
}

Write-Host ''

if (-not $allVerified) {
  Write-Host 'ERROR: Output verification failed' -ForegroundColor $ColorError
  exit 1
}

# ============================================================================
# BUILD COMPLETE
# ============================================================================

Write-Host '=' * 60
Write-Host 'BUILD SUCCEEDED' -ForegroundColor $ColorSuccess
Write-Host 'All steps completed successfully' -ForegroundColor $ColorSuccess
Write-Host ''
Write-Host 'Output location: C:\dev\my-pos\backend\dist\RestaurantPOS' -ForegroundColor $ColorInfo
Write-Host 'Executable: RestaurantPOS.exe' -ForegroundColor $ColorInfo
Write-Host '=' * 60
