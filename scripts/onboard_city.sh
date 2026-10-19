#!/usr/bin/env bash
# ResilientSteps City Onboarding Script
# Usage: ./scripts/onboard_city.sh <path_to_city_config.yaml>
# Example: ./scripts/onboard_city.sh config/city.yaml

CONFIG_FILE=$1

if [ -z "$CONFIG_FILE" ]; then
    echo "Error: Please provide a city YAML config file path."
    echo "Usage: ./scripts/onboard_city.sh <path_to_city_config.yaml>"
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Config file not found at '$CONFIG_FILE'"
    exit 1
fi

echo "=========================================="
echo " Onboarding City from: $CONFIG_FILE"
echo "=========================================="

# 1. Copy config file to config/city.yaml if different
if [ "$CONFIG_FILE" != "config/city.yaml" ]; then
    cp "$CONFIG_FILE" "config/city.yaml"
    echo "Updated config/city.yaml"
fi

# 2. Extract Valhalla Tile URL
TILE_URL=$(python -c "import yaml; data=yaml.safe_load(open('config/city.yaml')); print(data.get('city', data).get('valhalla_tile_url', ''))")

if [ -n "$TILE_URL" ]; then
    export VALHALLA_TILE_URL=$TILE_URL
    echo "Set VALHALLA_TILE_URL=$VALHALLA_TILE_URL"
fi

# 3. Restart Docker services
echo "Rebuilding docker services for new city..."
docker compose up -d

# 4. Run safety graph ingest pipeline
echo "Running OSMnx safety data ingest pipeline..."
cd logic && python generate_safety_map.py && cd ..

echo "City onboarding complete!"
