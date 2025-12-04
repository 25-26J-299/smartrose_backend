# SmartRose Backend

FastAPI backend application for SmartRose built with Python 3.14.1.

## Features

- FastAPI with async/await support
- RESTful API endpoints
- Health check monitoring
- CORS middleware configuration
- Comprehensive test coverage
- Pydantic v2 for data validation
- SQLAlchemy for database operations

## Project Structure

```
smartrose_backend/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI application entry point
│   ├── routes/                    # API route handlers
│   │   ├── __init__.py
│   │   ├── health.py              # Health check endpoint
│   │   ├── component1.py          # Component 1 routes
│   │   ├── component2.py          # Component 2 routes
│   │   ├── component3.py          # Component 3 routes
│   │   └── component4.py          # Component 4 routes
│   ├── services/                  # Business logic layer
│   │   ├── __init__.py
│   │   ├── com1_service.py
│   │   ├── com2_service.py
│   │   ├── com3_service.py
│   │   └── com4_service.py
│   ├── models/                    # Data models
│   │   ├── __init__.py
│   │   └── base_model.py
│   ├── core/                      # Core configuration
│   │   ├── __init__.py
│   │   ├── config.py              # Application settings (Pydantic v2)
│   │   └── database.py            # Database configuration
│   └── utils/                     # Utility functions
│       ├── __init__.py
│       └── helpers.py
├── tests/                         # Test files
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures
│   └── test_health.py             # Health check tests
├── venv/                          # Virtual environment (gitignored)
├── htmlcov/                       # Coverage HTML reports (gitignored)
├── pytest.ini                     # Pytest configuration
├── requirements.txt               # Python dependencies
├── .gitignore                    # Git ignore rules
└── README.md
```

## Prerequisites

- Python 3.14.1 (or compatible version)
- pip (Python package manager)

## Setup

### 1. Create and Activate Virtual Environment

```bash
# Create virtual environment with Python 3.14.1
python3.14 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Environment Configuration (Optional)

Create a `.env` file in the project root for environment-specific settings:

```env
DEBUG=False
DATABASE_URL=sqlite:///./smartrose.db
CORS_ORIGINS=["*"]
APP_NAME=SmartRose Backend
VERSION=1.0.0
```

## Running the Application

### Development Server

Start the development server with auto-reload:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API Base URL**: `http://localhost:8000`
- **Interactive API Docs (Swagger UI)**: `http://localhost:8000/docs`
- **Alternative API Docs (ReDoc)**: `http://localhost:8000/redoc`

## API Endpoints

### Root
- `GET /` - Welcome message

### Health Check
- `GET /api/v1/health` - Health check endpoint

### Component 1
- `GET /api/v1/com1` - Get component 1 data
- `POST /api/v1/com1` - Create component 1 data

### Component 2
- `GET /api/v1/com2` - Get component 2 data
- `POST /api/v1/com2` - Create component 2 data

### Component 3
- `GET /api/v1/com3` - Get component 3 data
- `POST /api/v1/com3` - Create component 3 data

### Component 4
- `GET /api/v1/com4` - Get component 4 data
- `POST /api/v1/com4` - Create component 4 data

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Tests with Verbose Output

```bash
pytest -v
```

### Run Specific Test File

```bash
pytest tests/test_health.py
```

### Run Specific Test Function

```bash
pytest tests/test_health.py::test_root
```

### Run Tests with Coverage

```bash
# Terminal output
pytest --cov=app --cov-report=term

# HTML report
pytest --cov=app --cov-report=html

# Both terminal and HTML
pytest --cov=app --cov-report=term --cov-report=html
```

After generating HTML coverage, view it with:
```bash
open htmlcov/index.html  # macOS
```

## Dependencies

### Core Dependencies
- **FastAPI** (0.123.8) - Modern, fast web framework
- **Uvicorn** (0.38.0) - ASGI server
- **Pydantic** (2.12.5) - Data validation using Python type annotations
- **Pydantic Settings** (2.12.0) - Settings management
- **SQLAlchemy** (2.0.44) - SQL toolkit and ORM

### Development Dependencies
- **pytest** (9.0.1) - Testing framework
- **pytest-asyncio** (1.3.0) - Async test support
- **pytest-cov** (7.0.0) - Coverage plugin
- **httpx** (0.28.1) - HTTP client for testing

See `requirements.txt` for the complete list of dependencies.

## Configuration

The application uses Pydantic Settings (v2) for configuration management. Settings are defined in `app/core/config.py` and can be overridden via:

1. Environment variables
2. `.env` file
3. Default values in the `Settings` class

## Development

### Code Style

The project follows Python best practices and uses:
- Type hints for better code documentation
- Async/await for asynchronous operations
- Pydantic models for data validation

### Adding New Routes

1. Create a new route file in `app/routes/`
2. Import and include the router in `app/main.py`
3. Add corresponding service in `app/services/` if needed
4. Write tests in `tests/`

### Project Status

- ✅ Python 3.14.1 compatibility
- ✅ Pydantic v2 configuration
- ✅ Test coverage setup
- ✅ Health check endpoint
- ✅ Component routes (1-4)
- ✅ CORS middleware
- ✅ Async/await support

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]
