param(
  [string]$HostAddress = "0.0.0.0",
  [int]$Port = 5000,
  [string]$AllowedOrigin = "https://seu-frontend.com",
  [string]$ServiceAccountFile = "C:\secrets\firebase-service-account.json"
)

$ErrorActionPreference = "Stop"

Write-Host "== HEAL/REDISUS Backend (Production) ==" -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath $ServiceAccountFile)) {
  Write-Error "FIREBASE_SERVICE_ACCOUNT_FILE nao encontrado: $ServiceAccountFile"
}

$env:FLASK_ENV = "production"
$env:CLINICAL_API_REQUIRE_AUTH = "1"
$env:CLINICAL_API_ALLOWED_ORIGIN = $AllowedOrigin
$env:FIREBASE_SERVICE_ACCOUNT_FILE = $ServiceAccountFile

Write-Host "Variaveis carregadas:" -ForegroundColor Green
Write-Host " - FLASK_ENV=$($env:FLASK_ENV)"
Write-Host " - CLINICAL_API_REQUIRE_AUTH=$($env:CLINICAL_API_REQUIRE_AUTH)"
Write-Host " - CLINICAL_API_ALLOWED_ORIGIN=$($env:CLINICAL_API_ALLOWED_ORIGIN)"
Write-Host " - FIREBASE_SERVICE_ACCOUNT_FILE=$($env:FIREBASE_SERVICE_ACCOUNT_FILE)"
Write-Host ""
Write-Host "Iniciando backend em http://$HostAddress`:$Port ..." -ForegroundColor Yellow

python "heal_platform.py" --mode dashboard --host $HostAddress --port $Port
