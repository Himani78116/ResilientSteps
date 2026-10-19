param (
    [string]$Profile = "local"
)

$env:CITYOS_PROFILE = $Profile

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Starting ResilientSteps with profile: $Profile" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

if ($Profile -eq "demo") {
    Write-Host "Running demo data seeder..." -ForegroundColor Yellow
    python logic/seed_demo_data.py
}

docker compose up -d

Write-Host ""
Write-Host "ResilientSteps services are online!" -ForegroundColor Green
Write-Host "Backend API:      http://localhost:8000" -ForegroundColor Green
Write-Host "Authority Web UI: http://localhost:8000/dashboard-ui/" -ForegroundColor Green
Write-Host "Valhalla Routing: http://localhost:8002" -ForegroundColor Green
