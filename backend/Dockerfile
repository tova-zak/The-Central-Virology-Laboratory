# Dockerfile for Central Virology Laboratory Backend
# Target: Render.com Free tier (512 MB RAM, 0.1 CPU)
# Features: Tesseract OCR (Hebrew + English), OpenCV preprocessing

FROM python:3.13-slim

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
RUN mkdir -p /app/temp_storage

# Expose port
EXPOSE 8000

# Health check - verifies readiness without exposing secrets
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f "http://127.0.0.1:${PORT:-8000}/health" || exit 1

# Run server
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --no-access-log"]
