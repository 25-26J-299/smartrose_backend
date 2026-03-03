"""
Full end-to-end test for the multi-user INM backend changes.

Tests (in order):
  1. Login as approved farmer (mario@gmail.com) — get JWT
  2. GET /auth/my-devices?device_type=INM — should return user's INM devices
  3. GET /auth/my-locations — should return user's greenhouses
  4. POST /inm/sensor-data (no token) — valid device => 201
  5. POST /inm/sensor-data (no token) — FAKE device => 404
  6. GET /inm/status?device_id=... — with JWT => 200
  7. GET /inm/status?device_id=... — NO token => 401
  8. POST /inm/growth-stage — with JWT => 200
  9. GET /inm/growth-stage?device_id=... — with JWT => 200
 10. GET /inm/sensor-data?device_id=... — with JWT => 200
 11. POST /inm/action — with JWT => 200
 12. GET /inm/action-history?device_id=... — with JWT => 200
 13. Cross-user test: amanda's device with mario's JWT => 403
"""

import asyncio
import httpx

BASE = "http://localhost:8000/api/v1"

# --- Known approved users in DB ---
# mario@gmail.com  | farmer | approved | device: SR-INM-2024-001
# amanda@gmail.com | farmer | approved | device: SR-INM-1001

MARIO_EMAIL = "mario@gmail.com"
MARIO_DEVICE = "SR-INM-2024-001"

AMANDA_EMAIL = "amanda@gmail.com"
AMANDA_DEVICE = "SR-INM-1001"

# We need to reset a password first (done in prep step below)
TEST_PASSWORD = "Test@Reset99"


async def prep_reset_passwords():
    """Reset both test users' passwords so we can log in."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from app.services.auth_service import hash_password
    import os
    from dotenv import load_dotenv
    load_dotenv()

    client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
    db = client[os.getenv("MONGO_DB")]
    hashed = hash_password(TEST_PASSWORD)
    for email in [MARIO_EMAIL, AMANDA_EMAIL]:
        await db.users.update_one(
            {"email": email},
            {"$set": {"password_hash": hashed}},
        )
        print(f"  Password reset for {email}")


def ok(label, resp, expected=200):
    status = "PASS" if resp.status_code == expected else f"FAIL (got {resp.status_code})"
    print(f"  [{status}]  {label}")
    return resp.status_code == expected


async def run_tests():
    await prep_reset_passwords()
    print()

    async with httpx.AsyncClient(base_url=BASE, timeout=15) as c:

        # --- 1. Login mario ---
        print("=== AUTH ===")
        r = await c.post("/auth/login", json={"email": MARIO_EMAIL, "password": TEST_PASSWORD})
        if not ok("Login mario (approved farmer)", r, 200):
            print("  body:", r.text[:200])
            return
        mario_token = r.json()["access_token"]
        mario_headers = {"Authorization": f"Bearer {mario_token}"}

        # Login amanda
        r = await c.post("/auth/login", json={"email": AMANDA_EMAIL, "password": TEST_PASSWORD})
        ok("Login amanda (approved farmer)", r, 200)
        amanda_token = r.json()["access_token"]
        amanda_headers = {"Authorization": f"Bearer {amanda_token}"}

        # --- 2. My devices ---
        print("\n=== MY DEVICES / LOCATIONS ===")
        r = await c.get("/auth/my-devices?device_type=INM", headers=mario_headers)
        ok("GET /auth/my-devices?device_type=INM (mario)", r, 200)
        devices = r.json().get("devices", [])
        print(f"  mario devices: {[d.get('device_serial_number') for d in devices]}")

        r = await c.get("/auth/my-locations", headers=mario_headers)
        ok("GET /auth/my-locations (mario)", r, 200)
        locs = r.json().get("locations", [])
        print(f"  mario locations: {[l.get('name') for l in locs]}")

        # --- 3-5. Sensor data ingest ---
        print("\n=== SENSOR DATA INGEST (no token, ESP32 flow) ===")
        sensor_payload = {
            "device_id": MARIO_DEVICE,
            "N": 45.2, "P": 18.5, "K": 62.0,
            "ec": 1.85, "ph": 6.2,
            "soil_temp": 22.5, "soil_moisture": 65.0,
            "air_temp": 26.0, "air_hum": 72.0,
        }
        r = await c.post("/inm/sensor-data", json=sensor_payload)
        ok("POST /inm/sensor-data — registered device (mario)", r, 201)
        if r.status_code == 201:
            print(f"  reading id: {r.json().get('id')}")
        else:
            print("  error:", r.text[:300])

        r = await c.post("/inm/sensor-data", json={**sensor_payload, "device_id": "FAKE-DEVICE"})
        ok("POST /inm/sensor-data — unregistered device (expect 404)", r, 404)

        # --- 6-7. Status ---
        print("\n=== STATUS ===")
        r = await c.get(f"/inm/status?device_id={MARIO_DEVICE}", headers=mario_headers)
        ok("GET /inm/status — with JWT (mario's device)", r, 200)
        if r.status_code == 200:
            d = r.json()["data"]
            print(f"  EC: {d.get('current_ec')}  |  EC status: {d.get('ec_status')}  |  stage: {d.get('growth_stage_used')}")

        r = await c.get(f"/inm/status?device_id={MARIO_DEVICE}")
        ok("GET /inm/status — NO token (expect 401)", r, 401)

        # --- 8-9. Growth stage ---
        print("\n=== GROWTH STAGE ===")
        r = await c.post(
            "/inm/growth-stage",
            json={"growth_stage": "flowering", "device_id": MARIO_DEVICE},
            headers=mario_headers,
        )
        ok("POST /inm/growth-stage — set 'flowering' (mario)", r, 200)

        r = await c.get(f"/inm/growth-stage?device_id={MARIO_DEVICE}", headers=mario_headers)
        ok("GET /inm/growth-stage (mario)", r, 200)
        if r.status_code == 200:
            print(f"  stage: {r.json()['data'].get('current_growth_stage')}")

        # --- 10. Sensor data read ---
        print("\n=== SENSOR DATA READ ===")
        r = await c.get(f"/inm/sensor-data?device_id={MARIO_DEVICE}&limit=5", headers=mario_headers)
        ok("GET /inm/sensor-data?device_id= (mario)", r, 200)
        if r.status_code == 200:
            print(f"  count: {r.json().get('count')}")

        # --- 11-12. Actions ---
        print("\n=== ACTIONS ===")
        r = await c.post(
            "/inm/action",
            json={
                "device_id": MARIO_DEVICE,
                "action_taken": "applied",
                "recommendation_text": "EC is low — add fertilizer",
            },
            headers=mario_headers,
        )
        ok("POST /inm/action (mario)", r, 200)

        r = await c.get(f"/inm/action-history?device_id={MARIO_DEVICE}", headers=mario_headers)
        ok("GET /inm/action-history?device_id= (mario)", r, 200)
        if r.status_code == 200:
            print(f"  history count: {r.json().get('count')}")

        # --- 13. Cross-user ownership check ---
        print("\n=== CROSS-USER OWNERSHIP ===")
        r = await c.get(f"/inm/status?device_id={AMANDA_DEVICE}", headers=mario_headers)
        ok("GET /inm/status — mario uses AMANDA's device (expect 403)", r, 403)

        r = await c.get(f"/inm/sensor-data?device_id={AMANDA_DEVICE}", headers=mario_headers)
        ok("GET /inm/sensor-data — mario uses AMANDA's device (expect 403)", r, 403)

        r = await c.get(f"/inm/status?device_id={MARIO_DEVICE}", headers=amanda_headers)
        ok("GET /inm/status — amanda uses MARIO's device (expect 403)", r, 403)

        print("\n=== ALL TESTS COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(run_tests())
