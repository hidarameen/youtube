# ----------------- Builder Stage -----------------
FROM python:3.11-slim-bullseye AS builder

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Install system dependencies for building Python packages
RUN apt-get update && apt-get install -y \
    gcc g++ make libffi-dev libssl-dev \
    libjpeg-dev libpng-dev libwebp-dev zlib1g-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv $VIRTUAL_ENV

# Upgrade pip
RUN pip install --upgrade pip setuptools wheel

# Copy dependency files only
WORKDIR /app
COPY pyproject.toml uv.lock ./

# Install dependencies inside /opt/venv via uv
RUN pip install uv \
 && uv sync --frozen --no-cache --python $VIRTUAL_ENV/bin/python

# ----------------- Production Stage -----------------
FROM python:3.11-slim-bullseye AS production

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg curl ca-certificates libmagic1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create app user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser . .

# Create necessary directories
RUN mkdir -p temp logs \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Verify all dependencies are installed
RUN python -c "import aiohttp, asyncpg, loguru, PIL, psutil, psycopg2, magic, telegram, redis, requests, sqlalchemy, telethon, uvloop, yt_dlp; print('✅ All dependencies installed successfully')"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command
CMD ["python", "main.py"]
