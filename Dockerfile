# LLM Gateway - Dockerfile
# Multi-stage build for optimized production image

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies to a temporary location
RUN pip install --no-cache-dir --prefix=/install .

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY src/ ./src/
COPY configs/ ./configs/
COPY prompts/ ./prompts/

# Create logs directory
RUN mkdir -p runs/logs

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run the application
CMD ["python", "-m", "uvicorn", "src.llmops.gateway:app", "--host", "0.0.0.0", "--port", "8000"]
