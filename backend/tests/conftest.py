from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def _stub_live_weather():
    with patch(
        "app.modules.walksafe.services.risk_engine.weather_service.get_weather",
        new=AsyncMock(return_value=None),
    ):
        yield
