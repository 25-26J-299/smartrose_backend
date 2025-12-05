# SMARTROSE Backend (FastAPI + MongoDB)

This is the starter backend for the SMARTROSE system. It provides:
- FastAPI app with versioned routing
- MongoDB connectivity via Motor
- Sensor data ingestion endpoint (`/api/v1/sensor-data/`)
- Placeholders for ML services and migration scripts

## Getting started
1) Create a `.env` based on `.env.example` and fill `MONGO_URI`.
2) Install dependencies:
```
pip install -r requirements.txt
```
3) Run the API locally:
```
uvicorn app.main:app --reload
```
4) Health check: `GET http://localhost:8000/health`

## Docker
```
cd docker
docker-compose up --build
```

## Tests
Pytest scaffolding is present; some tests are skipped until Mongo mocking and model logic are added.

