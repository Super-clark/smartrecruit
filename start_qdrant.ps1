# start_qdrant.ps1
# Launches the Qdrant standalone binary from the project folder.
# Run this in a separate terminal and keep it open while using the app.
#
# Usage:
#   .\start_qdrant.ps1

$qdrantExe = Join-Path $PSScriptRoot "qdrant.exe"
$configFile = Join-Path $PSScriptRoot "qdrant_config.yaml"

if (-not (Test-Path $qdrantExe)) {
    Write-Host ""
    Write-Host "ERROR: qdrant.exe not found in this folder." -ForegroundColor Red
    Write-Host ""
    Write-Host "Download it from:" -ForegroundColor Yellow
    Write-Host "  https://github.com/qdrant/qdrant/releases/latest" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Look for:  qdrant-x86_64-pc-windows-msvc.zip" -ForegroundColor Yellow
    Write-Host "Extract qdrant.exe into this folder:" -ForegroundColor Yellow
    Write-Host "  $PSScriptRoot" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

Write-Host "Starting Qdrant on http://localhost:6333 ..." -ForegroundColor Green
Write-Host "Keep this window open while using SmartRecruit." -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop.`n"

& $qdrantExe --config-path $configFile
