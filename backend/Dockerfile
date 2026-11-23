# B-roll Engine backend image — used for both the api and worker services.
# Bundles FFmpeg 7.x (GPL, invoked as external binary), FFprobe, and
# Noto Sans (OFL-1.1, commercial use permitted) for subtitle burn-in.
#
# Multi-stage build:
#   stage 1 "deps"   — install Python deps into a venv (layer-cached)
#   stage 2 "runtime"— copy the venv and app code on top of a slim base

# ---- stage 1: dependency install ----
FROM python:3.12-slim AS deps

WORKDIR /build

# System packages needed only at build time.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip --quiet && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ---- stage 2: runtime image ----
FROM python:3.12-slim AS runtime

# FFmpeg + FFprobe: install from Debian Bookworm (GPL; invoked as external binary).
# Noto Sans: OFL-1.1, free for commercial use, provides subtitle font.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-noto \
    && rm -rf /var/lib/apt/lists/*

# Copy the venv from the deps stage.
COPY --from=deps /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# App code.
WORKDIR /app
COPY . .

# Ensure data and storage directories exist (volumes will shadow these).
RUN mkdir -p /data /storage

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_URL="sqlite:////data/broll.db" \
    STORAGE_LOCAL_ROOT="/storage"

# Default command is the API server; docker-compose overrides it for the worker.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
