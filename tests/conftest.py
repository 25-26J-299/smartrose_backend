"""
Pytest configuration and shared fixtures
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """
    Create a test client for the FastAPI application
    """
    return TestClient(app)


@pytest.fixture
def test_app():
    """
    Get the FastAPI application instance
    """
    return app

