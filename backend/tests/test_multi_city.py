import os
import sys
import unittest
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import load_config, get_city_config
from logic.safety_feature_engine import SafetyFeatureEngine


class MultiCityTests(unittest.TestCase):
    def test_city_endpoint(self):
        with TestClient(app) as client:
            response = client.get("/city")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("city", data)
        self.assertIn("center", data)
        self.assertIn("timezone", data)
        self.assertEqual(data["city"], "Pune")
        self.assertEqual(data["center"]["lat"], 18.5204)

    def test_city_config_loader(self):
        city = get_city_config()
        self.assertEqual(city["name"], "Pune")
        self.assertEqual(city["osmnx_place"], "Pune, Maharashtra, India")
        self.assertEqual(city["h3_resolution"], 9)

    def test_safety_feature_engine_timezone_parameter(self):
        # Verify engine initializes with custom timezone parameter
        engine_ist = SafetyFeatureEngine(tz_name="Asia/Kolkata")
        self.assertEqual(engine_ist._tz_name, "Asia/Kolkata")

        engine_ny = SafetyFeatureEngine(tz_name="America/New_York")
        self.assertEqual(engine_ny._tz_name, "America/New_York")

    def test_logic_city_config_loader(self):
        from logic.generate_safety_map import load_city_config
        cfg = load_city_config()
        self.assertEqual(cfg["name"], "Pune")
        self.assertEqual(cfg["osmnx_place"], "Pune, Maharashtra, India")
