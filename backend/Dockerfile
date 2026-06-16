FROM docker.io/python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1
ENV BIMOS_WORKSPACE=/workspace
ENV BIMOS_CACHE=/cache
ENV BIMOS_LOGS=/logs

WORKDIR /app

RUN groupadd -r bimos && useradd -r -g bimos -d /app -s /sbin/nologin bimos \
    && mkdir -p /workspace /cache /logs /data \
    && chown bimos:bimos /workspace /cache /logs /data /app


FROM docker.io/python:3.12-slim AS builder

WORKDIR /build

COPY pyproject.toml README.md ./

RUN pip install --no-cache-dir build wheel \
    && pip download --no-cache-dir --dest /deps ".[db,monitoring]" \
    && python -m build --wheel


FROM base AS runtime

COPY --from=builder /deps /deps
RUN pip install --no-cache-dir \
    --find-links /deps \
    /deps/*.whl 2>/dev/null \
    && rm -rf /deps

COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/bimos-*.whl && rm /tmp/bimos-*.whl

USER bimos

EXPOSE 8000

VOLUME ["/workspace", "/cache", "/logs", "/data"]

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

ENTRYPOINT ["bimos"]
CMD ["--help"]
