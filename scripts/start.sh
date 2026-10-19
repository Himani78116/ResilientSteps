#!/usr/bin/env bash
# Usage: ./scripts/start.sh [profile]
# Examples:
#   ./scripts/start.sh local
#   ./scripts/start.sh demo
#   ./scripts/start.sh aws

PROFILE=${1:-local}
export CITYOS_PROFILE=$PROFILE

echo "=========================================="
echo " Starting ResilientSteps with profile: $PROFILE"
echo "=========================================="

if [ "$PROFILE" = "demo" ]; then
    echo "Running demo data seeder..."
    python logic/seed_demo_data.py || echo "Warning: Demo seeding skipped or failed."
fi

docker compose up -d

echo ""
echo "ResilientSteps services are online!"
echo "Backend API:      http://localhost:8000"
echo "Authority Web UI: http://localhost:8000/dashboard-ui/"
echo "Valhalla Routing: http://localhost:8002"
