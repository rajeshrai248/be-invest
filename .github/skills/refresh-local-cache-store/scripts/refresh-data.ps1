# Refresh all cached data: PDFs, cost analysis, financial analysis
# PowerShell script to trigger the data refresh workflow

param(
    [string]$Model = "claude-sonnet-4-20250514",
    [switch]$SkipApiCheck = $false
)

$ErrorActionPreference = "Stop"

# Get project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)

Write-Host "🚀 Data Refresh Script" -ForegroundColor Cyan
Write-Host "=" * 60

# Check if API is running (unless skipped)
if (-not $SkipApiCheck) {
    Write-Host "`nChecking API health..." -ForegroundColor Yellow
    
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" `
            -TimeoutSec 5 `
            -ErrorAction Stop
        Write-Host "✅ API is running and healthy" -ForegroundColor Green
    }
    catch {
        Write-Host "❌ API server is not running!" -ForegroundColor Red
        Write-Host "`nPlease start the API server first:" -ForegroundColor Yellow
        Write-Host "   python scripts\run_api.py" 
        Write-Host ""
        exit 1
    }
}

Write-Host "`n🔄 Starting refresh workflow..." -ForegroundColor Cyan
Write-Host ""

# Run the Python refresh script
$PythonScript = Join-Path $ProjectRoot "scripts\refresh_data.py"

try {
    Push-Location $ProjectRoot
    
    # Run with specified model
    $env:REFRESH_MODEL = $Model
    python $PythonScript
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✅ Refresh completed successfully!" -ForegroundColor Green
    }
    else {
        Write-Host "`n❌ Refresh completed with errors" -ForegroundColor Red
        exit 1
    }
}
catch {
    Write-Host "❌ Error running refresh: $_" -ForegroundColor Red
    exit 1
}
finally {
    Pop-Location
}
