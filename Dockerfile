# syntax=docker/dockerfile:1.7@sha256:a57df69d0ea827fb7266491f2813635de6f17269be881f696fbfdf2d83dda33e
FROM python:3.12.14-slim-trixie@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f AS patched-base

# Refresh distribution security fixes when this layer is rebuilt without cache.
RUN apt-get update \
    && apt-get upgrade --yes --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir pip==26.2.1

FROM patched-base AS builder

ARG UV_VERSION=0.11.26
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app
RUN pip install --no-cache-dir "uv==${UV_VERSION}"
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM builder AS verification
ENV PATH="/opt/venv/bin:${PATH}"
RUN uv sync --frozen --all-groups --no-editable
COPY tests ./tests
COPY fixtures ./fixtures
COPY assessment ./assessment
COPY config ./config
COPY PRD.md ./PRD.md
COPY templates ./templates
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]

FROM patched-base AS runtime

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=development \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

RUN groupadd --system --gid 10001 banklab \
    && useradd --system --uid 10001 --gid banklab --home-dir /nonexistent banklab \
    && /usr/local/bin/python -m pip uninstall --yes pip \
    && rm -rf /usr/local/lib/python3.12/ensurepip
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=banklab:banklab src ./src
COPY --chown=banklab:banklab migrations ./migrations
COPY --chown=banklab:banklab templates ./templates
COPY --chown=banklab:banklab alembic.ini ./alembic.ini
COPY --chown=banklab:banklab scripts/verify-runtime.py ./scripts/verify-runtime.py
COPY --chown=banklab:banklab --chmod=0555 scripts/container-entrypoint.sh /usr/local/bin/container-entrypoint
RUN mkdir -p /app/runtime && chown banklab:banklab /app/runtime

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=6 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).read()"]

ENTRYPOINT ["container-entrypoint"]
CMD ["uvicorn", "bank_lab.app:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
