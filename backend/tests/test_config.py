import os
import unittest

from app.core.config import (
    load_config,
    get_city_config,
    get_scoring_config,
    get_profile_config,
)


class ConfigTests(unittest.TestCase):
    def test_load_local_profile(self):
        cfg = load_config("local")
        self.assertEqual(cfg["profile_name"], "local")
        self.assertIn("city", cfg)
        self.assertIn("scoring", cfg)
        self.assertEqual(cfg["city"]["name"], "Pune")
        self.assertEqual(cfg["profile"]["backend"]["port"], 8000)

    def test_load_demo_profile(self):
        os.environ["NGROK_DOMAIN"] = "test-demo-domain.ngrok-free.app"
        cfg = load_config("demo")
        self.assertEqual(cfg["profile_name"], "demo")
        self.assertTrue(cfg["profile"]["demo"]["seed_data"])
        self.assertEqual(cfg["profile"]["tunnel"]["domain"], "test-demo-domain.ngrok-free.app")

    def test_load_aws_and_production_profiles(self):
        cfg_aws = load_config("aws")
        self.assertEqual(cfg_aws["profile_name"], "aws")
        self.assertEqual(cfg_aws["profile"]["storage"]["type"], "s3")

        cfg_prod = load_config("production")
        self.assertEqual(cfg_prod["profile_name"], "production")
        self.assertEqual(cfg_prod["profile"]["backend"]["workers"], 8)

    def test_convenience_accessors(self):
        city = get_city_config()
        self.assertEqual(city["name"], "Pune")
        self.assertEqual(city["timezone"], "Asia/Kolkata")

        scoring = get_scoring_config()
        self.assertIn("road_type_scores", scoring)
        self.assertEqual(scoring["road_type_scores"]["footway"], 90)

        profile = get_profile_config()
        self.assertIn("backend", profile)
