# SmartRose Backend

FastAPI backend application for SmartRose.

## Project Structure

```
smartrose_backend/
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── routes/              # API route handlers
│   │   ├── health.py        # Health check endpoint
│   │   ├── com1.py          # Com1 routes
│   │   ├── com2.py          # Com2 routes
│   │   ├── com3.py          # Com3 routes
│   │   └── com4.py          # Com4 routes
│   ├── services/            # Business logic layer
│   │   ├── com1_service.py
│   │   ├── com2_service.py
│   │   ├── com3_service.py
│   │   └── com4_service.py
│   ├── models/              # Data models
│   │   └── base_model.py
│   ├── core/                # Core configuration
│   │   ├── config.py        # Application settings
│   │   └── database.py      # Database configuration
│   └── utils/               # Utility functions
│       └── helpers.py
├── tests/                   # Test files
│   └── test_health.py
├── requirements.txt         # Python dependencies
└── README.md
```

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file (optional) for environment variables:
```
DEBUG=True
DATABASE_URL=sqlite:///./smartrose.db
CORS_ORIGINS=["*"]
```

## Running the Application

Start the development server:
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`

API documentation:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Running Tests

```bash
pytest tests/
```

## API Endpoints

- `GET /` - Root endpoint
- `GET /api/v1/health` - Health check
- `GET /api/v1/com1` - Get com1 data
- `POST /api/v1/com1` - Create com1 data
- `GET /api/v1/com2` - Get com2 data
- `POST /api/v1/com2` - Create com2 data
- `GET /api/v1/com3` - Get com3 data
- `POST /api/v1/com3` - Create com3 data
- `GET /api/v1/com4` - Get com4 data
- `POST /api/v1/com4` - Create com4 data
