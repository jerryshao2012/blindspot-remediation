# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm

ARG APP_VERSION=0.1.0

LABEL org.opencontainers.image.title="AI Engineering Pipeline Evaluation"
LABEL org.opencontainers.image.version="${APP_VERSION}"
LABEL org.opencontainers.image.description="Offline qualification of the AI engineering automation pipeline"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

RUN groupadd --system evaluator \
    && useradd \
        --system \
        --gid evaluator \
        --create-home \
        --home-dir /home/evaluator \
        evaluator

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY src /app/src

RUN python -m pip install --upgrade pip \
    && python -m pip install .

RUN mkdir -p /work /benchmarks /results \
    && chown -R evaluator:evaluator \
        /app \
        /work \
        /benchmarks \
        /results \
        /home/evaluator

USER evaluator

WORKDIR /work

ENTRYPOINT ["pipeline-eval"]
