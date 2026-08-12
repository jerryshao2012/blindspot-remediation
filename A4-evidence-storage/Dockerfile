# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm

ARG APP_VERSION=0.1.0

LABEL org.opencontainers.image.title="AI Engineering Evidence Storage"
LABEL org.opencontainers.image.version="${APP_VERSION}"
LABEL org.opencontainers.image.description="Immutable evidence and run-manifest service"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN groupadd --system evidence \
    && useradd \
        --system \
        --gid evidence \
        --create-home \
        --home-dir /home/evidence \
        evidence

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY src /app/src

# Component 1 must be available through the organization's Python package feed
# or installed earlier in a monorepo/container build.
RUN python -m pip install --upgrade pip \
    && python -m pip install .

RUN mkdir -p /work /evidence-store \
    && chown -R evidence:evidence \
        /app \
        /work \
        /evidence-store \
        /home/evidence

USER evidence

WORKDIR /work

ENTRYPOINT ["evidence-store"]
