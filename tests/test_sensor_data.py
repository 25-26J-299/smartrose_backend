"""Basic test placeholders for sensor data endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.mark.skip("Add Mongo mocking before enabling this test.")
def test_sensor_data_post_returns_success():
    response = client.post(
        "/api/v1/sensor-data/",
        json={"sensor_id": "demo-1", "temperature": 20.5, "humidity": 55.0},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"

