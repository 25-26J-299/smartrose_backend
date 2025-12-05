"""Simple manual ingestion generator for /api/v1/sensor-data/."""

import random
import time
from datetime import datetime, timezone
from itertools import cycle

import requests

API_URL = "http://localhost:8000/api/v1/sensor-data/"

# Rotate through a few sensor ids to simulate multiple devices
SENSOR_IDS = cycle(["eosm-01", "eosm-02", "eosm-03"])


def build_payload() -> dict:
    """Build a minimal valid SensorData payload."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "sensor_id": next(SENSOR_IDS),
        "temperature": round(random.uniform(18, 32), 2),
        "humidity": round(random.uniform(35, 70), 1),
        "timestamp": now,
    }


def send_once(payload: dict) -> None:
    """Send one ingestion request and print the result."""
    try:
        resp = requests.post(API_URL, json=payload, timeout=10)
        resp.raise_for_status()
        body = resp.json()
        print(
            f"[OK] {payload['sensor_id']} -> status={resp.status_code} id={body.get('data', {}).get('id')}"
        )
    except requests.exceptions.RequestException as exc:
        print(f"[FAIL] {payload['sensor_id']} -> {exc}")
        time.sleep(3)


def main():
    print("Starting dummy ingestion. CTRL+C to stop.")
    try:
        while True:
            payload = build_payload()
            send_once(payload)
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nStopped by user.")


if __name__ == "__main__":
    main()

