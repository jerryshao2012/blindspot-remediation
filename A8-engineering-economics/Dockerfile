# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm

ARG APP_VERSION=0.1.0

LABEL org.opencontainers.image.title="AI Engineering Economics"
LABEL org.opencontainers.image.version="${APP_VERSION}"
LABEL org.opencontainers.image.description="Engineering productivity and automation unit economics"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN groupadd --system economics \
    && useradd \
        --system \
        --gid economics \
        --create-home \
        --home-dir /home/economics \
        economics

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY src /app/src

RUN python -m pip install --upgrade pip \
    && python -m pip install .

RUN mkdir -p /work \
    && chown -R economics:economics \
        /app \
        /work \
        /home/economics

USER economics

WORKDIR /work

ENTRYPOINT ["engineering-economics"]
