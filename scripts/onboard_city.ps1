param (
    [Parameter(Mandatory=$true)]
    [string]$ConfigFile
)

if (!(Test-Path $ConfigFile)) {
    Write-Host "Error: Config file not found at '$ConfigFile'" -ForegroundColor Red
    exit 1
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Onboarding City from: $ConfigFile" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Copy config file to config/city.yaml if different
if ($ConfigFile -ne "config/city.yaml") {
    Copy-Item $ConfigFile "config/city.yaml" -Force
    Write-Host "Updated config/city.yaml" -ForegroundColor Green
}

# 2. Extract Valhalla Tile URL
$TileUrl = python -c "import yaml; data=yaml.safe_load(open('config/city.yaml')); print(data.get('city', data).get('valhalla_tile_url', ''))"

if ($TileUrl) {
    $env:VALHALLA_TILE_URL = $TileUrl
    Write-Host "Set VALHALLA_TILE_URL=$TileUrl" -ForegroundColor Green
}

# 3. Restart Docker services
Write-Host "Restarting docker services..." -ForegroundColor Yellow
docker compose up -d

# 4. Run safety graph ingest pipeline
Write-Host "Running OSMnx safety data ingest pipeline..." -ForegroundColor Yellow
Set-Location logic
python generate_safety_map.py
Set-Location ..

Write-Host "City onboarding complete!" -ForegroundColor Green
