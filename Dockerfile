# Medical Centre Platform — Production Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Environment defaults (override at runtime)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    HOST=0.0.0.0 \
    PORT=8080

# Expose port
EXPOSE 8080

# Health check — stdlib only (no requests dependency)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8080/__health', timeout=3).status==200 else 1)" || exit 1

# Run with production Gunicorn config (override via gunicorn.conf.py env vars)
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
