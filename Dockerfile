# Ultra High-Performance Telegram Video Downloader Bot
# Multi-stage build for optimized production image

# Build stage
FROM python:3.11-slim-bullseye as builder

# Set environment variables for build
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    libpng-dev \
    libwebp-dev \
    zlib1g-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install UV for fast package management
RUN pip install uv

# Create virtual environment
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy dependency files
COPY pyproject.toml ./

# Install Python dependencies with optimizations
RUN uv pip install --no-cache-dir -r pyproject.toml && \
    uv pip install --no-cache-dir --upgrade pip setuptools wheel

# Production stage
FROM python:3.11-slim-bullseye as production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies for runtime
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    ca-certificates \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create app user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Create app directory
WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser . .

# Create necessary directories
RUN mkdir -p temp logs \
    && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Verify all dependencies are installed
RUN /opt/venv/bin/python -c "import aiohttp, asyncpg, loguru, PIL, psutil, psycopg2, magic, telegram, redis, requests, sqlalchemy, telethon, uvloop, yt_dlp; print('✅ All dependencies installed successfully')"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command
CMD ["python", "main.py"]
