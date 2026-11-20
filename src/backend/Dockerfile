FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    MODEL_PATH=/models/best.pt \
    YOLO_CONFIG_DIR=/tmp

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
      libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

RUN mkdir -p /tmp/Ultralytics
COPY src/backend/main.py ./src/backend/main.py

EXPOSE 8000
CMD ["uvicorn", "src.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
