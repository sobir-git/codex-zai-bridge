FROM python:3.12.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc build-essential libffi-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv==0.11.3

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ ./src/

RUN uv pip install --system --no-cache-dir .

FROM python:3.12.13-slim AS runtime

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/src /app/src

RUN mkdir -p /app/log

ARG OPENAI_BASE_URL_INTERNAL=http://localhost:8000
ARG OPENAI_BASE_URL=http://localhost:8080
ARG OPENAI_API_KEY=sk-fakekey
ARG API_ADAPTER_HOST=0.0.0.0
ARG API_ADAPTER_PORT=8080
ARG LOG_LEVEL=INFO
ARG LOG_FILE_PATH=/app/log/api_adapter.log

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OPENAI_BASE_URL_INTERNAL=${OPENAI_BASE_URL_INTERNAL} \
    OPENAI_BASE_URL=${OPENAI_BASE_URL} \
    OPENAI_API_KEY=${OPENAI_API_KEY} \
    API_ADAPTER_HOST=${API_ADAPTER_HOST} \
    API_ADAPTER_PORT=${API_ADAPTER_PORT} \
    LOG_LEVEL=${LOG_LEVEL} \
    LOG_FILE_PATH=${LOG_FILE_PATH}

RUN echo '#!/bin/sh\nexec uvicorn open_responses_server.server_entrypoint:app --host $API_ADAPTER_HOST --port $API_ADAPTER_PORT "$@"' > /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh

RUN adduser --disabled-password --gecos "" appuser && \
    chown -R appuser:appuser /app/log && \
    chown appuser:appuser /app/entrypoint.sh

USER appuser

CMD ["sh", "/app/entrypoint.sh"]
