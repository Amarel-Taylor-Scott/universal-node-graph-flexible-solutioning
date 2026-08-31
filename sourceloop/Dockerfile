# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv

RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
WORKDIR /build

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip wheel \
    && pip install ".[postgres]"

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    SOURCELOOP_EVIDENCE_DIR=/data/evidence

RUN groupadd --system --gid 10001 sourceloop \
    && useradd --system --uid 10001 --gid sourceloop --home-dir /app --shell /usr/sbin/nologin sourceloop \
    && mkdir -p /app /data/evidence \
    && chown -R sourceloop:sourceloop /app /data/evidence

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=3).read()" || exit 1

ENTRYPOINT ["sourceloop"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
