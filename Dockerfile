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

# Install uv and export dependencies
RUN pip install uv \
 && uv export --frozen --format=requirements-txt > requirements.txt \
 && pip install --no-cache-dir -r requirements.txt

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
    && ap
