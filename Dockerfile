# ==============================================================================
# Multi-Stage Dockerfile for data-recording
# Base: python:3.12-slim
# ==============================================================================

# Stage 1: Build stage for dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

# Create isolated virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy package metadata and source code for installation
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install dependencies and application package into virtual environment
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Clean up build artifacts, cache, and pip to minimize size
RUN rm -rf /opt/venv/lib/python3.12/site-packages/pip* /opt/venv/bin/pip* && \
    find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type f -name "*.pyc" -delete 2>/dev/null || true && \
    find /opt/venv -type f -name "*.pyo" -delete 2>/dev/null || true

# Stage 2: Final runtime stage
FROM python:3.12-slim AS runner

# Create non-root system user and group
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application source
COPY --chown=appuser:appuser src/ /app/src/

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create volume mount directories with appuser ownership
RUN mkdir -p /app/logs /app/data/uploads && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

EXPOSE 9015

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9015/health')" || exit 1

ENTRYPOINT ["uvicorn", "data_recorder.main:app", "--host", "0.0.0.0", "--port", "9015"]
