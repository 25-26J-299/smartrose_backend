"""Basic test placeholder for EOSM endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.mark.skip("Pending EOSM implementation.")
def test_eosm_placeholder():
    response = client.get("/api/v1/eosm/")
    assert response.status_code == 200

