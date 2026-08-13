# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm

ARG APP_VERSION=0.1.0

LABEL org.opencontainers.image.title="AI Engineering Production Observability"
LABEL org.opencontainers.image.version="${APP_VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN groupadd --system observability \
    && useradd \
        --system \
        --gid observability \
        --create-home \
        --home-dir /home/observability \
        observability

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY src /app/src

RUN python -m pip install --upgrade pip \
    && python -m pip install .

RUN mkdir -p /work \
    && chown -R observability:observability \
        /app \
        /work \
        /home/observability

USER observability

WORKDIR /work

ENTRYPOINT ["operational-observability"]
