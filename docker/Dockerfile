# Base lightweight Python image
FROM python:3.11-slim

# Avoid Python bytecode and ensure stdout/stderr are unbuffered
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first to leverage Docker layer caching
COPY ../requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY ../app /app/app

# Expose FastAPI port
EXPOSE 8000

# Launch the API
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

