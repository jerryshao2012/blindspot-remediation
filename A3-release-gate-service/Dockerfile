# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm

ARG APP_VERSION=0.1.0

LABEL org.opencontainers.image.title="AI Engineering Release Gate"
LABEL org.opencontainers.image.version="${APP_VERSION}"
LABEL org.opencontainers.image.description="Deterministic clean-room ReleaseGateService"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system gate \
    && useradd \
        --system \
        --gid gate \
        --create-home \
        --home-dir /home/gate \
        gate

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY src /app/src

# The shared-contracts package must be available from the organization's package
# feed or installed earlier in a monorepo image build.
RUN python -m pip install --upgrade pip \
    && python -m pip install .

RUN mkdir -p /work /gate-artifacts \
    && chown -R gate:gate /app /work /gate-artifacts /home/gate

USER gate
WORKDIR /work

ENTRYPOINT ["release-gate"]
