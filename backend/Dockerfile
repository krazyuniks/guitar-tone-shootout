# Multi-stage production build for Guitar Tone Shootout Backend

# Stage 1: Build dependencies
FROM python:3.14-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install NAM VST3 plugin for audio processing
ARG NAM_VERSION=0.7.13
RUN mkdir -p /opt/vst3 && \
    curl -L "https://github.com/sdatkinson/NeuralAmpModelerPlugin/releases/download/v${NAM_VERSION}/NeuralAmpModeler-linux-v${NAM_VERSION}.zip" -o /tmp/nam.zip && \
    unzip /tmp/nam.zip -d /tmp/nam && \
    mv /tmp/nam/NeuralAmpModeler.vst3 /opt/vst3/ && \
    rm -rf /tmp/nam /tmp/nam.zip

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies into a virtual environment
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install -e "."

# Install gunicorn for production
RUN uv pip install gunicorn>=23.0.0

# Stage 2: Production image
FROM python:3.14-slim AS production

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy NAM VST3 plugin from builder
COPY --from=builder /opt/vst3 /usr/lib/vst3
ENV NAM_VST3_PATH=/usr/lib/vst3/NeuralAmpModeler.vst3

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Expose port (internal only, nginx proxies)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run with gunicorn + uvicorn workers
CMD ["gunicorn", "app.main:app", \
    "--bind", "0.0.0.0:8000", \
    "--workers", "4", \
    "--worker-class", "uvicorn.workers.UvicornWorker", \
    "--access-logfile", "-", \
    "--error-logfile", "-"]
