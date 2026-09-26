# syntax=docker/dockerfile:1.7
FROM python:3.12.11-slim-bookworm AS builder

ARG UV_VERSION=0.11.26
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app
RUN pip install --no-cache-dir "uv==${UV_VERSION}"
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12.11-slim-bookworm AS runtime

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=development \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

RUN groupadd --system --gid 10001 banklab \
    && useradd --system --uid 10001 --gid banklab --home-dir /nonexistent banklab
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=banklab:banklab src ./src
COPY --chown=banklab:banklab migrations ./migrations
COPY --chown=banklab:banklab templates ./templates
COPY --chown=banklab:banklab alembic.ini ./alembic.ini
COPY --chown=banklab:banklab --chmod=0555 scripts/container-entrypoint.sh /usr/local/bin/container-entrypoint

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=6 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).read()"]

ENTRYPOINT ["container-entrypoint"]
CMD ["uvicorn", "bank_lab.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
