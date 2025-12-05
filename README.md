# SMARTROSE Backend (FastAPI + MongoDB)

This is the starter backend for the SMARTROSE system. It provides:
- FastAPI app with versioned routing
- MongoDB connectivity via Motor (startup ping + graceful shutdown)
- Sensor data ingestion endpoint (`/api/v1/sensor-data/`) with validation + logging
- DB health check (`/api/v1/db-health/`) that pings Mongo
- Stub ML predict endpoints for EOSM/INM/FM/EDAS to wire real models later
- Basic structured logging to stdout for requests/DB errors

## Getting started
1) Install Python 3.10+ and MongoDB (or use a cloud Mongo URI).
2) Create and activate a virtualenv (recommended):
   - Windows PowerShell:
     ```
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - macOS/Linux:
     ```
     python -m venv .venv
     source .venv/bin/activate
     ```
3) Create `.env` (copy from `.env.example` if present) and set:
   ```
   MONGO_URI=mongodb://localhost:27017
   MONGO_DB=smartrose
   ```
4) Install dependencies:
   ```
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
5) Run the API locally (auto-reload):
   ```
   uvicorn app.main:app --reload
   ```
6) Verify health:
   - Liveness: `GET http://localhost:8000/health`
   - Mongo: `GET http://localhost:8000/api/v1/db-health/`
7) Test a sensor ingestion request (example):
   ```
   curl -X POST http://localhost:8000/api/v1/sensor-data/ ^
     -H "Content-Type: application/json" ^
     -d "{\"sensor_id\":\"demo-1\",\"temperature\":22.5,\"humidity\":55}"
   ```

## Docker
```
cd docker
docker-compose up --build
```

## Tests
Pytest scaffolding is present; some tests are skipped until Mongo mocking and model logic are added.

## Notes for teammates
- ML predict routes are stubbed at `/api/v1/{component}/predict` and call placeholder functions in `app/ml/.../inference.py`; swap in real model loading/prediction when ready.
- Logging is centralized in `app/core/logging_config.py`; request/DB errors are logged automatically.
- Mongo client lifecycle is handled on app startup/shutdown; ensure `MONGO_URI`/`MONGO_DB` are set in `.env`.

