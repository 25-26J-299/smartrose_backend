"""Manual tester for the EOSM prediction stub."""

import json
import sys

import requests

API_URL = "http://localhost:8000/api/v1/eosm/predict"

# Dummy payload since the EOSM model contract is not yet defined.
DUMMY_PAYLOAD = {
    "device_id": "eosm-demo-01",
    "metrics": {
        "vibration_rms": 0.15,
        "temperature": 27.4,
        "pressure": 1.01,
    },
    "context": {
        "mode": "test",
        "line": "A1",
    },
}


def main():
    print(f"POST {API_URL}")
    print("Payload:")
    print(json.dumps(DUMMY_PAYLOAD, indent=2))

    try:
        resp = requests.post(API_URL, json=DUMMY_PAYLOAD, timeout=10)
        resp.raise_for_status()
        print("\nResponse:")
        print(resp.json())
    except requests.exceptions.RequestException as exc:
        print(f"\nRequest failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()

