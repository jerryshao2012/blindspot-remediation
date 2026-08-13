# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm

ARG APP_VERSION=0.1.0

LABEL org.opencontainers.image.title="AI Engineering Orchestrator"
LABEL org.opencontainers.image.version="${APP_VERSION}"
LABEL org.opencontainers.image.description="Deterministic control plane for AI-primary engineering automation"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN groupadd --system orchestrator \
    && useradd \
        --system \
        --gid orchestrator \
        --create-home \
        --home-dir /home/orchestrator \
        orchestrator

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY src /app/src

RUN python -m pip install --upgrade pip \
    && python -m pip install .

RUN mkdir -p /work \
    && chown -R orchestrator:orchestrator \
        /app \
        /work \
        /home/orchestrator

USER orchestrator

WORKDIR /work

ENTRYPOINT ["engineering-orchestrator"]
