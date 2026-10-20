# Dockerfile for Central Virology Laboratory Backend
# Shared image for the protected staging API and future production services
# Features: Tesseract OCR (Hebrew + English), OpenCV preprocessing

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TEMP_STORAGE_PATH=/app/temp_storage

# Install system dependencies including Tesseract OCR
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    tesseract-ocr \
    tesseract-ocr-heb \
    tesseract-ocr-eng \
    libtesseract-dev \
    libmagic1 \
    libglib2.0-0 \
    libgl1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app

# Create storage directory (ephemeral on Render Free)
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid 10001 --no-create-home app \
    && mkdir -p /app/temp_storage \
    && chown -R app:app /app/temp_storage
USER 10001:10001

# Expose port
EXPOSE 8000

# Health check - verifies readiness without exposing secrets
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f "http://127.0.0.1:${PORT:-8000}/ready" || exit 1

# Run server
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --no-access-log --no-server-header --limit-concurrency 16 --backlog 64 --timeout-keep-alive 5 --timeout-graceful-shutdown 30"]
