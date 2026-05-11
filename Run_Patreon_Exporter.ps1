$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

Write-Host "Patreon Gmail Member Exporter" -ForegroundColor Cyan
Write-Host "Working directory: $PSScriptRoot"
Write-Host ""

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "Python was not found in PATH." -ForegroundColor Red
    Write-Host "Install Python, then run this shortcut again."
    Read-Host "Press Enter to close"
    exit 1
}

if (-not (Test-Path -LiteralPath ".\credentials.json")) {
    Write-Host "Missing credentials.json." -ForegroundColor Yellow
    Write-Host "Create a Gmail API Desktop OAuth client and save the downloaded JSON here:"
    Write-Host "$PSScriptRoot\credentials.json"
    Write-Host ""
    Write-Host "Opening README for setup instructions..."
    Start-Process -FilePath ".\README.md"
    Read-Host "Press Enter to close"
    exit 1
}

Write-Host "Checking required Python packages..."
python -c "import googleapiclient, google_auth_oauthlib, openpyxl" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing required Python packages..."
    python -m pip install -r .\requirements.txt
}

Write-Host ""
Write-Host "Exporting Patreon member records..."
$csvPath = Join-Path $PSScriptRoot "output\patreon_members.csv"
$xlsxPath = Join-Path $PSScriptRoot "output\patreon_members.xlsx"
$htmlPath = Join-Path $PSScriptRoot "output\patreon_members_report.html"
python .\export_patreon_members.py --out $csvPath --xlsx $xlsxPath --html $htmlPath

Write-Host ""
Write-Host "Done. Output folder:"
Write-Host "$PSScriptRoot\output"
if (Test-Path -LiteralPath $htmlPath) {
    Start-Process -FilePath $htmlPath
}
if (Test-Path -LiteralPath $xlsxPath) {
    Start-Process -FilePath $xlsxPath
}
Read-Host "Press Enter to close"
