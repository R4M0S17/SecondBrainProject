# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY ui/tray/package*.json ./
RUN npm ci
COPY ui/tray/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

COPY core/ core/
COPY main.py .
COPY config/ config/
COPY bin/start_engine.sh bin/
COPY scripts/download-models.sh /scripts/download-models.sh
RUN chmod +x /scripts/download-models.sh
COPY --from=frontend-builder /app/dist/ ui/tray/dist/

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV CEREBRO_FRONTEND_DIR=/app/ui/tray/dist
ENV CEREBRO_MODE=sandbox
EXPOSE 7842

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "main.py"]
