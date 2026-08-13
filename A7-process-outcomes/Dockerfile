# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm

ARG APP_VERSION=0.1.0

LABEL org.opencontainers.image.title="AI Engineering Process Outcomes"
LABEL org.opencontainers.image.version="${APP_VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN groupadd --system outcomes \
    && useradd \
        --system \
        --gid outcomes \
        --create-home \
        --home-dir /home/outcomes \
        outcomes

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY src /app/src

RUN python -m pip install --upgrade pip \
    && python -m pip install .

RUN mkdir -p /work \
    && chown -R outcomes:outcomes \
        /app \
        /work \
        /home/outcomes

USER outcomes

WORKDIR /work

ENTRYPOINT ["process-outcomes"]
