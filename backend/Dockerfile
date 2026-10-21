FROM docker.io/python:3.12-slim AS base

LABEL org.opencontainers.image.title="BIMOS API" \
      org.opencontainers.image.description="BIMOS web API and dashboard" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.source="https://github.com/RenatoJVA/BIMOS"

ENV PYTHONUNBUFFERED=1
ENV BIMOS_WORKSPACE=/workspace
ENV BIMOS_CACHE=/cache
ENV BIMOS_LOGS=/logs

WORKDIR /app

# Unprivileged runtime user. The image only ever reads its own code and writes
# under the mounted volumes, so it never needs root after install time.
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

# Wheel-only install: the builder stage resolved the dependency graph once and
# every wheel is already cp312 manylinux, so the runtime needs no compiler.
# Errors are deliberately not silenced: a swallowed resolver failure here shows
# up much later as a missing module inside the container.
COPY --from=builder /deps /deps
RUN python -m pip install --no-cache-dir --no-compile \
      --find-links /deps \
      /deps/*.whl \
    && rm -rf /deps

COPY --from=builder /build/dist/*.whl /tmp/
RUN python -m pip install --no-cache-dir --no-compile /tmp/bimos-*.whl \
    && rm /tmp/bimos-*.whl

USER bimos

EXPOSE 8000

VOLUME ["/workspace", "/cache", "/logs", "/data"]

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

ENTRYPOINT ["bimos"]
CMD ["--help"]
