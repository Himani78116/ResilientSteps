import unittest

from app.modules.walksafe.services.weather_service import (
    OPEN_METEO_BASE_URL,
    UV_PENALTY,
    WEATHER_CACHE_TTL_SECONDS,
    WeatherService,
    compute_heat_penalty,
    parse_weather_payload,
)

# Trimmed copy of a real Open-Meteo response, used so tests don't call the API.
OPEN_METEO_FIXTURE = {
    "latitude": 18.5204,
    "longitude": 73.8567,
    "timezone": "Asia/Kolkata",
    "current": {
        "time": "2026-10-20T10:00",
        "interval": 900,
        "temperature_2m": 28.4,
        "apparent_temperature": 31.7,
        "relative_humidity_2m": 68,
        "uv_index": 6.5,
        "is_day": 1,
    },
}

PARSED_FIXTURE = {
    "temperature_c": 28.4,
    "apparent_temperature_c": 31.7,
    "relative_humidity": 68.0,
    "uv_index": 6.5,
    "is_day": True,
    "heat_penalty": 5.0,
}


# Stand-in for httpx.AsyncClient so WeatherService never touches the network.
class FakeAsyncClient:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls: list[tuple[str, dict]] = []

    async def get(self, url, params=None):
        self.calls.append((url, params or {}))
        if self._error is not None:
            raise self._error

        class FakeResponse:
            def __init__(self, payload):
                self._payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        return FakeResponse(self._response)


class WeatherServiceTests(unittest.IsolatedAsyncioTestCase):
    # Flattens the nested Open-Meteo JSON into the service's simple weather dict.
    def test_parse_weather_payload_returns_flat_dict(self):
        parsed = parse_weather_payload(OPEN_METEO_FIXTURE)
        self.assertEqual(parsed["temperature_c"], 28.4)
        self.assertEqual(parsed["apparent_temperature_c"], 31.7)
        self.assertEqual(parsed["relative_humidity"], 68.0)
        self.assertEqual(parsed["uv_index"], 6.5)
        self.assertIs(parsed["is_day"], True)
        self.assertEqual(parsed["heat_penalty"], 5.0)

    # Missing keys become None and heat penalty defaults to 0.0 instead of raising.
    def test_parse_weather_payload_tolerates_unknown_values(self):
        parsed = parse_weather_payload({"current": {}})
        self.assertIsNone(parsed["temperature_c"])
        self.assertIsNone(parsed["apparent_temperature_c"])
        self.assertIsNone(parsed["relative_humidity"])
        self.assertIsNone(parsed["uv_index"])
        self.assertIsNone(parsed["is_day"])
        self.assertEqual(parsed["heat_penalty"], 0.0)

        parsed = parse_weather_payload({})
        self.assertEqual(parsed["heat_penalty"], 0.0)

    # Pins the exact penalty for each heat-tier boundary temperature.
    def test_compute_heat_penalty_boundary_table(self):
        expected = {
            27.0: 0.0,
            28.0: 5.0,
            32.0: 12.0,
            38.0: 20.0,
            42.0: 30.0,
            45.0: 30.0,
        }
        for apparent_c, penalty in expected.items():
            self.assertEqual(
                compute_heat_penalty(apparent_c, None),
                penalty,
                f"apparent {apparent_c} should give {penalty}",
            )

    # UV index >= 8 adds a flat penalty on top of (or instead of) the heat tier.
    def test_compute_heat_penalty_adds_uv_penalty(self):
        self.assertEqual(compute_heat_penalty(31.7, 8.0), 5.0 + UV_PENALTY)
        self.assertEqual(compute_heat_penalty(42.0, 8.0), 30.0 + UV_PENALTY)
        self.assertEqual(compute_heat_penalty(None, 8.0), UV_PENALTY)
        self.assertEqual(compute_heat_penalty(31.7, 7.9), 5.0)

    # Total penalty is clamped at MAX_HEAT_PENALTY (40.0).
    def test_compute_heat_penalty_caps_at_40(self):
        self.assertEqual(compute_heat_penalty(45.0, 20.0), 30.0 + UV_PENALTY)

    # Builds the correct Open-Meteo URL/params and reuses the cache within the hour.
    async def test_get_weather_returns_parsed_data_and_caches_within_hour(self):
        client = FakeAsyncClient(response=OPEN_METEO_FIXTURE)
        service = WeatherService(client=client)

        first = await service.get_weather(18.5204, 73.8567)
        second = await service.get_weather(18.5204, 73.8567)

        self.assertEqual(first, PARSED_FIXTURE)
        self.assertEqual(second, PARSED_FIXTURE)
        self.assertEqual(len(client.calls), 1)

        url, params = client.calls[0]
        self.assertEqual(url, OPEN_METEO_BASE_URL)
        self.assertEqual(params["latitude"], 18.5204)
        self.assertEqual(params["longitude"], 73.8567)
        self.assertIn("apparent_temperature", params["current"])

    # A network failure returns None so route scoring can skip the heat term.
    async def test_network_error_returns_none_and_does_not_raise(self):
        client = FakeAsyncClient(error=RuntimeError("network down"))
        service = WeatherService(client=client)

        result = await service.get_weather(18.5204, 73.8567)

        self.assertIsNone(result)
        self.assertEqual(len(client.calls), 1)


if __name__ == "__main__":
    unittest.main()
