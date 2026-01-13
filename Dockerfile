# ============================================================================
# Auto-Agent-Harness Dockerfile
# ============================================================================
# Multi-stage build for production deployment

# ----------------------------------------------------------------------------
# Stage 1: Build UI
# ----------------------------------------------------------------------------
FROM node:20-alpine AS ui-builder

WORKDIR /app/ui

# Copy package files
COPY ui/package*.json ./

# Install dependencies
RUN npm ci

# Copy source files
COPY ui/ ./

# Build production bundle
RUN npm run build

# ----------------------------------------------------------------------------
# Stage 2: Python Runtime
# ----------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create non-root user for security
RUN groupadd -r auto-agent && useradd -r -g auto-agent auto-agent

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=auto-agent:auto-agent . .

# Copy built UI from builder stage
COPY --from=ui-builder --chown=auto-agent:auto-agent /app/ui/dist /app/ui/dist

# Create directories for data
RUN mkdir -p /app/data /workspace && \
    chown -R auto-agent:auto-agent /app /workspace

# Switch to non-root user
USER auto-agent

# Expose port
EXPOSE 8888

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8888/api/health || exit 1

# Default environment variables
ENV HOST=0.0.0.0 \
    PORT=8888 \
    DATA_DIR=/app/data \
    ALLOWED_ROOT_DIRECTORY=/workspace \
    REQUIRE_LOCALHOST=false \
    AUTH_ENABLED=true

# Start server
CMD ["python", "-m", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8888"]
